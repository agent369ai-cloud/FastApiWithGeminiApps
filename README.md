# Secure Agentic AI System with Multi-Session Memory

An production-grade enterprise setup featuring a high-performance **FastAPI backend** agent integrated with Google's **Gemini 3.5 Flash** model via the `google-genai` SDK, orchestrated alongside a reactive **Streamlit frontend chat dashboard**.

---

## 🚀 System Architecture & Key Features

* **Autonomous Tool Execution (Function Calling)**: The Gemini agent dynamically decides when to run native internal Python tools (e.g., `get_internal_system_status`) to fetch raw environment server metrics and format them into clear responses.
* **Persistent Multi-Topic Memory (ChatGPT Style)**: Replaces volatile, single-window session arrays with a file-based **SQLite** layout. Chat history is mapped using a `session_id`, allowing independent conversation threads that persist across browser reloads or multiple windows.
* **Native RBAC (Role-Based Access Control)**: Secure JSON Web Token (`pyjwt`) authentication built natively without external dependencies.
  * **`Testuser01`** (`Admin@1234`): Held under the `user` scope. Can chat with the agent and check general system status, but is blocked from admin views.
  * **`admin`** (`secretpassword`): Held under the `admin` scope with absolute system-wide access.
* **Orchestration**: Fully isolated networking layout containerized using a clean `docker-compose.yml` framework with dedicated storage disk volumes.

---

## 📂 Project Directory Structure

```text
FastApiWithGeminiApps/
├── data/                  # Host-mounted local folder (Created dynamically for SQLite)
│   └── chat_history.db    # Persistent SQLite database file
├── Dockerfile             # Multi-stage optimized build file for the FastAPI service
├── docker-compose.yml     # Multi-service runtime configuration specification
├── main.py                # Core FastAPI service implementing authentication, RBAC, & Gemini tools
├── app_frontend.py        # Streamlit web interface displaying threads & security portals
└── requirements.txt       # Frozen application dependencies
```

---

## 🛠️ Step-by-Step Installation & Deployment

### 1. Prerequisites
Ensure your hosting machine (`srvr1`) has **Docker Engine** and **Docker Compose Plugin** configured:
```bash
docker --version
docker compose version
```

### 2. Configure Environment Variables
The application infrastructure reads externalized API keys from the container execution profile. Ensure you generate a fresh, secure API target string via Google AI Studio.

### 3. Deploy the Full Stack
Execute the following compose command inside the root directory to build the images and run the full backend-frontend pipeline in detached background mode:
```bash
docker compose up -d --build
```

---

## 🎯 Verification & Endpoint Testing

Once the orchestration layer reports a stable execution profile, you can access the system elements across the network using your server's public IP address:

* **Interactive Streamlit Web UI**: `http://<YOUR_SERVER_PUBLIC_IP>:8501`
* **Interactive FastAPI Documentation UI**: `http://<YOUR_SERVER_PUBLIC_IP>:8000/my-custom-docs`

### Interactive Functional Testing Flow:
1. Navigate to the Streamlit UI (`:8501`) and authenticate in the sidebar utilizing **`Testuser01`** and **`Admin@1234`**.
2. Submit a unique topic context statement into the thread window: `"Remember that our primary production deployment region is Oregon US."`
3. Hit **`➕ New Chat`** at the top of the sidebar panel. Notice the main message pane transitions to a pristine topic slate instantly.
4. Input an operational request instruction: `"Can you check our backend database and connection health metrics right now?"`
5. Watch the agent evaluate your intent, pause, systematically call its internal `get_internal_system_status` python tool, and format a natural summary back onto the UI screen.
6. Click between the saved session headers listed under your **`📜 Past Chats & Topics`** pane to see history refresh dynamically from the SQLite layer.

---

## 🛑 Management & Maintenance Commands

```bash
# Monitor system health logs across all container processes
docker compose logs -f

# Verify real-time status of service ports 8000 and 8501
docker compose ps

# Gracefully tear down container containers without removing database storage logs
docker compose down
```
