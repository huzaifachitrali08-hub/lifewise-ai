import hashlib
import hmac
import re
import secrets
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "lifewise.db"
PBKDF2_ITERATIONS = 310_000


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db():
    """Create tables and safely migrate older LIFEWISE databases."""
    with connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            education TEXT NOT NULL DEFAULT '',
            interests TEXT NOT NULL DEFAULT '',
            skills TEXT NOT NULL DEFAULT '',
            age INTEGER,
            gender TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            preferences TEXT NOT NULL DEFAULT
                'Explain step by step and use practical examples.',
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS user_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            approved INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS user_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            area TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS user_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_user_memories_user
            ON user_memories(user_id, id);
        CREATE INDEX IF NOT EXISTS idx_user_goals_user
            ON user_goals(user_id, id);
        CREATE INDEX IF NOT EXISTS idx_user_messages_user
            ON user_messages(user_id, id);
        """)
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "email" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        profile_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(user_profiles)").fetchall()
        }
        if "profile_photo" not in profile_columns:
            conn.execute("ALTER TABLE user_profiles ADD COLUMN profile_photo BLOB")
        if "community_visible" not in profile_columns:
            conn.execute("ALTER TABLE user_profiles ADD COLUMN community_visible INTEGER NOT NULL DEFAULT 0")
        if "age" not in profile_columns:
            conn.execute("ALTER TABLE user_profiles ADD COLUMN age INTEGER")
        if "gender" not in profile_columns:
            conn.execute("ALTER TABLE user_profiles ADD COLUMN gender TEXT NOT NULL DEFAULT ''")
        if "location" not in profile_columns:
            conn.execute("ALTER TABLE user_profiles ADD COLUMN location TEXT NOT NULL DEFAULT ''")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS direct_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            read_at TEXT,
            FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(recipient_id) REFERENCES users(id) ON DELETE CASCADE,
            CHECK(sender_id <> recipient_id)
        );
        CREATE INDEX IF NOT EXISTS idx_dm_pair_id
            ON direct_messages(sender_id, recipient_id, id);
        CREATE INDEX IF NOT EXISTS idx_dm_recipient_read
            ON direct_messages(recipient_id, read_at, id);
        CREATE TABLE IF NOT EXISTS community_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            image BLOB,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
            CHECK(length(content) <= 2000)
        );
        CREATE INDEX IF NOT EXISTS idx_community_messages_id
            ON community_messages(id);
        CREATE TABLE IF NOT EXISTS community_message_hidden (
            user_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            PRIMARY KEY(user_id, message_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(message_id) REFERENCES community_messages(id) ON DELETE CASCADE
        );
        """)
        # Version 7: optional file attachments for private and community messages.
        for table in ("direct_messages", "community_messages"):
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for column, definition in (
                ("attachment_name", "TEXT"),
                ("attachment_mime", "TEXT"),
                ("attachment_size", "INTEGER"),
                ("attachment_data", "BLOB"),
            ):
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dm_sender_recipient_id ON direct_messages(sender_id, recipient_id, id DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dm_recipient_sender_id ON direct_messages(recipient_id, sender_id, id DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_public_profiles_name ON user_profiles(community_visible, name COLLATE NOCASE)")
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique
            ON users(email COLLATE NOCASE)
            WHERE email IS NOT NULL
        """)


def _hash_password(password, salt_hex=None):
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return digest.hex(), salt.hex()


def _valid_email(email):
    email = email.strip()
    return len(email) <= 254 and re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+", email
    ) is not None


def register_user(email, password):
    email = email.strip().lower()
    if not _valid_email(email):
        return False, "Please enter a valid email address.", None
    if len(password) < 8:
        return False, "Password must contain at least 8 characters.", None
    password_hash, salt = _hash_password(password)
    try:
        with connect() as conn:
            cursor = conn.execute(
                """INSERT INTO users
                   (username, email, password_hash, password_salt)
                   VALUES (?, ?, ?, ?)""",
                (email, email, password_hash, salt)
            )
            user_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO user_profiles(user_id) VALUES (?)", (user_id,)
            )
        return True, "Account created successfully.", {
            "id": user_id, "email": email, "username": email
        }
    except sqlite3.IntegrityError:
        return False, "This email address is already registered. Please log in.", None


def authenticate_user(email, password):
    email = email.strip().lower()
    with connect() as conn:
        row = conn.execute(
            """SELECT id, username, email, password_hash, password_salt
               FROM users
               WHERE (email = ? COLLATE NOCASE)
                  OR (email IS NULL AND username = ? COLLATE NOCASE)
               LIMIT 1""",
            (email, email)
        ).fetchone()
    if not row:
        return None
    candidate_hash, _ = _hash_password(password, row["password_salt"])
    if not hmac.compare_digest(candidate_hash, row["password_hash"]):
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "username": row["email"] or row["username"]
    }


# PROFILE
def get_profile(user_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id=?", (user_id,)
        ).fetchone()
        return dict(row) if row else {}


def save_profile(user_id, name, education, interests, skills, preferences,
                 age=None, gender="", location=""):
    """Save profile details; age, gender and location are optional."""
    age_value = int(age) if age not in (None, "", 0, "0") else None
    if age_value is not None and not 13 <= age_value <= 120:
        raise ValueError("Please enter an age between 13 and 120, or leave it blank.")
    with connect() as conn:
        conn.execute("""
            INSERT INTO user_profiles
                (user_id, name, education, interests, skills, preferences, age, gender, location)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name=excluded.name, education=excluded.education,
                interests=excluded.interests, skills=excluded.skills,
                preferences=excluded.preferences, age=excluded.age,
                gender=excluded.gender, location=excluded.location
        """, (
            user_id, name.strip(), education.strip(), interests.strip(),
            skills.strip(), preferences.strip(), age_value,
            (gender or "").strip(), (location or "").strip()
        ))


def save_profile_photo(user_id, photo_bytes):
    """Save or clear a user's profile image in their own profile row."""
    with connect() as conn:
        conn.execute(
            "UPDATE user_profiles SET profile_photo=? WHERE user_id=?",
            (photo_bytes, user_id)
        )


def save_community_visibility(user_id, visible):
    with connect() as conn:
        conn.execute(
            "UPDATE user_profiles SET community_visible=? WHERE user_id=?",
            (int(bool(visible)), user_id)
        )


def list_public_users(query="", exclude_user_id=None, limit=50):
    """Return discoverable profile fields only; never expose email or private data."""
    sql = """
        SELECT u.id, p.name, p.education, p.interests, p.skills, p.age,
               p.gender, p.location, p.profile_photo
        FROM users u JOIN user_profiles p ON p.user_id=u.id
        WHERE p.community_visible=1
    """
    params = []
    if exclude_user_id is not None:
        sql += " AND u.id<>?"
        params.append(exclude_user_id)
    if query and query.strip():
        term = f"%{query.strip()}%"
        sql += " AND (p.name LIKE ? OR p.interests LIKE ? OR p.education LIKE ? OR p.location LIKE ?)"
        params.extend([term, term, term, term])
    sql += " ORDER BY p.name COLLATE NOCASE LIMIT ?"
    params.append(int(limit))
    with connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def send_direct_message(sender_id, recipient_id, content, attachment=None):
    content = str(content).strip()
    if not content and attachment is None:
        raise ValueError("Write a message or attach a file.")
    if len(content) > 4000:
        raise ValueError("Message must be 4,000 characters or fewer.")
    if int(sender_id) == int(recipient_id):
        raise ValueError("You cannot message your own account.")
    with connect() as conn:
        recipient = conn.execute("SELECT id FROM users WHERE id=?", (recipient_id,)).fetchone()
        if not recipient:
            raise ValueError("This user account could not be found.")
        conn.execute(
            """INSERT INTO direct_messages
               (sender_id, recipient_id, content, attachment_name, attachment_mime, attachment_size, attachment_data)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sender_id, recipient_id, content,
             attachment.get("name") if attachment else None,
             attachment.get("mime") if attachment else None,
             attachment.get("size") if attachment else None,
             attachment.get("data") if attachment else None)
        )


def get_direct_messages(user_id, other_user_id, limit=100):
    """Only the two participants can retrieve this private conversation."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT m.id, m.sender_id, m.recipient_id, m.content, m.created_at,
                   m.read_at, m.attachment_name, m.attachment_mime,
                   m.attachment_size, m.attachment_data, p.name AS sender_name,
                   p.profile_photo AS sender_photo
            FROM direct_messages m
            JOIN user_profiles p ON p.user_id=m.sender_id
            WHERE (m.sender_id=? AND m.recipient_id=?)
               OR (m.sender_id=? AND m.recipient_id=?)
            ORDER BY m.id DESC LIMIT ?
        """, (user_id, other_user_id, other_user_id, user_id, int(limit))).fetchall()
        return [dict(row) for row in reversed(rows)]


def list_conversations(user_id, limit=50):
    """Return one latest-message preview per conversation for this user only."""
    with connect() as conn:
        rows = conn.execute("""
            WITH conversation_rows AS (
                SELECT CASE WHEN sender_id=? THEN recipient_id ELSE sender_id END AS other_id,
                       id, content, created_at,
                       CASE WHEN sender_id=? THEN 0 ELSE 1 END AS incoming
                FROM direct_messages
                WHERE sender_id=? OR recipient_id=?
            ), ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY other_id ORDER BY id DESC) AS rn
                FROM conversation_rows
            )
            SELECT r.other_id, p.name, p.profile_photo, r.content, r.created_at,
                   (SELECT COUNT(*) FROM direct_messages unread
                    WHERE unread.sender_id=r.other_id AND unread.recipient_id=?
                      AND unread.read_at IS NULL) AS unread_count
            FROM ranked r JOIN user_profiles p ON p.user_id=r.other_id
            WHERE r.rn=1 ORDER BY r.id DESC LIMIT ?
        """, (user_id, user_id, user_id, user_id, user_id, int(limit))).fetchall()
        return [dict(row) for row in rows]


def send_community_message(sender_id, content="", image_bytes=None, attachment=None):
    """Publish a post to the shared room. Only opted-in members may post."""
    content = str(content or "").strip()
    if len(content) > 2000:
        raise ValueError("Message must be 2,000 characters or fewer.")
    if not content and image_bytes is None and attachment is None:
        raise ValueError("Write a message or attach a file or picture.")
    with connect() as conn:
        member = conn.execute(
            "SELECT community_visible FROM user_profiles WHERE user_id=?",
            (sender_id,)
        ).fetchone()
        if not member or not member["community_visible"]:
            raise ValueError("Enable Community visibility in your profile before posting.")
        conn.execute(
            """INSERT INTO community_messages
               (sender_id, content, image, attachment_name, attachment_mime, attachment_size, attachment_data)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sender_id, content, image_bytes,
             attachment.get("name") if attachment else None,
             attachment.get("mime") if attachment else None,
             attachment.get("size") if attachment else None,
             attachment.get("data") if attachment else None)
        )


def list_community_messages(limit=100, viewer_id=None):
    """Return visible posts, excluding messages this viewer hid for themselves."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT m.id, m.sender_id, m.content, m.image, m.created_at,
                   m.attachment_name, m.attachment_mime, m.attachment_size, m.attachment_data,
                   p.name AS sender_name, p.profile_photo
            FROM community_messages m
            JOIN user_profiles p ON p.user_id=m.sender_id
            LEFT JOIN community_message_hidden h
              ON h.message_id=m.id AND h.user_id=?
            WHERE p.community_visible=1 AND h.message_id IS NULL
            ORDER BY m.id DESC LIMIT ?
        """, (viewer_id if viewer_id is not None else -1, int(limit))).fetchall()
        return [dict(row) for row in reversed(rows)]


def delete_own_community_message(user_id, message_id):
    """Delete a community post only when the requesting user authored it."""
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM community_messages WHERE id=? AND sender_id=?",
            (int(message_id), int(user_id))
        )
        return cur.rowcount > 0


def hide_community_messages_for_user(user_id):
    """Hide the current community history for this user only; others retain it."""
    with connect() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO community_message_hidden(user_id, message_id)
            SELECT ?, id FROM community_messages
        """, (int(user_id),))


def mark_direct_messages_read(user_id, other_user_id):
    with connect() as conn:
        conn.execute("""
            UPDATE direct_messages SET read_at=CURRENT_TIMESTAMP
            WHERE sender_id=? AND recipient_id=? AND read_at IS NULL
        """, (other_user_id, user_id))


def unread_direct_message_count(user_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM direct_messages WHERE recipient_id=? AND read_at IS NULL",
            (user_id,)
        ).fetchone()
        return int(row["n"])


# MEMORIES
def add_memory(user_id, content, category="General", approved=True):
    content = content.strip()
    category = category.strip() or "General"
    if not content:
        raise ValueError("Memory content cannot be empty.")
    with connect() as conn:
        cursor = conn.execute("""
            INSERT INTO user_memories (user_id, content, category, approved)
            VALUES (?, ?, ?, ?)
        """, (user_id, content, category, int(bool(approved))))
        return cursor.lastrowid


def list_memories(user_id, include_pending=True, category=None, query=None, limit=200):
    sql = "SELECT * FROM user_memories WHERE user_id=?"
    params = [user_id]
    if not include_pending:
        sql += " AND approved=1"
    if category and category != "All":
        sql += " AND category=?"
        params.append(category)
    if query and query.strip():
        term = f"%{query.strip()}%"
        sql += " AND (content LIKE ? OR category LIKE ?)"
        params.extend([term, term])
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_approved_memories(user_id, limit=50):
    with connect() as conn:
        rows = conn.execute("""
            SELECT * FROM user_memories
            WHERE user_id=? AND approved=1 ORDER BY id DESC LIMIT ?
        """, (user_id, int(limit))).fetchall()
        return [dict(r) for r in rows]


def update_memory(user_id, memory_id, content, category=None, approved=None):
    content = content.strip()
    if not content:
        raise ValueError("Memory content cannot be empty.")
    assignments, params = ["content=?"], [content]
    if category is not None:
        assignments.append("category=?")
        params.append(category.strip() or "General")
    if approved is not None:
        assignments.append("approved=?")
        params.append(int(bool(approved)))
    params.extend([memory_id, user_id])
    with connect() as conn:
        cur = conn.execute(
            f"UPDATE user_memories SET {', '.join(assignments)} WHERE id=? AND user_id=?",
            params
        )
        return cur.rowcount > 0


def delete_memory(user_id, memory_id):
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM user_memories WHERE id=? AND user_id=?",
            (memory_id, user_id)
        )
        return cur.rowcount > 0


# GOALS
def add_goal(user_id, title, area):
    title = title.strip()
    if not title:
        raise ValueError("Goal cannot be empty.")
    with connect() as conn:
        conn.execute(
            "INSERT INTO user_goals(user_id, title, area) VALUES (?, ?, ?)",
            (user_id, title, area)
        )


def list_goals(user_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM user_goals WHERE user_id=? ORDER BY id DESC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_goal_status(user_id, goal_id, status):
    with connect() as conn:
        cur = conn.execute(
            "UPDATE user_goals SET status=? WHERE id=? AND user_id=?",
            (status, goal_id, user_id)
        )
        return cur.rowcount > 0


def delete_goal(user_id, goal_id):
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM user_goals WHERE id=? AND user_id=?",
            (goal_id, user_id)
        )
        return cur.rowcount > 0


# CHAT
def save_message(user_id, role, content):
    if role not in ("user", "assistant"):
        raise ValueError("Invalid message role.")
    with connect() as conn:
        conn.execute(
            "INSERT INTO user_messages(user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content)
        )


def recent_messages(user_id, limit=30):
    """Return recent chat messages in chronological order, including timestamps."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT role, content, created_at FROM user_messages
            WHERE user_id=? ORDER BY id DESC LIMIT ?
        """, (user_id, int(limit))).fetchall()
        return [dict(r) for r in reversed(rows)]


def clear_chat(user_id):
    with connect() as conn:
        conn.execute("DELETE FROM user_messages WHERE user_id=?", (user_id,))
