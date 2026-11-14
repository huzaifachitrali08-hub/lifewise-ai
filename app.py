import base64
import json
import mimetypes
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

import streamlit as st
from dotenv import load_dotenv

from db import (
    init_db, register_user, authenticate_user,
    get_profile, save_profile, save_profile_photo, save_community_visibility,
    list_public_users, send_direct_message, get_direct_messages,
    list_conversations, mark_direct_messages_read, unread_direct_message_count,
    send_community_message, list_community_messages,
    delete_own_community_message, hide_community_messages_for_user,
    add_goal, list_goals, update_goal_status, delete_goal,
    add_memory, list_memories, get_approved_memories,
    update_memory, delete_memory,
    save_message, recent_messages, clear_chat
)
from counselor import get_counselor_reply
from streamlit_autorefresh import st_autorefresh

load_dotenv()
init_db()

st.set_page_config(
    page_title="LIFEWISE AI | Personal AI Counselor",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

APP_DIR = Path(__file__).parent
LOGO_PATH = APP_DIR / "lifewise_logo.png"
MEMORY_CATEGORIES = [
    "General", "Career", "Education", "Skills",
    "Interests", "Preferences", "Personal", "Projects"
]
MAX_PROFILE_PHOTO_BYTES = 3 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_TYPES = [
    "pdf", "doc", "docx", "xls", "xlsx", "csv", "ppt", "pptx", "txt",
    "jpg", "jpeg", "png", "gif", "webp", "zip"
]


def prepare_attachment(uploaded_file):
    """Validate one supported attachment and return bytes plus safe metadata."""
    if uploaded_file is None:
        return None
    data = uploaded_file.getvalue()
    if not data:
        raise ValueError("The selected file is empty.")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise ValueError("Each attachment must be 10 MB or smaller.")
    name = Path(uploaded_file.name).name
    extension = Path(name).suffix.lower().lstrip(".")
    if extension not in ALLOWED_ATTACHMENT_TYPES:
        raise ValueError("This file type is not supported. Choose a document, spreadsheet, presentation, image, text or ZIP file.")
    mime = uploaded_file.type or mimetypes.guess_type(name)[0] or "application/octet-stream"
    return {"name": name, "mime": mime, "size": len(data), "data": data}


def show_message_attachment(message, key):
    if message.get("attachment_data") and message.get("attachment_name"):
        size_mb = (message.get("attachment_size") or 0) / (1024 * 1024)
        st.download_button(
            f"📎 {message['attachment_name']} · {size_mb:.2f} MB",
            data=message["attachment_data"],
            file_name=message["attachment_name"],
            mime=message.get("attachment_mime") or "application/octet-stream",
            key=f"download_{key}",
            use_container_width=False
        )



def prepare_profile_photo(uploaded_file):
    """Validate and normalize uploaded photos to small JPEG images."""
    if uploaded_file is None:
        return None
    raw = uploaded_file.getvalue()
    if len(raw) > MAX_PROFILE_PHOTO_BYTES:
        raise ValueError("Please choose an image smaller than 3 MB.")
    try:
        image = Image.open(BytesIO(raw))
        image.verify()
        image = Image.open(BytesIO(raw)).convert("RGB")
        image.thumbnail((512, 512))
        output = BytesIO()
        image.save(output, format="JPEG", quality=85, optimize=True)
        return output.getvalue()
    except Exception as exc:
        raise ValueError("That file is not a supported image. Please upload JPG or PNG.") from exc


def display_name(user_row):
    return (user_row.get("name") or "LIFEWISE member").strip()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root{--navy:#172f54;--blue:#315fce;--ink:#1d2b3f;--muted:#718096;--line:#e5eaf2}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;color:var(--ink)}
.stApp{background:#f5f7fb}[data-testid="stAppViewContainer"]{background:transparent}
.block-container{padding-top:1.1rem;padding-bottom:3rem;max-width:1440px}
header[data-testid="stHeader"]{background:rgba(245,247,251,.92)}footer{visibility:hidden}
.lw-brand-copy{color:var(--muted);font-size:.88rem;margin-top:-.25rem}
.lw-status{display:inline-flex;align-items:center;gap:.45rem;color:#137a65;font-weight:700;font-size:.78rem;background:#eaf7f3;padding:.42rem .72rem;border-radius:99px;white-space:nowrap}
.lw-dot{width:7px;height:7px;border-radius:50%;background:#19a783;display:inline-block}
.lw-hero{padding:1.45rem 1.65rem;border-radius:20px;background:linear-gradient(112deg,#172f54,#315fce 78%,#4978df);color:white;box-shadow:0 10px 26px rgba(37,76,154,.12);margin:.35rem 0 1.15rem}
.lw-hero h2{color:white!important;font-family:Manrope,sans-serif;margin:0 0 .38rem;font-size:1.55rem;letter-spacing:-.025em}
.lw-hero p{color:#e8efff!important;margin:0;line-height:1.55}
.lw-auth-panel{background:#fff;border:1px solid var(--line);border-radius:22px;padding:1.4rem;box-shadow:0 8px 28px rgba(20,43,74,.045);min-height:100%}
.lw-auth-hero{background:linear-gradient(145deg,#172f54,#315fce 76%,#4778d8);color:#fff;border-radius:22px;padding:2rem 1.65rem;min-height:430px}
.lw-auth-hero h1{color:white!important;font-family:Manrope,sans-serif;font-size:2.05rem;line-height:1.2;letter-spacing:-.035em}
.lw-auth-hero p{color:#e8efff!important;line-height:1.65}
.lw-feature{border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.09);border-radius:13px;padding:.78rem .9rem;margin-top:.7rem}
.lw-card{padding:1.05rem 1.15rem;border:1px solid var(--line);border-radius:16px;background:#fff;box-shadow:0 3px 13px rgba(20,43,74,.035);margin-bottom:.8rem}
.lw-guest{border-color:#cbd9f7;background:#f2f6ff}
.lw-metric{background:#fff;border:1px solid var(--line);border-radius:16px;padding:1rem 1.1rem;min-height:105px;box-shadow:0 3px 13px rgba(20,43,74,.035)}
.lw-metric-label{color:var(--muted);font-size:.82rem;font-weight:600}
.lw-metric-value{color:var(--navy);font:800 1.75rem Manrope,sans-serif;margin-top:.25rem}
.lw-subtle{color:var(--muted);font-size:.9rem}
[data-testid="stChatMessage"]{border:1px solid var(--line);border-radius:16px;padding:.85rem 1rem;background:#fff;box-shadow:0 2px 10px rgba(20,43,74,.03);margin-bottom:.7rem}
[data-testid="stChatInput"]{border:1px solid #d7e0ef;border-radius:16px;box-shadow:0 4px 16px rgba(37,76,154,.06);background:#fff}
[data-testid="stChatInput"] textarea{font-size:1rem}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"]{line-height:1.7}
.lw-chat-meta{color:#8793a5;font-size:.72rem;margin-top:.25rem}
div.stButton>button,div.stFormSubmitButton>button{border-radius:11px;font-weight:650;min-height:2.55rem;border:1px solid #dbe3ef}
div.stButton>button[kind="primary"],div.stFormSubmitButton>button[kind="primary"]{background:var(--blue);border:0;color:white}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--line)}
[data-testid="stSidebar"] [data-testid="stImage"] img{border-radius:12px}
.stRadio [role="radiogroup"]{gap:.35rem}
.stRadio [role="radiogroup"] label{background:#fff;border:1px solid var(--line);border-radius:11px;padding:.48rem .78rem;margin:0;font-weight:650}
.stRadio [role="radiogroup"] label:has(input:checked){background:#eaf0ff;border-color:#b9c9f2;color:#244aa8}
div[data-testid="stExpander"]{border:1px solid var(--line);border-radius:13px}
hr{border-color:var(--line)}
@media(max-width:800px){.block-container{padding-left:.85rem;padding-right:.85rem;padding-top:.7rem}.lw-auth-hero{min-height:auto;padding:1.45rem}.lw-hero{padding:1.15rem 1.2rem;border-radius:16px}.lw-hero h2{font-size:1.3rem}.lw-auth-hero h1{font-size:1.65rem}.stRadio [role="radiogroup"]{flex-wrap:wrap}.stRadio [role="radiogroup"] label{padding:.4rem .58rem;font-size:.82rem}}
</style>
""", unsafe_allow_html=True)


def show_brand():
    brand_col, status_col = st.columns([5, 1])
    with brand_col:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=250)
        else:
            st.markdown("# 🧭 LIFEWISE AI")
        st.markdown('<div class="lw-brand-copy">Your personal AI counselor · Learn · Grow · Achieve</div>', unsafe_allow_html=True)
    with status_col:
        st.markdown('<div style="height:20px"></div><div class="lw-status"><span class="lw-dot"></span> Ready to help</div>', unsafe_allow_html=True)


def show_authentication():
    show_brand()
    st.markdown('<div class="lw-hero"><h2>A clearer path starts with one conversation.</h2><p>Get thoughtful guidance for your learning, career, goals and personal growth.</p></div>', unsafe_allow_html=True)
    left, right = st.columns([1.05, 1.15], gap="large")
    with left:
        st.markdown("""
        <div class="lw-auth-hero">
          <div style="font-size:2.2rem;margin-bottom:.8rem">✦ 🧭</div>
          <h1>Make your next step a confident one.</h1>
          <p>LIFEWISE AI helps you turn questions into practical next steps, one conversation at a time.</p>
          <div class="lw-feature"><b>🎯 Plan your goals</b><br><small>Break big ambitions into manageable actions.</small></div>
          <div class="lw-feature"><b>📚 Grow your skills</b><br><small>Build realistic learning paths and study plans.</small></div>
          <div class="lw-feature"><b>💬 Get personal guidance</b><br><small>Ask questions in a simple, supportive chat.</small></div>
        </div>
        """, unsafe_allow_html=True)
    with right:
        st.markdown('<div class="lw-auth-panel">', unsafe_allow_html=True)
        st.markdown("### Welcome to LIFEWISE AI")
        st.caption("Choose how you would like to continue.")
        st.markdown("""
        <div class="lw-card lw-guest">
          <h3 style="margin:.1rem 0 .35rem;color:#153d76">💬 Continue as Guest</h3>
          <p style="margin:0 0 .3rem">Try the personal AI counselor without creating an account.</p>
          <small style="color:#64748b">Guest chats are temporary and are not saved to the database.</small>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Continue as Guest  →", type="primary", use_container_width=True):
            st.session_state["guest_mode"] = True
            st.session_state["guest_messages"] = []
            st.rerun()
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div class="lw-card">
          <h3 style="margin:.1rem 0 .35rem;color:#153d76">🔐 Your private workspace</h3>
          <p style="margin:0">Create an account to keep your profile, goals, approved memories and conversation history.</p>
        </div>
        """, unsafe_allow_html=True)
        login_tab, register_tab = st.tabs(["Log in", "Create account"])
        with login_tab:
            with st.form("login_form"):
                login_email = st.text_input("Email address", placeholder="you@example.com")
                login_password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
            if submitted:
                user = authenticate_user(login_email, login_password)
                if user:
                    st.session_state["user"] = user
                    st.session_state.pop("guest_mode", None)
                    st.rerun()
                else:
                    st.error("Incorrect email address or password.")
        with register_tab:
            with st.form("register_form"):
                new_email = st.text_input("Email address", placeholder="you@example.com")
                new_password = st.text_input("Choose a password", type="password", help="Use at least 8 characters.")
                confirm_password = st.text_input("Confirm password", type="password")
                submitted = st.form_submit_button("Create my account", type="primary", use_container_width=True)
            if submitted:
                if new_password != confirm_password:
                    st.error("The passwords do not match.")
                else:
                    ok, message, user = register_user(new_email, new_password)
                    if ok:
                        st.session_state["user"] = user
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        st.markdown("</div>", unsafe_allow_html=True)
    st.caption("Guest conversations are temporary. Registered accounts keep their own private profile, goals, memories and chat history.")


def show_onboarding(user_id):
    profile = get_profile(user_id)
    goals = list_goals(user_id)
    has_profile = bool(profile.get("name", "").strip() and profile.get("education", "").strip())
    has_goal = len(goals) > 0

    if has_profile and has_goal:
        return False

    st.title("🧭 Let's set up your LIFEWISE AI profile")
    st.progress((int(has_profile) + int(has_goal)) / 2)
    st.caption("Complete these two short steps before opening your personal dashboard.")

    if not has_profile:
        st.subheader("Step 1 of 2 · Create your profile")
        with st.form("onboarding_profile"):
            name = st.text_input("Preferred name", value=profile.get("name", ""))
            education = st.text_input("Education", value=profile.get("education", ""))
            age = st.number_input("Age (optional; enter 0 to leave blank)", min_value=0, max_value=120,
                                  value=int(profile.get("age") or 0), step=1)
            gender = st.selectbox("Gender (optional)", ["", "Female", "Male", "Non-binary", "Prefer not to say", "Other"],
                                  index=["", "Female", "Male", "Non-binary", "Prefer not to say", "Other"].index(profile.get("gender", "") if profile.get("gender", "") in ["", "Female", "Male", "Non-binary", "Prefer not to say", "Other"] else ""))
            location = st.text_input("Location (optional)", value=profile.get("location", ""), placeholder="City, country")
            interests = st.text_area("Interests", value=profile.get("interests", ""))
            skills = st.text_area("Current skills", value=profile.get("skills", ""))
            preferences = st.text_area(
                "How should LIFEWISE AI guide you?",
                value=profile.get(
                    "preferences",
                    "Explain step by step and use practical examples."
                )
            )
            uploaded_photo = st.file_uploader(
                "Profile photo (optional)", type=["jpg", "jpeg", "png"],
                help="Maximum 3 MB. You can change it later."
            )
            show_in_community = st.checkbox(
                "Make my profile visible to registered LIFEWISE members",
                value=bool(profile.get("community_visible", 0))
            )
            submitted = st.form_submit_button("Save profile and continue", type="primary")
        if submitted:
            if not name.strip() or not education.strip():
                st.error("Please enter your preferred name and education.")
            else:
                save_profile(user_id, name, education, interests, skills, preferences, age, gender, location)
                try:
                    if uploaded_photo is not None:
                        save_profile_photo(user_id, prepare_profile_photo(uploaded_photo))
                    save_community_visibility(user_id, show_in_community)
                except ValueError as error:
                    st.error(str(error))
                    return True
                st.success("Profile saved. Now set your first goal.")
                st.rerun()
        return True

    st.subheader("Step 2 of 2 · Set your first goal")
    st.write("What is the most important thing you want LIFEWISE AI to help you achieve?")
    with st.form("onboarding_goal"):
        title = st.text_input(
            "Your first goal",
            placeholder="Example: Become a professional data scientist"
        )
        area = st.selectbox(
            "Goal area",
            ["Career", "Study", "Business", "Personal development", "Other"]
        )
        submitted = st.form_submit_button("Save goal and enter LIFEWISE AI", type="primary")
    if submitted:
        if not title.strip():
            st.error("Please enter a goal.")
        else:
            add_goal(user_id, title, area)
            st.success("Your profile and first goal are ready!")
            st.rerun()
    return True


def show_sidebar(user_id=None, account_email=None, guest=False):
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)
        st.caption("Your Personal AI Counselor")
        st.divider()
        if guest:
            st.info("Guest mode · Chat is temporary")
            if st.button("Exit guest mode", use_container_width=True):
                st.session_state.pop("guest_mode", None)
                st.session_state.pop("guest_messages", None)
                st.rerun()
            st.caption("Create an account to save goals, profile and chat history.")
            return

        st.caption(f"Signed in: {account_email}")
        if st.button("Log out", use_container_width=True):
            st.session_state.pop("user", None)
            st.rerun()

        st.divider()
        profile = get_profile(user_id)
        st.subheader("Your profile")
        if profile.get("profile_photo"):
            st.image(profile["profile_photo"], width=120)
        with st.form("profile_form"):
            name = st.text_input("Preferred name", value=profile.get("name", ""))
            education = st.text_input("Education", value=profile.get("education", ""))
            age = st.number_input("Age (optional; enter 0 to leave blank)", min_value=0, max_value=120,
                                  value=int(profile.get("age") or 0), step=1, key="sidebar_profile_age")
            gender_options = ["", "Female", "Male", "Non-binary", "Prefer not to say", "Other"]
            saved_gender = profile.get("gender", "")
            gender = st.selectbox("Gender (optional)", gender_options,
                                  index=gender_options.index(saved_gender) if saved_gender in gender_options else 0,
                                  key="sidebar_profile_gender")
            location = st.text_input("Location (optional)", value=profile.get("location", ""),
                                     placeholder="City, country", key="sidebar_profile_location")
            interests = st.text_area("Interests", value=profile.get("interests", ""))
            skills = st.text_area("Skills", value=profile.get("skills", ""))
            preferences = st.text_area(
                "How should the AI guide you?",
                value=profile.get(
                    "preferences", "Explain step by step and use practical examples."
                )
            )
            uploaded_photo = st.file_uploader(
                "Change profile photo", type=["jpg", "jpeg", "png"],
                help="JPG or PNG, maximum 3 MB."
            )
            remove_photo = st.checkbox("Remove my current photo")
            show_in_community = st.checkbox(
                "Show my profile in Community",
                value=bool(profile.get("community_visible", 0)),
                help="When enabled, your name, photo, education, interests and optional age, gender and location can be seen by community members."
            )
            if st.form_submit_button("Save profile"):
                save_profile(user_id, name, education, interests, skills, preferences, age, gender, location)
                try:
                    if uploaded_photo is not None:
                        save_profile_photo(user_id, prepare_profile_photo(uploaded_photo))
                    elif remove_photo:
                        save_profile_photo(user_id, None)
                    save_community_visibility(user_id, show_in_community)
                except ValueError as error:
                    st.error(str(error))
                    return
                st.success("Profile saved.")
                st.rerun()

        st.divider()
        st.subheader("🧠 Your memories")
        with st.form("memory_form", clear_on_submit=True):
            memory_text = st.text_area(
                "What should LIFEWISE AI remember?",
                placeholder="Example: I am learning Python."
            )
            category = st.selectbox("Category", MEMORY_CATEGORIES)
            approved = st.checkbox("Allow AI to use this memory", value=True)
            if st.form_submit_button("Save memory"):
                if memory_text.strip():
                    add_memory(user_id, memory_text, category, approved)
                    st.success("Memory saved.")
                    st.rerun()
                else:
                    st.warning("Please enter a memory.")

        query = st.text_input("Search memories", placeholder="Search saved memories")
        category_filter = st.selectbox(
            "Filter memories", ["All"] + MEMORY_CATEGORIES
        )
        memories = list_memories(
            user_id, include_pending=True, category=category_filter,
            query=query, limit=100
        )
        for memory in memories:
            with st.expander(
                f"{memory['category']} · {'Approved' if memory['approved'] else 'Not approved'}"
            ):
                st.write(memory["content"])
                with st.form(f"edit_memory_{memory['id']}"):
                    edited = st.text_area("Edit memory", value=memory["content"])
                    cat = st.selectbox(
                        "Category", MEMORY_CATEGORIES,
                        index=MEMORY_CATEGORIES.index(
                            memory["category"] if memory["category"] in MEMORY_CATEGORIES else "General"
                        )
                    )
                    allow = st.checkbox("Approved for AI use", value=bool(memory["approved"]))
                    if st.form_submit_button("Update"):
                        if edited.strip():
                            update_memory(user_id, memory["id"], edited, cat, allow)
                            st.rerun()
                if st.button("Delete memory", key=f"delete_memory_{memory['id']}"):
                    delete_memory(user_id, memory["id"])
                    st.rerun()


def scroll_chat_to_latest():
    """Scroll the main Streamlit document to the newest message and composer."""
    st.html("""
    <script>
    (() => {
      const doc = window.parent.document;
      const run = () => {
        const chat = doc.querySelectorAll('[data-testid="stChatMessage"]');
        if (chat.length) chat[chat.length - 1].scrollIntoView({behavior: 'smooth', block: 'end'});
        const composer = doc.querySelector('[data-testid="stChatInput"]');
        if (composer) composer.scrollIntoView({behavior: 'smooth', block: 'end'});
      };
      requestAnimationFrame(() => requestAnimationFrame(run));
    })();
    </script>
    """)


def render_copy_button(content, key):
    """Show a compact copy control for an assistant response."""
    safe_content = json.dumps(str(content))
    st.html(f"""
    <div style="display:flex;justify-content:flex-end;margin-top:-.35rem;margin-bottom:.55rem">
      <button id="copy-{key}" type="button"
        style="border:1px solid #d8e4f3;background:#fff;color:#31547f;
        border-radius:9px;padding:5px 11px;font:600 12px 'DM Sans',sans-serif;cursor:pointer">
        Copy response
      </button>
      <span id="copy-status-{key}" style="font:12px sans-serif;color:#16804a;
        margin-left:8px;align-self:center"></span>
    </div>
    <script>
    const copyButton = document.getElementById("copy-{key}");
    const copyStatus = document.getElementById("copy-status-{key}");
    if (copyButton) {{
      copyButton.addEventListener("click", async () => {{
        const text = {safe_content};
        try {{
          await navigator.clipboard.writeText(text);
          copyStatus.textContent = "Copied";
          copyButton.textContent = "Copied";
        }} catch (error) {{
          copyStatus.textContent = "Clipboard unavailable in this browser";
        }}
      }});
    }}
    </script>
    """)


def render_chat(messages, guest=False, user_id=None):
    st.markdown("<div class='lw-section-title' style='font-size:1.45rem'>LIFEWISE AI Counselor</div>", unsafe_allow_html=True)
    st.caption("A supportive space to explore your career, education, goals, skills and personal growth.")
    st.caption("Your message box stays at the bottom. New replies appear at the latest point in the conversation.")
    top_left, top_right = st.columns([5, 1])
    with top_right:
        if st.button("＋ New chat", use_container_width=True):
            if guest:
                st.session_state["guest_messages"] = []
            else:
                clear_chat(user_id)
            st.rerun()

    if not messages:
        st.markdown("""
        <div class="lw-card" style="padding:1.4rem">
          <h3 style="color:#153d76;margin:.1rem 0 .5rem">👋 Hello! I'm LIFEWISE AI.</h3>
          <p style="margin:0 0 .5rem">What would you like help with today?</p>
          <small style="color:#64748b">Try asking about a career path, a study plan, learning a skill, or reaching a personal goal.</small>
        </div>
        """, unsafe_allow_html=True)

    for message_index, item in enumerate(messages):
        avatar = "🧭" if item["role"] == "assistant" else "🙂"
        with st.chat_message(item["role"], avatar=avatar):
            st.markdown(item["content"])
            created_at = item.get("created_at")
            if created_at:
                try:
                    stamp = datetime.fromisoformat(str(created_at)).strftime("%b %d · %I:%M %p")
                except (TypeError, ValueError):
                    stamp = str(created_at)
                st.caption(stamp)
            if item["role"] == "assistant":
                render_copy_button(item["content"], f"history_{message_index}")

    prompt = st.chat_input("Message LIFEWISE AI...")
    if prompt:
        if guest:
            history = list(st.session_state.get("guest_messages", []))
            st.session_state["guest_messages"].append({"role": "user", "content": prompt})
            profile, memories, goals = {}, [], []
        else:
            history = recent_messages(user_id, limit=12)
            save_message(user_id, "user", prompt)
            profile = get_profile(user_id)
            memories = get_approved_memories(user_id, limit=50)
            goals = list_goals(user_id)

        with st.chat_message("user", avatar="🙂"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="🧭"):
            with st.spinner("LIFEWISE AI is thinking..."):
                reply = get_counselor_reply(
                    prompt, profile=profile, memories=memories, goals=goals,
                    conversation_history=history
                )
                st.markdown(reply)
                render_copy_button(reply, "latest")

        if guest:
            st.session_state["guest_messages"].append({"role": "assistant", "content": reply})
        else:
            save_message(user_id, "assistant", reply)
        st.rerun()

    # Run after all history is rendered, including after the response-triggered rerun.
    scroll_chat_to_latest()


def show_goals(user_id):
    st.subheader("🎯 Your goals")
    with st.form("goal_form", clear_on_submit=True):
        title = st.text_input("Goal")
        area = st.selectbox(
            "Area", ["Career", "Study", "Business", "Personal development", "Other"]
        )
        submitted = st.form_submit_button("Add goal", type="primary")
    if submitted:
        if title.strip():
            add_goal(user_id, title, area)
            st.rerun()
        else:
            st.warning("Please enter a goal.")

    for goal in list_goals(user_id):
        cols = st.columns([4, 2, 2, 1])
        cols[0].write(f"**{goal['title']}**")
        cols[1].write(goal["area"])
        if goal["status"] == "Completed":
            cols[2].success("Completed")
        elif cols[2].button("Mark complete", key=f"complete_{goal['id']}"):
            update_goal_status(user_id, goal["id"], "Completed")
            st.rerun()
        if cols[3].button("Delete", key=f"delete_goal_{goal['id']}"):
            delete_goal(user_id, goal["id"])
            st.rerun()


def show_community(user_id):
    st.subheader("👥 LIFEWISE Community")
    st.caption("Meet members, share messages and files, and start private conversations. Only members who enable Community visibility can participate.")

    profile = get_profile(user_id)
    if not profile.get("community_visible"):
        st.warning("Your Community profile is currently hidden. Open Profile settings in the sidebar and enable Community visibility to join the group chat and appear in the member directory.")
    else:
        st.markdown("### 💬 Community group chat")
        st.caption("Messages here are visible to all opted-in community members. Do not share private or sensitive information.")
        st_autorefresh(interval=8000, limit=None, key="community_chat_refresh")

        # Conversation history stays above; chat controls are grouped at the bottom.
        posts = list_community_messages(limit=100, viewer_id=user_id)
        if not posts:
            st.info("No community messages yet. Start the conversation!")
        for post in posts:
            mine = int(post.get("sender_id", -1)) == int(user_id)
            avatar = post.get("profile_photo") or ("🙂" if mine else "👤")
            with st.chat_message("user" if mine else "assistant", avatar=avatar):
                name = "You" if mine else (post.get("sender_name") or "LIFEWISE member")
                st.markdown(f"**{name}**")
                if post.get("content"):
                    st.markdown(post["content"])
                if post.get("image"):
                    st.image(post["image"], use_container_width=True)
                show_message_attachment(post, f"community_{post['id']}")
                st.caption(post.get("created_at", ""))
                if mine and st.button("Delete my message", key=f"delete_community_{post['id']}"):
                    delete_own_community_message(user_id, post["id"])
                    st.rerun()

        with st.expander("📎 Attach a picture or document", expanded=False):
            image_col, file_col = st.columns(2)
            with image_col:
                post_image = st.file_uploader("Picture (optional)", type=["jpg", "jpeg", "png"], help="Maximum 3 MB.", key="community_image_v7")
            with file_col:
                post_file = st.file_uploader("Document or other file (optional)", type=ALLOWED_ATTACHMENT_TYPES, help="One file, maximum 10 MB.", key="community_attachment_v7")
            send_attachment_clicked = st.button("Send attachment", key="community_send_attachment_v7", type="primary")

        if send_attachment_clicked:
            try:
                image_bytes = prepare_profile_photo(post_image) if post_image is not None else None
                attachment = prepare_attachment(post_file)
                if image_bytes is None and attachment is None:
                    st.warning("Choose a picture or document first.")
                else:
                    send_community_message(user_id, "", image_bytes, attachment)
                    st.rerun()
            except ValueError as error:
                st.error(str(error))

        with st.form("community_message_composer_v73", clear_on_submit=True):
            post_text = st.text_input(
                "Write a message to the community…", max_chars=2000,
                placeholder="Write a message to the community…",
                label_visibility="collapsed", key="community_chat_input_v73"
            )
            send_col, clear_col = st.columns([3, 1])
            with send_col:
                send_post = st.form_submit_button("➤ Send message", type="primary", use_container_width=True)
            with clear_col:
                clear_chat = st.form_submit_button("🧹 Clear chat for me", use_container_width=True)

        if clear_chat:
            hide_community_messages_for_user(user_id)
            st.rerun()
        if send_post:
            if post_text and post_text.strip():
                send_community_message(user_id, post_text.strip(), None, None)
                st.rerun()
            else:
                st.warning("Write a message before sending.")
        st.caption("Clear chat for me only hides messages from your account. It does not remove them for other members.")
        scroll_chat_to_latest()

    st.divider()
    st.markdown("### 👤 Discover community members")
    search = st.text_input(
        "Find members", placeholder="Search by name, education, interests or location...",
        key="community_search"
    )
    members = list_public_users(search, exclude_user_id=user_id, limit=60)
    if not members:
        st.info("No other members found. Members appear here only after they enable profile visibility in their profile settings.")
    else:
        for start in range(0, len(members), 2):
            cols = st.columns(2, gap="large")
            for col, member in zip(cols, members[start:start + 2]):
                with col:
                    with st.container(border=True):
                        photo_col, details_col = st.columns([1, 3])
                        with photo_col:
                            if member.get("profile_photo"):
                                st.image(member["profile_photo"], width=92)
                            else:
                                st.markdown("<div style='font-size:3rem;text-align:center'>👤</div>", unsafe_allow_html=True)
                        with details_col:
                            st.markdown(f"**{display_name(member)}**")
                            if member.get("education"):
                                st.caption(member["education"])
                            member_details = [value for value in [
                                f"Age: {member['age']}" if member.get("age") else "",
                                member.get("gender", ""), member.get("location", "")
                            ] if value]
                            if member_details:
                                st.caption(" · ".join(member_details))
                            if member.get("interests"):
                                st.write(member["interests"][:180])
                        if st.button("Message privately", key=f"community_message_{member['id']}", type="primary", use_container_width=True):
                            st.session_state["selected_dm_user"] = int(member["id"])
                            st.info("Conversation selected. Open the Messages tab to chat.")


def show_messages(user_id):
    st.subheader("💬 Private messages")
    st.caption("Only you and the selected recipient can view this conversation.")
    st_autorefresh(interval=8000, limit=None, key="private_message_refresh")

    conversations = list_conversations(user_id, limit=100)
    conversation_map = {int(row["other_id"]): row for row in conversations}
    selected_from_community = st.session_state.get("selected_dm_user")
    if selected_from_community and int(selected_from_community) not in conversation_map:
        visible = list_public_users(exclude_user_id=user_id, limit=500)
        selected_member = next((m for m in visible if int(m["id"]) == int(selected_from_community)), None)
        if selected_member:
            conversation_map[int(selected_member["id"])] = {
                "other_id": int(selected_member["id"]), "name": selected_member.get("name"),
                "profile_photo": selected_member.get("profile_photo"),
                "content": "Start a new conversation", "created_at": "", "unread_count": 0
            }

    if not conversation_map:
        st.info("You do not have any messages yet. Visit Community and choose a member to start a conversation.")
        return

    ids = list(conversation_map.keys())
    default_index = ids.index(int(selected_from_community)) if selected_from_community and int(selected_from_community) in ids else 0
    selected_id = st.selectbox(
        "Choose a conversation", ids, index=default_index,
        format_func=lambda item_id: (
            f"{conversation_map[item_id].get('name') or 'LIFEWISE member'}"
            + (f" · {conversation_map[item_id].get('unread_count', 0)} new" if conversation_map[item_id].get('unread_count') else "")
        ),
        key="direct_message_conversation"
    )
    selected = conversation_map[int(selected_id)]
    title_col, refresh_col = st.columns([5, 1])
    with title_col:
        st.markdown(f"### {selected.get('name') or 'LIFEWISE member'}")
    with refresh_col:
        refresh_clicked = st.button("↻ Refresh", key="refresh_private_messages", use_container_width=True)

    # Force a fresh database read on every refresh click; no cached conversation data is used.
    if refresh_clicked:
        st.session_state["private_message_last_refresh"] = datetime.now().isoformat(timespec="seconds")
        st.toast("Conversation refreshed", icon="🔄")
    mark_direct_messages_read(user_id, selected_id)
    messages = get_direct_messages(user_id, selected_id, limit=100)
    my_profile = get_profile(user_id) or {}
    if not messages:
        st.info("This is the beginning of your conversation. Send a friendly message below.")
    for index, message in enumerate(messages):
        mine = int(message["sender_id"]) == int(user_id)
        message_avatar = my_profile.get("profile_photo") if mine else message.get("sender_photo")
        if not message_avatar:
            message_avatar = "🙂" if mine else "👤"
        with st.chat_message("user" if mine else "assistant", avatar=message_avatar):
            st.markdown(message["content"])
            try:
                stamp = datetime.fromisoformat(message["created_at"]).strftime("%b %d · %I:%M %p")
            except (TypeError, ValueError):
                stamp = message.get("created_at", "")
            st.caption(("You" if mine else (message.get("sender_name") or "Member")) + (f" · {stamp}" if stamp else ""))
            show_message_attachment(message, f"direct_{message['id']}")

    # Keep the newest message and composer in view after sending or auto-refresh.
    scroll_chat_to_latest()
    with st.form("private_message_form", clear_on_submit=True):
        message_text = st.text_input("Write a private message...", label_visibility="collapsed", placeholder="Write a private message...")
        message_file = st.file_uploader("Attach a file (optional)", type=ALLOWED_ATTACHMENT_TYPES, help="One file, maximum 10 MB.", key=f"dm_file_{selected_id}")
        send_clicked = st.form_submit_button("Send message", type="primary")
    if send_clicked:
        try:
            attachment = prepare_attachment(message_file)
            if not (message_text or "").strip() and attachment is None:
                st.warning("Write a message or attach a file.")
            else:
                send_direct_message(user_id, selected_id, message_text or "", attachment)
                st.rerun()
        except ValueError as error:
            st.error(str(error))


def show_profile_page(user_id):
    profile = get_profile(user_id)
    st.subheader("👤 Your profile")
    left, right = st.columns([1, 2])
    with left:
        if profile.get("profile_photo"):
            st.image(profile["profile_photo"], width=180)
        else:
            st.markdown("<div style='font-size:5rem'>👤</div>", unsafe_allow_html=True)
    with right:
        st.markdown(f"### {profile.get('name') or 'Your name'}")
        st.write("**Education:** " + (profile.get("education") or "Not added"))
        st.write("**Age:** " + (str(profile.get("age")) if profile.get("age") else "Not added"))
        st.write("**Gender:** " + (profile.get("gender") or "Not added"))
        st.write("**Location:** " + (profile.get("location") or "Not added"))
        st.write("**Interests:** " + (profile.get("interests") or "Not added"))
        st.write("**Skills:** " + (profile.get("skills") or "Not added"))
        st.caption("Use the profile editor in the left sidebar to update your details and photo.")
        st.info("Community visibility is optional. When enabled, your name, education, interests, photo and any age, gender or location you provide can be visible to community members. Your email, goals, memories and AI conversations remain private. Leave optional details blank if you do not want to share them.")
        st.write("**Community visibility:** " + ("On" if profile.get("community_visible") else "Off"))




def show_overview(user_id, email):
    profile = get_profile(user_id)
    goals = list_goals(user_id)
    memories = get_approved_memories(user_id, limit=200)
    unread = unread_direct_message_count(user_id)
    active = sum(1 for g in goals if str(g.get("status", "")).lower() not in ("completed", "done"))
    completed = len(goals) - active
    first_name = (profile.get("name") or "there").strip().split()[0]
    st.markdown(f'<div class="lw-hero"><h2>Welcome back, {first_name}.</h2><p>Your personal growth workspace. Choose one small step and make today count.</p></div>', unsafe_allow_html=True)
    st.markdown("### Your workspace")
    st.caption("A quick view of your progress and the tools available to you.")
    cols = st.columns(4)
    for col, (label, value) in zip(cols, [("Active goals", active), ("Completed goals", completed), ("Saved memories", len(memories)), ("Unread messages", unread)]):
        with col:
            st.markdown(f'<div class="lw-metric"><div class="lw-metric-label">{label}</div><div class="lw-metric-value">{value}</div></div>', unsafe_allow_html=True)
    st.write("")
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        st.markdown("### Your tools")
        st.markdown('<div class="lw-card"><b>💬 AI Counselor</b><br><span class="lw-subtle">Explore a question, career idea or learning plan.</span></div><div class="lw-card"><b>🎯 Goals</b><br><span class="lw-subtle">Turn an ambition into clear, manageable actions.</span></div><div class="lw-card"><b>👥 Community</b><br><span class="lw-subtle">Connect with opted-in members and join the conversation.</span></div>', unsafe_allow_html=True)
    with right:
        st.markdown("### Recent goals")
        if goals:
            for goal in goals[:5]:
                st.markdown(f'<div class="lw-card"><b>{goal.get("title", "Untitled goal")}</b><br><span class="lw-subtle">{goal.get("area", "General")} · {goal.get("status") or "In progress"}</span></div>', unsafe_allow_html=True)
        else:
            st.info("You haven't added a goal yet. Open Goals to create your first one.")
        st.caption(f"Signed in as {email}")


def show_registered_app(user):
    user_id = user["id"]
    email = user.get("email") or user["username"]
    if show_onboarding(user_id):
        return

    show_sidebar(user_id, email)
    show_brand()
    st.caption(f"Personal workspace · Signed in as {email}")
    pages = ["Overview", "AI Counselor", "Goals", "Community", "Messages", "Profile"]
    selected_page = st.radio("Main navigation", pages, horizontal=True,
                             label_visibility="collapsed", key="main_navigation")
    st.divider()
    if selected_page == "Overview":
        show_overview(user_id, email)
    elif selected_page == "AI Counselor":
        st.markdown("### AI Counselor")
        st.caption("Ask a question, explore an idea or work through your next step.")
        st.info("LIFEWISE AI is a guidance prototype, not a replacement for licensed medical, legal, financial or career professionals.")
        render_chat(recent_messages(user_id, limit=40), user_id=user_id)
    elif selected_page == "Goals":
        show_goals(user_id)
    elif selected_page == "Community":
        show_community(user_id)
    elif selected_page == "Messages":
        show_messages(user_id)
    elif selected_page == "Profile":
        show_profile_page(user_id)


def show_guest_app():
    show_sidebar(guest=True)
    show_brand()
    st.markdown('<div class="lw-hero"><h2>Your next step starts here.</h2><p>Ask freely and explore ideas with LIFEWISE AI.</p></div>', unsafe_allow_html=True)
    st.info(
        "You are using Guest Mode. Messages stay temporarily in this browser session "
        "and are not written to the LIFEWISE database."
    )
    render_chat(
        st.session_state.get("guest_messages", []),
        guest=True
    )


if "user" in st.session_state:
    show_registered_app(st.session_state["user"])
elif st.session_state.get("guest_mode"):
    show_guest_app()
else:
    show_authentication()
