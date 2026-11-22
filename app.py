import html
import json
import mimetypes
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

import streamlit as st
st.markdown("""
<style>
header {visibility: hidden !important;}
[data-testid="stToolbar"] {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
[data-testid="stStatusWidget"] {display: none !important;}
</style>
""", unsafe_allow_html=True)
from dotenv import load_dotenv

from db import (
    init_db, register_user, authenticate_user,
    get_profile, save_profile, save_profile_photo, save_community_visibility,
    list_public_users, send_direct_message, get_direct_messages,
    list_conversations, mark_direct_messages_read, unread_direct_message_count,
    send_community_message, list_community_messages,
    delete_own_community_message, hide_community_messages_for_user, hide_direct_messages_for_user,
    add_goal, list_goals, update_goal_status, delete_goal,
    add_goal_actions, list_goal_actions, update_goal_action_status,
    add_custom_goal_action, delete_goal_action,
    save_goal_coach_message, list_goal_coach_messages, clear_goal_coach_messages,
    save_goal_checkin, list_goal_checkins, add_goal_problem, list_goal_problems,
    update_goal_problem_status, add_goal_evidence, list_goal_evidence,
    get_goal_evidence_file, reschedule_pending_goal_actions,
    add_memory, list_memories, get_approved_memories,
    update_memory, delete_memory,
    save_message, recent_messages, clear_chat
)
from counselor import get_counselor_reply
from action_engine import build_action_plan, build_smart_action_plan, detect_goal_type, calculate_progress
import pandas as pd
from streamlit_autorefresh import st_autorefresh

load_dotenv()
init_db()

st.set_page_config(
    page_title="LIFEWISE AI | Personal Growth & Goal Planner",
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
    # Normalize both POSIX and Windows separators; uploaded names are untrusted.
    name = str(uploaded_file.name or "upload").replace("\\", "/").split("/")[-1].strip()
    name = name or "upload"
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
        width, height = image.size
        if width < 1 or height < 1 or width * height > 20_000_000:
            raise ValueError("Image dimensions are too large.")
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

# Standalone stylesheet: one source of truth for desktop and mobile styling.
STYLE_PATH = APP_DIR / "style.css"
if not STYLE_PATH.is_file():
    raise FileNotFoundError("style.css is required and must be placed beside app.py.")
st.markdown(
    "<style>\n" + STYLE_PATH.read_text(encoding="utf-8") + "\n</style>",
    unsafe_allow_html=True,
)


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
    # Escape HTML-sensitive characters as well as JSON quotes so AI text cannot
    # terminate the inline script element when rendered by the browser.
    safe_content = (json.dumps(str(content))
                    .replace("<", "\\u003c")
                    .replace(">", "\\u003e")
                    .replace("&", "\\u0026")
                    .replace("\u2028", "\\u2028")
                    .replace("\u2029", "\\u2029"))
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

    if not guest:
        st.divider()
        logout_col, _ = st.columns([1, 4])
        with logout_col:
            if st.button("Log out", key="counselor_bottom_logout", use_container_width=True):
                for session_key in ("user", "selected_dm_user", "direct_message_conversation"):
                    st.session_state.pop(session_key, None)
                st.rerun()


def render_goal_analytics(goal, actions, progress):
    """Visual summaries are calculated from this goal's saved action records."""
    st.markdown("#### 📊 Your progress at a glance")
    status_df = pd.DataFrame({
        "Action status": ["Completed", "In progress", "Pending"],
        "Actions": [progress["completed"], progress["in_progress"], progress["pending"]],
    }).set_index("Action status")
    left, right = st.columns(2)
    with left:
        st.markdown("**Action status**")
        st.bar_chart(status_df, height=230)
    with right:
        st.markdown("**Progress by phase**")
        phase_rows = []
        for phase in dict.fromkeys(a["phase"] for a in actions):
            items = [a for a in actions if a["phase"] == phase]
            phase_rows.append({
                "Phase": phase.split("·", 1)[-1].strip(),
                "Completed": sum(a["status"] == "Completed" for a in items),
                "Remaining": sum(a["status"] != "Completed" for a in items),
            })
        if phase_rows:
            st.bar_chart(pd.DataFrame(phase_rows).set_index("Phase"), height=230)
        else:
            st.info("Your phase chart will appear when actions are added.")

    completed_dates = []
    for action in actions:
        stamp = action.get("completed_at")
        if action.get("status") == "Completed" and stamp:
            try:
                completed_dates.append(datetime.fromisoformat(stamp).date())
            except (TypeError, ValueError):
                pass
    if completed_dates:
        daily = {}
        for day in sorted(completed_dates):
            daily[day.isoformat()] = daily.get(day.isoformat(), 0) + 1
        cumulative = 0
        trend_rows = []
        for day, count in sorted(daily.items()):
            cumulative += count
            trend_rows.append({"Date": day, "Completed actions": cumulative})
        st.markdown("**Completion trend**")
        st.line_chart(pd.DataFrame(trend_rows).set_index("Date"), height=190)
    else:
        st.caption("Your completion trend will appear after you complete actions.")

    target = goal.get("target_date")
    if target:
        try:
            days_left = (datetime.fromisoformat(target).date() - datetime.now().date()).days
            if days_left < 0:
                st.warning(f"Your target date passed {abs(days_left)} day(s) ago. You can update your plan or target date.")
            elif days_left == 0:
                st.info("Your target date is today. Focus on the most important unfinished action.")
            else:
                st.caption(f"📅 {days_left} days until your target date")
        except ValueError:
            pass


def show_goal_coach(user_id, goal, actions, progress):
    st.markdown("#### 💬 Your personal Goal Coach")
    st.caption("This private coach uses the selected goal and its saved action plan to help you choose practical next steps.")
    messages = list_goal_coach_messages(user_id, goal["id"], limit=30)
    if not messages:
        st.info("Try: ‘What should I do today?’ or ‘Help me break my next action into smaller steps.’")
    for index, message in enumerate(messages):
        with st.chat_message(message["role"], avatar="🙂" if message["role"] == "user" else "🧭"):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask about this goal, your next action or your progress…", key=f"goal_coach_input_{goal['id']}")
    if prompt:
        save_goal_coach_message(user_id, goal["id"], "user", prompt)
        with st.spinner("Your Goal Coach is thinking…"):
            try:
                profile = get_profile(user_id)
                goal_context = {
                    "title": goal.get("title"), "area": goal.get("area"),
                    "target_date": goal.get("target_date"),
                    "weekly_hours": goal.get("weekly_hours"),
                    "starting_point": goal.get("starting_point"),
                    "success_measure": goal.get("success_measure"),
                    "plan_mode": goal.get("plan_mode"),
                    "assessment_context": goal.get("assessment_context"),
                    "status": goal.get("status"),
                    "progress": progress,
                    "actions": [{"title": a["title"], "phase": a["phase"],
                                 "description": a["description"], "due_date": a.get("due_date"),
                                 "status": a["status"]} for a in actions],
                }
                history = list_goal_coach_messages(user_id, goal["id"], limit=12)
                reply = get_counselor_reply(
                    prompt,
                    profile=profile,
                    memories=[],
                    goals=[goal_context],
                    conversation_history=history[:-1],
                    goal_coach=True,
                )
                save_goal_coach_message(user_id, goal["id"], "assistant", reply)
            except Exception as error:
                st.error("I couldn't process that message. Please try again.")
                return
        st.rerun()

    if messages:
        if st.button("Clear this goal's chat", key=f"clear_goal_chat_{goal['id']}"):
            clear_goal_coach_messages(user_id, goal["id"])
            st.rerun()


def show_goals(user_id):
    st.subheader("🎯 Goal-to-Action workspace")
    st.caption("Turn an ambition into a plan, see your progress visually, and get help from a coach dedicated to each goal.")
    with st.expander("＋ Create a goal and action plan", expanded=not bool(list_goals(user_id))):
        with st.form("goal_form_v15", clear_on_submit=True):
            plan_mode = st.radio("How would you like to plan?", ["AI Smart Plan", "Manual Plan"], horizontal=True,
                                 help="AI Smart Plan assesses the goal and creates goal-specific milestones. Manual Plan gives you a blank workspace to build yourself.")
            title = st.text_input("What do you want to achieve?", placeholder="Example: Become a doctor")
            area = st.selectbox("Goal area", ["Career", "Study", "Business", "Personal development", "Health and fitness", "Other"])
            detected = detect_goal_type(title, area)
            default_years = 7 if detected == "medical_career" else 2 if detected in ("data_science", "software_career", "business") else 1
            if plan_mode == "AI Smart Plan":
                st.info("The counselor will identify the type and complexity of your goal, use your starting situation, and create staged milestones. You can review and edit every action.")
                country = st.text_input("Country or education system", placeholder="Example: Pakistan")
                education = st.text_input("Current education or qualification", placeholder="Example: Matric, FSc pre-medical, bachelor's degree")
                current_situation = st.text_area("Tell the counselor about your current situation", placeholder="What have you completed? What are you doing now? Any constraints or important details?", height=90)
            else:
                country, education, current_situation = "", "", ""
                st.caption("Manual mode does not generate tasks automatically. Create your own stages and actions after saving the goal.")
            suggested_date = datetime.now().date() + __import__("datetime").timedelta(days=round(default_years * 365.25) if plan_mode == "AI Smart Plan" else 90)
            target_date = st.date_input("Target date / planning horizon", value=suggested_date, min_value=datetime.now().date())
            weekly_hours = st.slider("Time you can give each week", 1, 40, 5)
            starting_point = st.selectbox("Your current starting point", ["Beginner", "Some experience", "Intermediate", "Advanced"])
            success_measure = st.text_input("How will you know you succeeded?", placeholder="Example: Meet official medical admission and licensing requirements")
            submitted = st.form_submit_button("Create my goal workspace", type="primary", use_container_width=True)
        if submitted:
            if not title.strip():
                st.error("Please enter a goal.")
            elif plan_mode == "AI Smart Plan" and detected == "medical_career" and not country.strip():
                st.error("Please enter the country where you plan to study or practise so the roadmap can account for the correct medical pathway.")
            else:
                try:
                    generated = []
                    if plan_mode == "AI Smart Plan":
                        roadmap = build_smart_action_plan(
                            title, area, target_date, weekly_hours, starting_point,
                            success_measure, country, education, current_situation
                        )
                        generated = roadmap["actions"]
                        plan_note = roadmap["planning_note"]
                        goal_type = roadmap["goal_type"]
                        assessment_context = "Country: " + country + "\nEducation: " + education + "\nCurrent situation: " + current_situation + "\nGoal type: " + goal_type
                    else:
                        plan_note = "Manual plan: add your own stages and actions in the Action plan tab."
                        assessment_context = ""
                    goal_id = add_goal(
                        user_id, title, area, target_date.isoformat(), weekly_hours,
                        starting_point, success_measure, plan_mode, assessment_context
                    )
                    if generated:
                        add_goal_actions(user_id, goal_id, generated)
                        st.success(f"Your goal roadmap has been saved with {len(generated)} goal-specific actions. {plan_note}")
                    else:
                        st.success("Your manual goal workspace has been created. Open Action plan to add your own stages and actions.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

    goals = list_goals(user_id)
    if not goals:
        st.info("Your workspace is ready. Create your first goal above to generate an action plan.")
        return

    active_goals = [g for g in goals if g.get("status") != "Completed"]
    if active_goals:
        st.markdown("#### Your active goals")
        st.caption("Choose a goal to open its charts, action plan and private Goal Coach.")

    for goal in goals:
        actions = list_goal_actions(user_id, goal["id"])
        progress = calculate_progress(actions)
        with st.container(border=True):
            head_left, head_right = st.columns([4, 1])
            with head_left:
                st.markdown(f"### {goal['title']}")
                target_label = goal.get("target_date") or "No target date"
                st.caption(f"{goal['area']} · Target: {target_label} · {goal.get('weekly_hours', 5)} hrs/week · {goal.get('starting_point', 'Beginner')} · {goal.get('plan_mode', 'Manual')}")
            with head_right:
                if goal["status"] == "Completed":
                    st.success("Goal complete")
                elif st.button("Complete goal", key=f"goal_done_{goal['id']}"):
                    update_goal_status(user_id, goal["id"], "Completed")
                    st.rerun()
            st.progress(progress["percent"] / 100, text=f"{progress['percent']}% complete · {progress['completed']}/{progress['total']} actions")
            metric_cols = st.columns(4)
            for col, label, value in zip(metric_cols, ["Completed", "In progress", "Pending", "Total"], [progress["completed"], progress["in_progress"], progress["pending"], progress["total"]]):
                col.metric(label, value)
            if goal.get("success_measure"):
                st.caption("Success measure: " + goal["success_measure"])

            view_key = f"goal_workspace_view_v20_{goal['id']}"
            workspace_view = st.selectbox(
                "Choose your workspace",
                ["📊 Dashboard", "🗂️ Action plan", "💬 Goal Coach", "🧩 Problem Solver", "📅 Check-ins", "🏆 Evidence"],
                key=view_key, label_visibility="collapsed"
            )
            next_action = next((a for a in actions if a.get("status") != "Completed"), None)
            if next_action and goal.get("status") != "Completed":
                st.markdown(
                    '<div class="lw-goal-next"><div class="lw-goal-next-title">✨ Your next best step</div>'
                    + '<div style="font-weight:700;color:#1d2b3f">' + html.escape(next_action["title"]) + '</div>'
                    + '<div style="color:#52657e;font-size:.88rem;margin:.25rem 0">' + html.escape(next_action.get("description", "")) + '</div>'
                    + '<div style="color:#315fce;font-size:.82rem;font-weight:650">' + html.escape(next_action.get("phase", "")) + ' · Due ' + html.escape(next_action.get("due_date") or "Not set") + '</div></div>',
                    unsafe_allow_html=True
                )
                # Show a one-time confirmation after the action status is saved.
                action_flash = st.session_state.pop("goal_action_flash", None)
                if action_flash:
                    st.success(action_flash)

                if next_action.get("status") == "Pending":
                    if st.button(
                        "▶ Start this action",
                        key=f"start_next_{next_action['id']}",
                        type="primary",
                        use_container_width=True,
                    ):
                        saved = update_goal_action_status(user_id, next_action["id"], "In Progress")
                        refreshed = list_goal_actions(user_id, goal["id"])
                        confirmed = any(
                            item.get("id") == next_action["id"] and item.get("status") == "In Progress"
                            for item in refreshed
                        )
                        if saved and confirmed:
                            st.session_state["goal_action_flash"] = "Action started. Your progress has been updated."
                            st.rerun()
                        st.error("We couldn't update this action. Please refresh and try again.")
                elif next_action.get("status") == "In Progress":
                    if st.button(
                        "✓ Mark this action complete",
                        key=f"complete_next_{next_action['id']}",
                        type="primary",
                        use_container_width=True,
                    ):
                        saved = update_goal_action_status(user_id, next_action["id"], "Completed")
                        refreshed = list_goal_actions(user_id, goal["id"])
                        confirmed = any(
                            item.get("id") == next_action["id"] and item.get("status") == "Completed"
                            for item in refreshed
                        )
                        if saved and confirmed:
                            st.session_state["goal_action_flash"] = "Action completed. Your progress has been updated."
                            st.rerun()
                        st.error("We couldn't update this action. Please refresh and try again.")
            if workspace_view == "📊 Dashboard":
                render_goal_analytics(goal, actions, progress)
                st.markdown("#### ⚡ Today's action focus")
                today_actions = [a for a in actions if a.get("status") != "Completed"][:3]
                if today_actions:
                    st.caption("Start with these manageable actions. The list is based on your saved plan and due-date order.")
                    for daily_action in today_actions:
                        due_text = daily_action.get("due_date") or "No due date"
                        st.markdown(f"**{daily_action['title']}** · {daily_action['status']} · Due {due_text}")
                        d1, d2 = st.columns(2)
                        if daily_action["status"] == "Pending" and d1.button("▶ Start", key=f"daily_start_{daily_action['id']}", use_container_width=True):
                            update_goal_action_status(user_id, daily_action["id"], "In Progress")
                            st.rerun()
                        if daily_action["status"] == "In Progress" and d1.button("✓ Complete", key=f"daily_done_{daily_action['id']}", use_container_width=True):
                            update_goal_action_status(user_id, daily_action["id"], "Completed")
                            st.rerun()
                else:
                    st.success("All actions in this plan are complete. Add a new milestone if you want to continue.")
                overdue = [a for a in actions if a.get("status") != "Completed" and a.get("due_date") and a["due_date"] < datetime.now().date().isoformat()]
                if overdue:
                    st.warning(f"{len(overdue)} unfinished action(s) are overdue. Review the Action plan and use the adaptive schedule tool if your timeline has changed.")
            elif workspace_view == "🗂️ Action plan":
                if actions:
                    phases = list(dict.fromkeys(x["phase"] for x in actions))
                    for phase in phases:
                        phase_actions = [x for x in actions if x["phase"] == phase]
                        with st.expander(f"{phase} · {sum(x['status'] == 'Completed' for x in phase_actions)}/{len(phase_actions)} done"):
                            for action in phase_actions:
                                with st.container(border=True):
                                    c1, c2 = st.columns([3, 2])
                                    with c1:
                                        st.markdown(f"**{action['title']}**")
                                        st.caption(action["description"])
                                        st.caption("📅 Due: " + (action.get("due_date") or "Not set"))
                                    with c2:
                                        status_options = ["Pending", "In Progress", "Completed"]
                                        current = action["status"] if action["status"] in status_options else "Pending"
                                        new_status = st.selectbox("Action status", status_options, index=status_options.index(current), key=f"action_status_{action['id']}")
                                        if new_status != current:
                                            update_goal_action_status(user_id, action["id"], new_status)
                                            st.rerun()
                                        if st.button("Delete action", key=f"action_delete_{action['id']}", use_container_width=True):
                                            delete_goal_action(user_id, action["id"])
                                            st.rerun()
                else:
                    st.warning("This goal has no actions yet. Add your own actions, or create a new AI Smart Plan for a goal-specific roadmap.")
                    if st.button("Generate a 12-action starter plan", key=f"generate_existing_{goal['id']}", type="primary"):
                        from datetime import date, timedelta
                        deadline = date.fromisoformat(goal["target_date"]) if goal.get("target_date") else date.today() + timedelta(days=90)
                        generated = build_action_plan(goal["title"], goal["area"], deadline, goal.get("weekly_hours", 5), goal.get("starting_point", "Beginner"), goal.get("success_measure", ""))
                        add_goal_actions(user_id, goal["id"], generated)
                        st.rerun()
                if actions:
                    with st.expander("🔄 Adapt my roadmap schedule"):
                        st.caption("Reschedule unfinished actions in their existing order. Completed actions and their history are not changed.")
                        revised_end_default = datetime.fromisoformat(goal["target_date"]).date() if goal.get("target_date") else datetime.now().date() + __import__("datetime").timedelta(days=90)
                        revised_end = st.date_input("New realistic planning end date", value=max(revised_end_default, datetime.now().date()), min_value=datetime.now().date(), key=f"adaptive_end_{goal['id']}")
                        if st.button("Rebuild unfinished schedule", key=f"adaptive_apply_{goal['id']}", type="primary"):
                            try:
                                changed = reschedule_pending_goal_actions(user_id, goal["id"], datetime.now().date().isoformat(), revised_end.isoformat())
                                st.success(f"Updated due dates for {changed} unfinished action(s). Completed work was preserved.")
                                st.rerun()
                            except ValueError as error:
                                st.error(str(error))
                with st.expander("＋ Add my own action"):
                    with st.form(f"custom_action_{goal['id']}", clear_on_submit=True):
                        custom_phase = st.text_input("Stage / milestone", value="My actions", key=f"custom_phase_{goal['id']}")
                        custom_title = st.text_input("Action title", key=f"custom_title_{goal['id']}")
                        custom_description = st.text_input("What will you do?", key=f"custom_desc_{goal['id']}")
                        custom_due = st.date_input("Due date", value=datetime.now().date() + __import__("datetime").timedelta(days=7), key=f"custom_due_{goal['id']}")
                        custom_submit = st.form_submit_button("Save action")
                    if custom_submit:
                        try:
                            add_custom_goal_action(user_id, goal["id"], custom_title, custom_description, custom_due.isoformat(), custom_phase)
                            st.rerun()
                        except ValueError as error:
                            st.error(str(error))
            elif workspace_view == "🧩 Problem Solver":
                st.markdown("#### 🧩 Turn a blocker into a practical recovery plan")
                st.caption("Describe what is stopping you. LIFEWISE analyses the selected goal and saved actions, then helps you choose a corrective task.")
                with st.form(f"problem_form_{goal['id']}"):
                    problem_text = st.text_area("What problem are you facing?", placeholder="Example: I keep missing my study targets because I do not understand statistics.", height=110)
                    problem_impact = st.text_input("How is it affecting your goal?", placeholder="Example: I am two weeks behind my study plan.")
                    problem_submit = st.form_submit_button("Analyse problem and suggest solutions", type="primary", use_container_width=True)
                if problem_submit:
                    if not problem_text.strip():
                        st.error("Please describe the problem so LIFEWISE can help.")
                    else:
                        with st.spinner("LIFEWISE is analysing your obstacle and current plan…"):
                            problem_context = {
                                "title": goal.get("title"), "target_date": goal.get("target_date"),
                                "weekly_hours": goal.get("weekly_hours"), "starting_point": goal.get("starting_point"),
                                "progress": progress,
                                "actions": [{"title": a["title"], "status": a["status"], "due_date": a.get("due_date"), "phase": a.get("phase")} for a in actions]
                            }
                            problem_prompt = ("Act as LIFEWISE's practical problem-solving coach. Analyse this obstacle against the goal and action data. Give: (1) likely root causes, clearly marked as hypotheses, (2) 2-4 realistic solutions, (3) one recommended next action that can be done within 1-3 days, (4) how to measure whether it worked. Do not claim to change saved tasks. Problem: " + problem_text + "\nImpact: " + problem_impact)
                            solution = get_counselor_reply(problem_prompt, profile=get_profile(user_id), goals=[problem_context], goal_coach=True)
                            add_goal_problem(user_id, goal["id"], problem_text, problem_impact, solution)
                            st.session_state[f"latest_problem_solution_{goal['id']}"] = solution
                latest_solution = st.session_state.get(f"latest_problem_solution_{goal['id']}")
                if latest_solution:
                    st.markdown("##### Suggested recovery plan")
                    st.markdown(latest_solution)
                    with st.expander("＋ Convert the recommended step into a saved action", expanded=True):
                        with st.form(f"problem_action_{goal['id']}"):
                            recovery_title = st.text_input("Action title", placeholder="Example: Complete 10 introductory statistics exercises")
                            recovery_description = st.text_area("What exactly will you do?", placeholder="Write a small, measurable task.")
                            recovery_due = st.date_input("Due date", value=datetime.now().date() + __import__("datetime").timedelta(days=2), min_value=datetime.now().date())
                            recovery_submit = st.form_submit_button("Add recovery action to my plan", type="primary")
                        if recovery_submit:
                            try:
                                add_custom_goal_action(user_id, goal["id"], recovery_title, recovery_description, recovery_due.isoformat(), "Recovery actions")
                                st.success("Recovery action added to your saved plan.")
                                st.rerun()
                            except ValueError as error:
                                st.error(str(error))
                problems = list_goal_problems(user_id, goal["id"])
                if problems:
                    st.markdown("##### Previous problems")
                    for item in problems[:8]:
                        with st.container(border=True):
                            st.markdown(f"**{item['problem']}**")
                            st.caption(f"{item['created_at']} · {item['status']}")
                            if item.get("solution"):
                                with st.expander("View suggested solution"):
                                    st.markdown(item["solution"])
                            status = st.selectbox("Problem status", ["Open", "In progress", "Resolved"], index=["Open", "In progress", "Resolved"].index(item["status"]), key=f"problem_status_{item['id']}")
                            if status != item["status"]:
                                update_goal_problem_status(user_id, item["id"], status)
                                st.rerun()
            elif workspace_view == "📅 Check-ins":
                st.markdown("#### 📅 Daily and weekly progress check-in")
                st.caption("Record what happened, identify blockers and choose the next focus. Your check-ins are saved privately to your account.")
                with st.form(f"checkin_form_{goal['id']}"):
                    checkin_day = st.date_input("Check-in date", value=datetime.now().date(), key=f"checkin_day_{goal['id']}")
                    completed_today = st.number_input("How many actions did you complete today?", min_value=0, max_value=100, value=0, step=1)
                    energy = st.slider("How was your energy / focus?", 1, 5, 3, key=f"checkin_energy_{goal['id']}")
                    reflection = st.text_area("What went well today?", key=f"checkin_reflection_{goal['id']}")
                    blocker = st.text_area("What blocked your progress?", key=f"checkin_blocker_{goal['id']}")
                    next_focus = st.text_input("What is your next focus?", key=f"checkin_focus_{goal['id']}")
                    checkin_submit = st.form_submit_button("Save my check-in", type="primary", use_container_width=True)
                if checkin_submit:
                    save_goal_checkin(user_id, goal["id"], checkin_day.isoformat(), completed_today, energy, reflection, blocker, next_focus)
                    st.success("Your check-in has been saved.")
                    st.rerun()
                checkins = list_goal_checkins(user_id, goal["id"])
                if checkins:
                    from datetime import timedelta
                    week_start = (datetime.now().date() - timedelta(days=6)).isoformat()
                    week_entries = [entry for entry in checkins if entry.get("checkin_date", "") >= week_start]
                    week_completed = sum(int(entry.get("completed_count") or 0) for entry in week_entries)
                    week_energy = round(sum(int(entry.get("energy") or 0) for entry in week_entries) / len(week_entries), 1) if week_entries else 0
                    week_blockers = sum(1 for entry in week_entries if (entry.get("blocker") or "").strip())
                    st.markdown("##### Your last 7 days")
                    summary_cols = st.columns(3)
                    summary_cols[0].metric("Check-ins", len(week_entries))
                    summary_cols[1].metric("Actions reported", week_completed)
                    summary_cols[2].metric("Average focus", f"{week_energy}/5" if week_entries else "—")
                    if week_blockers:
                        st.info(f"You recorded {week_blockers} blocker(s) this week. Use Problem Solver to turn a blocker into a recovery action.")
                    st.markdown("##### Recent check-ins")
                    st.metric("Check-ins recorded", len(checkins))
                    for entry in checkins[:7]:
                        with st.container(border=True):
                            st.markdown(f"**{entry['checkin_date']}** · {entry['completed_count']} completed · Focus {entry['energy']}/5")
                            if entry.get("reflection"):
                                st.write("Went well: " + entry["reflection"])
                            if entry.get("blocker"):
                                st.warning("Blocker: " + entry["blocker"])
                            if entry.get("next_focus"):
                                st.caption("Next focus: " + entry["next_focus"])
                else:
                    st.info("Your first check-in will create the start of your personal progress history.")
            elif workspace_view == "🏆 Evidence":
                st.markdown("#### 🏆 Evidence and achievements")
                st.caption("Save proof of completed work, such as a project, certificate, assignment or portfolio item. Avoid uploading highly sensitive documents.")
                with st.form(f"evidence_form_{goal['id']}"):
                    evidence_title = st.text_input("Achievement / evidence title", placeholder="Example: Completed Python data analysis project")
                    evidence_description = st.text_area("What does this demonstrate?")
                    action_choices = {f"No linked action": None}
                    action_choices.update({f"{a['title']} ({a['status']}) · #{a['id']}": a["id"] for a in actions})
                    selected_evidence_action = st.selectbox("Link to an action (optional)", list(action_choices.keys()))
                    evidence_file = st.file_uploader("Attach evidence (optional, max 5 MB)", type=["pdf", "png", "jpg", "jpeg", "txt", "docx", "csv", "zip"], key=f"evidence_upload_{goal['id']}")
                    evidence_submit = st.form_submit_button("Save achievement", type="primary", use_container_width=True)
                if evidence_submit:
                    try:
                        file_data = evidence_file.getvalue() if evidence_file else None
                        if file_data and len(file_data) > 5 * 1024 * 1024:
                            raise ValueError("Evidence files must be 5 MB or smaller.")
                        add_goal_evidence(user_id, goal["id"], evidence_title, evidence_description,
                                          action_choices[selected_evidence_action],
                                          evidence_file.name if evidence_file else None,
                                          evidence_file.type if evidence_file else None, file_data)
                        st.success("Achievement saved to your evidence tracker.")
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
                evidence_items = list_goal_evidence(user_id, goal["id"])
                if evidence_items:
                    st.markdown("##### Saved achievements")
                    for item in evidence_items:
                        with st.container(border=True):
                            st.markdown(f"**🏅 {item['title']}**")
                            if item.get("description"):
                                st.write(item["description"])
                            st.caption(f"{item['created_at']} · {item.get('action_title') or 'Not linked to an action'}")
                            if item.get("file_name"):
                                file_record = get_goal_evidence_file(user_id, item["id"])
                                if file_record and file_record.get("file_data"):
                                    st.download_button("Download " + item["file_name"], file_record["file_data"], file_name=item["file_name"], mime=file_record.get("mime_type") or "application/octet-stream", key=f"evidence_download_{item['id']}")
                else:
                    st.info("No evidence saved yet. Add your first achievement above.")
            elif workspace_view == "💬 Goal Coach":
                show_goal_coach(user_id, goal, actions, progress)

            footer_cols = st.columns([1, 1, 3])
            if goal["status"] != "Completed" and footer_cols[0].button("Mark goal active", key=f"goal_active_{goal['id']}"):
                update_goal_status(user_id, goal["id"], "Active")
                st.rerun()
            if footer_cols[1].button("Delete goal", key=f"delete_goal_{goal['id']}"):
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

    st.divider()
    st.caption("Clear this private conversation from your own account. The other person will still see their copy.")
    if st.button("🧹 Clear chat for me", key=f"clear_private_chat_{user_id}_{selected_id}", use_container_width=True):
        hidden_count = hide_direct_messages_for_user(user_id, selected_id)
        st.success(f"Conversation cleared from your view ({hidden_count} message(s)).")
        st.rerun()


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
    first_name = html.escape((profile.get("name") or "there").strip().split()[0])
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
                goal_title = html.escape(str(goal.get("title", "Untitled goal")))
                goal_area = html.escape(str(goal.get("area", "General")))
                goal_status = html.escape(str(goal.get("status") or "In progress"))
                st.markdown(f'<div class="lw-card"><b>{goal_title}</b><br><span class="lw-subtle">{goal_area} · {goal_status}</span></div>', unsafe_allow_html=True)
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
        st.markdown(
            """
            <div class="lw-disclaimer" role="note">
              <span class="lw-disclaimer-title">Important note</span>
              <span>LIFEWISE AI is a guidance prototype, not a replacement for licensed medical, legal, financial or career professionals.</span>
            </div>
            """,
            unsafe_allow_html=True
        )
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
