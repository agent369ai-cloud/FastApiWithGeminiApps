import streamlit as st
import requests

st.set_page_config(page_title="Agentic AI Hub", page_icon="🤖")
st.title("🤖 Secure Agentic AI System")

# Initialize session state for user token and chat logs
if "token" not in st.session_state:
    st.session_state.token = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# NOTE: If your FastAPI backend runs on a remote server, replace 'localhost' with your server's IP address.
BACKEND_URL = "http://localhost:8000" 

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
    # 2a. Display existing message history on screen refresh
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # 2b. Accept new inputs from the user
    if prompt := st.chat_input("Ask the system agent to do something..."):
        # Instantly render the new user message to the UI layout
        with st.chat_message("user"):
            st.write(prompt)
            
        # Format the historical chat array payload matching our Pydantic schema requirements
        formatted_history = []
        for msg in st.session_state.messages:
            formatted_history.append({
                "role": msg["role"],
                "content": msg["content"]
            })
            
        # Commit the new prompt token to your running local memory session cache
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Set up authorization headers and JSON payload requirements
        headers = {
            "Authorization": f"Bearer {st.session_state.token}",
            "Content-Type": "application/json"
        }
        json_payload = {
            "user_prompt": prompt,
            "chat_history": formatted_history
        }
        
        # Submit payload via network call to your FastAPI /agent endpoint
        try:
            with st.spinner("Agent is tracking context and processing tools..."):
                res = requests.post(f"{BACKEND_URL}/agent", json=json_payload, headers=headers)
            
            if res.status_code == 200:
                agent_reply = res.json()["agent_response"]
                # Render the final agent tool/thought output response block
                with st.chat_message("assistant"):
                    st.write(agent_reply)
                # Commit the response token text block back into history array cache
                st.session_state.messages.append({"role": "assistant", "content": agent_reply})
            else:
                error_detail = res.json().get('detail', 'Unknown error')
                st.error(f"Backend Server Rejection Error: {error_detail}")
        except Exception as e:
            st.error(f"Failed to communicate with backend service: {e}")
else:
    st.info("Please verify your credentials in the sidebar to interact with the autonomous system agent.")
