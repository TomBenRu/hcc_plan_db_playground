"""
HCC Plan Guacamole Authentication Service (Direct SQLite Version)

Ultra-vereinfachte Version mit direkten SQLite-Queries statt Pony ORM Entity-Mapping.
Vermeidet komplexe Entity-Definitionen und Pony ORM Decompiler-Issues.

Author: HCC Plan Development Team  
Date: September 2025
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, List
import os
import hashlib
import logging
from datetime import datetime, timedelta
import sqlite3
from passlib.context import CryptContext

# FastAPI Application
app = FastAPI(
    title="HCC Plan Guacamole Authentication Service",
    description="Direct SQLite Authentication für Apache Guacamole (No Pony ORM)",
    version="1.0.0-direct-sqlite",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Logging Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database Path (Docker Volume Mount)
DOCKER_DB_PATH = "/app/database/db_docker_test.sqlite"

# Password Context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except:
        return False

def get_db_connection():
    """Get SQLite database connection"""
    if not os.path.exists(DOCKER_DB_PATH):
        raise Exception(f"Database file not found: {DOCKER_DB_PATH}")
    return sqlite3.connect(DOCKER_DB_PATH)

# Pydantic Models
class AuthRequest(BaseModel):
    """Guacamole Authentication Request"""
    username: str
    password: str

class AuthResponse(BaseModel):
    """Guacamole Authentication Response"""
    available: List[str]
    
class UserSession(BaseModel):
    """User Session Info"""
    username: str
    role: str
    full_name: str
    session_id: str

# Health Check Endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint mit direkten SQLite-Queries"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Test 1: Check if Person table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Person';")
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            conn.close()
            return {
                "status": "unhealthy",
                "error": "Person table not found",
                "timestamp": datetime.now().isoformat()
            }
        
        # Test 2: Count persons
        cursor.execute("SELECT COUNT(*) FROM Person;")
        person_count = cursor.fetchone()[0]
        
        # Test 3: Check table structure
        cursor.execute("PRAGMA table_info(Person);")
        columns = [row[1] for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "persons_count": person_count,
            "columns_found": columns,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Main Authentication Endpoint
@app.post("/authenticate")
async def authenticate_user(auth: AuthRequest) -> Dict[str, Any]:
    """
    Direct SQLite Authentication für Guacamole
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find user by username
        cursor.execute(
            "SELECT id, username, password, f_name, l_name, role FROM Person WHERE username = ?",
            (auth.username,)
        )
        user_row = cursor.fetchone()
        conn.close()
        
        if not user_row:
            logger.warning(f"Authentication failed: User not found: {auth.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        user_id, username, password_hash, f_name, l_name, role = user_row
        
        # Verify password
        if not verify_password(auth.password, password_hash):
            logger.warning(f"Authentication failed: Invalid password for user: {auth.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid credentials"
            )
        
        # Erfolgreiche Authentication
        logger.info(f"Authentication successful for user: {auth.username}")
        
        # Generate session identifier
        session_id = hashlib.md5(f"{auth.username}_{datetime.now().isoformat()}".encode()).hexdigest()
        
        # Return Guacamole-kompatible Connection-Liste
        return {
            "available": [
                f"hcc-plan-session-{auth.username}"
            ],
            "user_info": {
                "username": auth.username,
                "full_name": f"{f_name} {l_name}",
                "role": role or "user",
                "session_id": session_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )

# Session Info Endpoint
@app.get("/session/{username}")
async def get_session_info(username: str):
    """Get session information for a user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, username, f_name, l_name, role FROM Person WHERE username = ?",
            (username,)
        )
        user_row = cursor.fetchone()
        conn.close()
        
        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id, username, f_name, l_name, role = user_row
        
        return UserSession(
            username=username,
            role=role or "user",
            full_name=f"{f_name} {l_name}",
            session_id=f"session-{username}-{datetime.now().strftime('%Y%m%d')}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session service error"
        )

# Debug Endpoint - Liste alle User
@app.get("/debug/users")
async def list_all_users():
    """Debug endpoint mit direkten SQLite-Queries"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT username, f_name, l_name, role FROM Person LIMIT 50;")
        users = cursor.fetchall()
        conn.close()
        
        return {
            "total_users": len(users),
            "users": [
                {
                    "username": user[0],
                    "name": f"{user[1]} {user[2]}",
                    "role": user[3] or "user"
                }
                for user in users
            ]
        }
        
    except Exception as e:
        logger.error(f"Debug users error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Debug service error"
        )

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
