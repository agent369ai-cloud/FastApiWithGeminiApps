from datetime import datetime, timedelta, timezone
from typing import Annotated, Dict, List, Optional  # Added List and Optional for history
import hashlib
import secrets
import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel  # 1. Added BaseModel for incoming JSON schemas
import jwt
from google import genai
from google.genai import types

# Security Configurations
SECRET_KEY = "super-secret-agentic-ai-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI(
    title="Agentic AI Secure Service",
    version="1.0.0",
    docs_url="/my-custom-docs",
    redoc_url="/my-second-dashboard"
)

# Initialize Gemini Client (Expects GEMINI_API_KEY env variable)
client = genai.Client()

# Helper Functions: Native Password Hashing
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

# Mock Database
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

# --- AGENT TOOLS (Functions the AI can choose to run) ---
def get_internal_system_status() -> str:
    """Retrieves real-time raw performance data and connection metrics from the server environment."""
    return "Database: Connected | Active Connections: 42 | Memory Usage: 14% | API Gateway: Stable"


# --- NEW: PYDANTIC SCHEMAS FOR CONVERSATION MEMORY ---
class ChatMessage(BaseModel):
    role: str      # Must be "user" or "assistant" from your Streamlit frontend
    content: str

class AgentRequest(BaseModel):
    user_prompt: str
    chat_history: Optional[List[ChatMessage]] = []


# --- ENDPOINTS ---

@app.post("/token")
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = USER_DB.get(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": user["username"], "exp": expire}
    return {"access_token": jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM), "token_type": "bearer"}

# MODIFIED: Changed from simple URL parameter to payload: AgentRequest JSON body
@app.post("/agent")
def run_ai_agent(payload: AgentRequest, current_user: Annotated[Dict, Depends(get_current_user)]):
    try:
        # Define the system blueprint instructions for the Agent
        system_instruction = (
            f"You are a secure autonomous systems agent working for user: {current_user['username']} "
            f"with role: {current_user['role']}. You have access to real-time functions. Use them if necessary."
        )
        
        # 2. Reconstruct the full chat logs array matching Google SDK structural schemas
        contents = []
        if payload.chat_history:
            for msg in payload.chat_history:
                # Convert Streamlit frontend "assistant" role identifier to Gemini SDK "model" expectation
                api_role = "model" if msg.role == "assistant" else msg.role
                contents.append(types.Content(
                    role=api_role,
                    parts=[types.Part.from_text(text=msg.content)]
                ))
        
        # Append the latest turn to the tail end of the array sequence
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=payload.user_prompt)]
        ))
        
        # Invoke the LLM passing the historical contents array instead of a single prompt string
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=contents, # Changed from user_prompt string to historical structural list
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[get_internal_system_status], 
            )
        )
        return {"agent_response": response.text}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Execution Failure: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "Public access allowed."}
