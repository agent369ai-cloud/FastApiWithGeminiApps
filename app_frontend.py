import streamlit as st
import requests

st.set_page_config(page_title="Agentic AI Hub", page_icon="🤖")
st.title("🤖 Secure Agentic AI System")

# Initialize session state for user token and chat logs
if "token" not in st.session_state:
    st.session_state.token = None
if "messages" not in st.session_state:
    st.session_state.messages = []

BACKEND_URL = "http://localhost:8000" # Replace with server IP if remote

# --- 1. LOGIN SIDEBAR ---
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
                    st.success(f"Logged in as {username}!")
                    st.rerun()
                else:
                    st.sidebar.error("Invalid credentials.")
            except Exception:
                st.sidebar.error("Cannot connect to FastAPI server.")
else:
    st.sidebar.success("🔒 Authenticated Session Active")
    if st.sidebar.button("Log Out"):
        st.session_state.token = None
        st.session_state.messages = []
        st.rerun()

# --- 2. AGENTIC CHAT INTERFACE ---
if st.session_state.token:
    # Display previous messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Accept new user prompt
    if prompt := st.chat_input("Ask the system agent to do something..."):
        with st.chat_message("user"):
            st.write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Submit to your FastAPI /agent endpoint
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        try:
            with st.spinner("Agent is thinking and processing tools..."):
                res = requests.post(f"{BACKEND_URL}/agent", params={"user_prompt": prompt}, headers=headers)
            
            if res.status_code == 200:
                agent_reply = res.json()["agent_response"]
                with st.chat_message("assistant"):
                    st.write(agent_reply)
                st.session_state.messages.append({"role": "assistant", "content": agent_reply})
            else:
                st.error(f"Error: {res.json().get('detail', 'Unknown error')}")
        except Exception as e:
            st.error(f"Failed to communicate with backend: {e}")
else:
    st.info("Please verify your credentials in the sidebar to interact with the autonomous system agent.")
