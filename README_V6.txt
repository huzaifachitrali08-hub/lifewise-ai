LIFEWISE AI — VERSION 6 COMMUNITY UPDATE

WHAT'S NEW
- Member community directory for registered accounts.
- Members can search profiles by name, education or interests.
- Members can start private one-to-one conversations.
- Direct messages are stored with timestamps and unread status.
- Message view refreshes every five seconds while open.
- Optional profile photo upload/change/removal (JPG/PNG, max 3 MB).
- Profile photos are normalized to small JPEG files and stored in SQLite.
- Community visibility is OFF by default and must be enabled by each member.
- Only opted-in profiles appear in the member directory.
- Email addresses, goals, memories and AI counselor conversations are not exposed.
- Existing Version 5 counselor, guest mode, goals, memories, branding and chat behavior are retained.

IMPORTANT DATA NOTES
- This update migrates the existing lifewise.db in place. It adds profile_photo and
  community_visible columns and a direct_messages table. It does not delete existing
  accounts, profile information, memories, goals or counselor messages.
- Make a copy of lifewise.db before upgrading.
- Guest mode still does not write messages or profile data to the database.
- Peer messaging is for registered accounts only.
- This SQLite version is suitable for local development / a single shared app
  instance. For a public multi-device deployment, move to a hosted database and
  persistent object storage before inviting real users. SQLite on a developer's
  laptop does not synchronize across separate computers.

INSTALLATION (WINDOWS / VS CODE)
1. Stop the running app in the terminal with Ctrl+C.
2. Make a backup copy of your current project folder and lifewise.db.
3. Replace app.py, db.py and counselor.py with the V6 files.
4. Keep your existing .env file and lifewise.db file. Keep lifewise_logo.png.
5. In the project terminal, activate your virtual environment.
6. Run: pip install -r requirements.txt
7. Run: streamlit run app.py

FIRST TEST
1. Log in with your existing account. Confirm your old goals, memories and AI chat remain.
2. Open Profile. Upload a JPG or PNG and save it.
3. Enable "Show my profile in Community" and save.
4. Create or log in to a second test account in another browser/incognito window.
5. Enable Community visibility on that account too.
6. Open Community, find the other test account and select Message.
7. Open Messages and send a private message. It should appear for the recipient
   after the automatic refresh (within about five seconds).
8. Confirm one account cannot see the other's private counselor conversation,
   goals, memories or email address.
9. Confirm Guest mode still works without creating database records.

SECURITY / PRIVACY
- Only authenticated registered members can use Community and Messages.
- Members must opt in before their basic profile appears in Community.
- Private messages are retrieved only for the two participants.
- This is still a development prototype. Before public launch, add email verification,
  rate limits, abuse reporting/blocking, moderation, HTTPS, backups and hosted storage.

COMMUNITY GROUP CHAT + PICTURE SHARING (V6 UPDATE)
- The Community tab now includes one shared group chat for opted-in members.
- Registered members must enable "Show my profile in Community" before they can
  post or view the shared community feed.
- Members can post text and optionally attach a JPG/PNG picture (max 3 MB).
- Uploaded pictures are validated, resized and stored in the SQLite database.
- The community feed refreshes automatically about every five seconds.
- The existing member directory and private one-to-one messages remain available.
- The database automatically creates a community_messages table on startup; existing
  account and counselor data is retained. Back up lifewise.db before upgrading.

IMPORTANT BEFORE PUBLIC LAUNCH
This is a student-project prototype. A shared chat and image feed need active
moderation before use by the public. Add administrator moderation, report and block
controls, rate limits, content/image review, account verification, secure hosted
storage, HTTPS and a clear community safety policy. Do not post private information.

VERSION 6.1 — MESSAGING & PROFILE IMPROVEMENTS

- Private Messages now call the page auto-scroll helper after rendering the conversation.
  This keeps the newest messages and message composer in view after a send or periodic
  refresh, while users can still scroll upward to read older messages.
- Profile editor now supports optional age, gender and location fields.
- Profile page displays the added details.
- Community member cards can display age, gender and location only when the member
  has opted into Community visibility.
- These fields are optional. Enter 0 for age to leave it blank, and leave gender or
  location blank if you do not want to provide them.
- Existing databases are migrated safely by adding columns; existing accounts and
  stored information are retained. Back up lifewise.db before updating.
- Community visibility remains opt-in. When enabled, age, gender and location that
  a member has provided are visible to other opted-in community members. Do not add
  information you do not want other community members to see.


LIFEWISE AI VERSION 7.0 - COMMUNITY CHAT AND FILE SHARING UPDATE

New in Version 7.0
- Community member search now includes name, education, interests and location.
- Private messages support one attachment per message.
- Community group posts support one document/file attachment per post, alongside an optional picture.
- Attachment types: PDF, DOC, DOCX, XLS, XLSX, CSV, PPT, PPTX, TXT, JPG, JPEG, PNG, GIF, WEBP and ZIP.
- Maximum attachment size: 10 MB per file. Profile photos remain limited to 3 MB.
- Recipients can download attachments from the message where they were shared.
- Chat scrolling targets the latest message and composer more directly.
- Background chat refresh is now every 8 seconds to reduce repeated reruns.
- SQLite uses WAL mode, a busy timeout and additional message/profile indexes to improve concurrent reads and search.

UPGRADE NOTES
- Existing users and existing messages are preserved. New attachment columns are added automatically when the app starts.
- Back up lifewise.db before deploying this version.
- Attachments are stored inside SQLite. This is suitable for a small student project or a single shared app instance. For a larger public service, use private object storage and a hosted database.
- The file type list is intentionally restricted; executable files and unknown file types are not accepted.
- Do not commit API keys, .env files, or lifewise.db to a public GitHub repository.
- Before public launch, add email verification, rate limits, abuse reporting/blocking, moderation, HTTPS, backups and hosted storage.

Version 7.2 update (private messaging and community controls)
- Fixed the private-message Refresh button so it triggers a Streamlit rerun and reloads the selected conversation.
- Private-message records now include the sender's profile photo; the chat uses the current user's photo for outgoing messages and the sender's photo for incoming messages, with a default avatar when no photo exists.
- Community members can hide the current community history from their own view using "Clear chat for me". This does not delete other members' history.
- Members can delete only their own community posts. They cannot delete another member's post.
- A small community_message_hidden table is created automatically during database initialization; existing data is preserved.

Upgrade notes:
1. Back up lifewise.db before replacing files.
2. Keep your existing .env file and API key private.
3. Replace app.py and db.py with the files in this package (or replace the whole project folder after backing it up).
4. Install requirements with: pip install -r requirements.txt
5. Start with: streamlit run app.py
