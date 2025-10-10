"""
HCC Plan Guacamole Authentication Service (Simplified Docker Version)

Vereinfachte FastAPI-basierte Authentication für Apache Guacamole.
Nutzt direkte Database-Connection ohne komplexe project_paths-Logik.

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
from uuid import UUID

# Simplified Database Setup für Docker-Container
from pony.orm import Database, Required, Optional, Set, db_session, PrimaryKey
from pony.orm import select, commit
from enum import Enum
import bcrypt

# FastAPI Application
app = FastAPI(
    title="HCC Plan Guacamole Authentication Service",
    description="Multi-User Authentication für Apache Guacamole mit HCC Plan Integration (Docker)",
    version="1.0.0-docker",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Logging Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simplified Database Setup
db = Database()

# Minimale Role Enum (simplified)
class Role(Enum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"

# Correct Person Model (basierend auf echtem HCC Plan Schema)
class Person(db.Entity):
    _table_ = 'Person'  # Großbuchstabe P!
    id = PrimaryKey(str)  # UUID als Primary Key
    username = Required(str)
    password = Required(str)  # password_hash
    f_name = Required(str)  # Vorname
    l_name = Required(str)  # Nachname  
    role = Optional(str)  # Role als String - jetzt mit Pony Optional

# Database Connection - Fixed Path im Container
DOCKER_DB_PATH = "/root/.local/share/happy_code_company/hcc_plan/database/database.sqlite"

try:
    db.bind(provider='sqlite', filename=DOCKER_DB_PATH, create_db=False)
    db.generate_mapping()
    logger.info(f"Database connected successfully: {DOCKER_DB_PATH}")
except Exception as e:
    logger.error(f"Database connection failed: {e}")
    raise

# Password Verification
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using bcrypt"""
    try:
        password_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        return False

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
    """Health check endpoint für Docker"""
    try:
        with db_session:
            # Simple DB connectivity test
            person_count = select(p for p in Person).count()
            return {
                "status": "healthy",
                "database": "connected", 
                "persons_count": person_count,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )

# Main Authentication Endpoint
@app.post("/authenticate")
async def authenticate_user(auth: AuthRequest) -> Dict[str, Any]:
    """
    Hauptauthentication-Endpoint für Guacamole
    Erwartet username/password, returniert Guacamole-kompatible Connection-Liste
    """
    try:
        with db_session:
            # Find user by username
            person = select(p for p in Person if p.username == auth.username).first()
            
            if not person:
                logger.warning(f"Authentication failed: User not found: {auth.username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
            
            # Verify password
            if not verify_password(auth.password, person.password):
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
            # Für jetzt: Standard-Connection für alle User
            return {
                "available": [
                    f"hcc-plan-session-{auth.username}"
                ],
                "user_info": {
                    "username": auth.username,
                    "full_name": f"{person.f_name} {person.l_name}",
                    "role": person.role,
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

# Session Info Endpoint (für Debugging)
@app.get("/session/{username}")
async def get_session_info(username: str):
    """Get session information for a user"""
    try:
        with db_session:
            person = select(p for p in Person if p.username == username).first()
            
            if not person:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            return UserSession(
                username=person.username,
                role=person.role or "user",
                full_name=f"{person.f_name} {person.l_name}",
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
    """Debug endpoint - Liste aller User in der Database"""
    try:
        with db_session:
            users = select((p.username, p.f_name, p.l_name, p.role) for p in Person)[:]
            return {
                "total_users": len(users),
                "users": [
                    {
                        "username": user[0],
                        "name": f"{user[1]} {user[2]}",
                        "role": user[3]
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
