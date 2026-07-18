import streamlit as st
import requests
import time

st.set_page_config(page_title="Agentic AI Hub", page_icon="🤖", layout="wide")
st.title("🤖 Secure Agentic AI System")

if "token" not in st.session_state:
    st.session_state.token = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_session" not in st.session_state:
    st.session_state.current_session = None
if "sessions_list" not in st.session_state:
    st.session_state.sessions_list = []

BACKEND_URL = "http://localhost:8000" 

# Helper function to load all chat threads from backend
def refresh_sessions_sidebar(headers):
    try:
        res = requests.get(f"{BACKEND_URL}/sessions", headers=headers)
        if res.status_code == 200:
            st.session_state.sessions_list = res.json()
    except Exception:
        pass

# --- 1. LOGIN & SIDEBAR ---
if not st.session_state.token:
    with st.sidebar.form("login_form"):
        st.subheader("System Authentication")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Log In")
        
        if login_btn:
            try:
                res = requests.post(f"{BACKEND_URL}/token", data={"username": username, "password": password})
                if res.status_code == 200:
                    st.session_state.token = res.json()["access_token"]
                    # Default initialization to a brand new session tracking ID string
                    st.session_state.current_session = f"session_{int(time.time())}"
                    st.session_state.messages = []
                    st.success(f"Logged in as {username}!")
                    st.rerun()
                else:
                    st.sidebar.error("Invalid credentials.")
            except Exception:
                st.sidebar.error("Cannot connect to FastAPI server.")
else:
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    st.sidebar.success("🔒 Authenticated Session Active")
    
    # ➕ NEW CHAT BUTTON BUTTON
    if st.sidebar.button("➕ New Chat", use_container_width=True):
        st.session_state.current_session = f"session_{int(time.time())}"
        st.session_state.messages = []
        st.rerun()

    st.sidebar.markdown("---")
    
    # Fetch lists of conversations from the backend SQLite DB
    refresh_sessions_sidebar(headers)
    
    st.sidebar.markdown("### 📜 Past Chats & Topics")
    if st.session_state.sessions_list:
        for sess in st.session_state.sessions_list:
            # Create a clickable toggle link button for every historical session
            button_label = f"💬 {sess['title']}..."
            # Highlight active conversation thread
            if st.session_state.current_session == sess['session_id']:
                button_label = f"➡️ {sess['title']}..."
                
            if st.sidebar.button(button_label, key=sess['session_id'], use_container_width=True):
                st.session_state.current_session = sess['session_id']
                # Fetch history specific to the selected link slot code
                hist_res = requests.get(f"{BACKEND_URL}/history/{sess['session_id']}", headers=headers)
                if hist_res.status_code == 200:
                    st.session_state.messages = hist_res.json()
                st.rerun()
    else:
        st.sidebar.caption("No historical sessions logged.")

    st.sidebar.markdown("---")
    if st.sidebar.button("Log Out", use_container_width=True):
        st.session_state.token = None
        st.session_state.messages = []
        st.session_state.current_session = None
        st.session_state.sessions_list = []
        st.rerun()

# --- 2. CHAT WORKSPACE CONTEXT ---
if st.session_state.token:
    # Display the filtered past items
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("Ask the system agent to do something..."):
        with st.chat_message("user"):
            st.write(prompt)
            
        st.session_state.messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {st.session_state.token}",
            "Content-Type": "application/json"
        }
        json_payload = {
            "user_prompt": prompt,
            "session_id": st.session_state.current_session # Passes active session state
        }
        
        try:
            with st.spinner("Agent running tools..."):
                res = requests.post(f"{BACKEND_URL}/agent", json=json_payload, headers=headers)
            
            if res.status_code == 200:
                agent_reply = res.json()["agent_response"]
                with st.chat_message("assistant"):
                    st.write(agent_reply)
                st.session_state.messages.append({"role": "assistant", "content": agent_reply})
                st.rerun()
            else:
                st.error(f"Error: {res.json().get('detail', 'Unknown error')}")
        except Exception as e:
            st.error(f"Failed to communicate with backend: {e}")
else:
    st.info("Please verify your credentials in the sidebar to interact with the autonomous system agent.")
