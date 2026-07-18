from datetime import datetime, timedelta, timezone
from typing import Annotated, Dict, List, Optional
import hashlib
import secrets
import sqlite3
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import jwt
from google import genai
from google.genai import types

SECRET_KEY = "super-secret-agentic-ai-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI(title="Multi-Session Agentic Service", version="1.0.0", docs_url="/my-custom-docs")
client = genai.Client()

DB_FILE = "data_store/chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # ADDED: session_id column to separate chats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Native Hashing Configurations
def hash_password(password: str, salt: bytes = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 600000)
    return f"{salt.hex()}:{pwd_hash.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt_hex, hash_hex = hashed_password.split(":")
        salt = bytes.fromhex(salt_hex)
        return hash_password(plain_password, salt) == hashed_password
    except ValueError:
        return False

USER_DB: Dict[str, Dict] = {
    "Testuser01": {"username": "Testuser01", "password_hash": hash_password("Admin@1234"), "role": "user"},
    "admin": {"username": "admin", "password_hash": hash_password("secretpassword"), "role": "admin"}
}

def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> Dict:
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None or username not in USER_DB:
            raise credentials_exception
        return USER_DB[username]
    except jwt.PyJWTError:
        raise credentials_exception

def get_internal_system_status() -> str:
    return "Database: Connected | Active Connections: 42 | Memory Usage: 14% | API Gateway: Stable"

class ChatMessage(BaseModel):
    role: str
    content: str

class AgentRequest(BaseModel):
    user_prompt: str
    session_id: str  # Frontend passes which session this message belongs to


# --- ENDPOINTS ---

@app.post("/token")
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = USER_DB.get(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": user["username"], "exp": expire}
    return {"access_token": jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM), "token_type": "bearer"}

# NEW ENDPOINT: Get all unique sessions for a user with their first message snippet
@app.get("/sessions")
def get_user_sessions(current_user: Annotated[Dict, Depends(get_current_user)]):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Pulls the first user message of each session to act as the chat title
    cursor.execute("""
        SELECT session_id, content FROM messages 
        WHERE username = ? AND role = 'user'
        GROUP BY session_id 
        ORDER BY id DESC
    """, (current_user["username"],))
    rows = cursor.fetchall()
    conn.close()
    return [{"session_id": row[0], "title": row[1][:30]} for row in rows]

# UPDATED: Get history filtered by a specific session_id
@app.get("/history/{session_id}", response_model=List[ChatMessage])
def get_session_history(session_id: str, current_user: Annotated[Dict, Depends(get_current_user)]):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM messages WHERE username = ? AND session_id = ? ORDER BY id ASC", 
        (current_user["username"], session_id)
    )
    rows = cursor.fetchall()
    conn.close()
    return [ChatMessage(role=row[0], content=row[1]) for row in rows]

# UPDATED: Saves and reads context matching the specific session_id
@app.post("/agent")
def run_ai_agent(payload: AgentRequest, current_user: Annotated[Dict, Depends(get_current_user)]):
    try:
        username = current_user["username"]
        system_instruction = (
            f"You are a secure autonomous systems agent working for user: {username} "
            f"with role: {current_user['role']}. You have access to real-time functions."
        )
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM messages WHERE username = ? AND session_id = ? ORDER BY id ASC", 
            (username, payload.session_id)
        )
        past_rows = cursor.fetchall()
        
        contents = []
        for row in past_rows:
            api_role = "model" if row[0] == "assistant" else row[0]
            contents.append(types.Content(role=api_role, parts=[types.Part.from_text(text=row[1])]))
            
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=payload.user_prompt)]))
        
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[get_internal_system_status], 
            )
        )
        
        # Save to database along with the session identifier
        cursor.execute("INSERT INTO messages (username, session_id, role, content) VALUES (?, ?, ?, ?)", (username, payload.session_id, "user", payload.user_prompt))
        cursor.execute("INSERT INTO messages (username, session_id, role, content) VALUES (?, ?, ?, ?)", (username, payload.session_id, "assistant", response.text))
        conn.commit()
        conn.close()
        
        return {"agent_response": response.text}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Execution Failure: {str(e)}")
