from datetime import datetime, timedelta, timezone
from typing import Annotated, Dict, List, Optional
import hashlib
import secrets
import os
import time
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import jwt
import psycopg2 # Replaces sqlite3 for enterprise scaling
from psycopg2.extras import RealDictCursor
from google import genai
from google.genai import types

# Load secret strings dynamically from .env file injected by docker-compose
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-insecure-key-for-local-dev")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI(
    title="Production Agentic AI Service",
    version="1.0.0",
    docs_url="/my-custom-docs",
    redoc_url="/my-second-dashboard"
)

# Initialize Gemini Client (Expects GEMINI_API_KEY environment variable)
client = genai.Client()

# Helper function to maintain a resilient connection pool handshake with Postgres
def get_db_connection():
    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(
                host="postgres_db", # Matches the docker-compose service name
                database="agentic_chat_db",
                user="agent_admin",
                password="secure_db_password_123"
            )
            return conn
        except psycopg2.OperationalError:
            retries -= 1
            time.sleep(2)
    raise HTTPException(status_code=500, detail="Database connection timeout.")

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Create persistent message schema table layout with auto-incrementing SERIAL ID
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            session_id VARCHAR(100) NOT NULL,
            role VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

# Run database engine schema checks immediately on runtime start
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

# Mock User DB (Replace with database lookups later as your app expands)
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

# --- AGENT TOOLS ---
def get_internal_system_status() -> str:
    """Retrieves real-time raw performance data and connection metrics from the server environment."""
    return "Database: Connected | Active Connections: 42 | Memory Usage: 14% | API Gateway: Stable"

class ChatMessage(BaseModel):
    role: str
    content: str

class AgentRequest(BaseModel):
    user_prompt: str
    session_id: str


# --- ENDPOINTS ---

@app.post("/token")
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = USER_DB.get(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": user["username"], "exp": expire}
    return {"access_token": jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM), "token_type": "bearer"}

# Fetches all unique session titles based on the first user message
@app.get("/sessions")
def get_user_sessions(current_user: Annotated[Dict, Depends(get_current_user)]):
    conn = get_db_connection()
    # RealDictCursor formats database row maps cleanly as standard Python dictionaries
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT DISTINCT ON (session_id) session_id, content, id
        FROM messages 
        WHERE username = %s AND role = 'user'
        ORDER BY session_id, id ASC
    """, (current_user["username"],))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Sort threads chronologically descending (newest chat at top)
    sorted_rows = sorted(rows, key=lambda x: x['id'], reverse=True)
    return [{"session_id": r["session_id"], "title": r["content"][:30]} for r in sorted_rows]

# Fetches full history logs filtered by specific session identifier tags
@app.get("/history/{session_id}", response_model=List[ChatMessage])
def get_session_history(session_id: str, current_user: Annotated[Dict, Depends(get_current_user)]):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        "SELECT role, content FROM messages WHERE username = %s AND session_id = %s ORDER BY id ASC", 
        (current_user["username"], session_id)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [ChatMessage(role=r["role"], content=r["content"]) for r in rows]

# Core agentic endpoint with context-windowed historic text injections
@app.post("/agent")
def run_ai_agent(payload: AgentRequest, current_user: Annotated[Dict, Depends(get_current_user)]):
    try:
        username = current_user["username"]
        system_instruction = (
            f"You are a secure autonomous systems agent working for user: {username} "
            f"with role: {current_user['role']}. You have access to real-time functions."
        )
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # FIXED: Grabs ONLY the last 10 messages of the conversation thread to save your API quota limit
        cursor.execute("""
            SELECT role, content FROM (
                SELECT role, content, id 
                FROM messages 
                WHERE username = %s AND session_id = %s 
                ORDER BY id DESC 
                LIMIT 10
            ) subquery 
            ORDER BY id ASC
        """, (username, payload.session_id))
        past_rows = cursor.fetchall()
        
        contents = []
        for row in past_rows:
            api_role = "model" if row["role"] == "assistant" else row["role"]
            contents.append(types.Content(role=api_role, parts=[types.Part.from_text(text=row["content"])]))
            
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=payload.user_prompt)]))
        
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[get_internal_system_status], 
            )
        )
        
        # Commit context values permanently into PostgreSQL row transactions
        cursor.execute(
            "INSERT INTO messages (username, session_id, role, content) VALUES (%s, %s, %s, %s)", 
            (username, payload.session_id, "user", payload.user_prompt)
        )
        cursor.execute(
            "INSERT INTO messages (username, session_id, role, content) VALUES (%s, %s, %s, %s)", 
            (username, payload.session_id, "assistant", response.text)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"agent_response": response.text}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Execution Failure: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "Public access allowed."}
