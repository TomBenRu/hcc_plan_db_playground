# auth-service/main.py
"""
HCC Plan Guacamole Authentication Service

FastAPI-basierter Authentication Service für Apache Guacamole Multi-User Setup.
Nutzt bestehende HCC Plan Person-Tabelle und Authentication für seamlose Integration.

Author: HCC Plan Development Team
Date: September 2025
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import sys
from uuid import UUID
from datetime import datetime, timedelta
import hashlib
import logging

# Add parent directory to path für HCC Plan imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import bestehender HCC Plan Code (keine Änderungen erforderlich!)
try:
    from database.models import Person as PersonModel
    from database.authentication import verify
    from database.enums import Role
    from database.database import db_session
except ImportError as e:
    logging.error(f"Failed to import HCC Plan database components: {e}")
    raise

# FastAPI Application
app = FastAPI(
    title="HCC Plan Guacamole Authentication Service",
    description="Multi-User Authentication für Apache Guacamole mit HCC Plan Integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Logging Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic Models
class AuthRequest(BaseModel):
    """Guacamole Authentication Request Model"""
    username: str
    password: str

class ConnectionParameters(BaseModel):
    """VNC Connection Parameters"""
    hostname: str
    port: str
    password: str
    color_depth: str = "24"
    cursor: str = "remote"
    swap_red_blue: str = "true"
    dest_width: str = "1920"
    dest_height: str = "1080"
    recording_path: Optional[str] = None
    recording_name: Optional[str] = None

class ConnectionConfig(BaseModel):
    """VNC Connection Configuration"""
    protocol: str = "vnc"
    parameters: ConnectionParameters

class AuthResponse(BaseModel):
    """Guacamole Authentication Response"""
    username: str
    expires: int  # Unix timestamp
    connections: Dict[str, ConnectionConfig]

# Utility Functions
def generate_session_password(user_id: UUID) -> str:
    """Generate secure VNC session password for user"""
    # Create deterministic but secure password based on user_id
    hash_input = f"hcc-vnc-{user_id}-session"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:12]

def calculate_vnc_port(user_id: UUID) -> int:
    """Calculate unique VNC port for user (5900-5999 range)"""
    base_port = 5900
    # Use hash of user_id to get consistent port assignment
    user_hash = hash(str(user_id)) % 100  # 0-99 range
    return base_port + user_hash

def get_session_expiry() -> int:
    """Get session expiry timestamp (4 hours from now)"""
    expiry_time = datetime.now() + timedelta(hours=4)
    return int(expiry_time.timestamp())

# Session Manager Import
try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'session-manager'))
    from session_manager import session_manager
    logger.info("Session Manager imported successfully")
except ImportError as e:
    logger.warning(f"Session Manager not available: {e}")
    session_manager = None

# API Endpoints
@app.post("/authenticate", response_model=AuthResponse)
async def authenticate_user(auth_request: AuthRequest):
    """
    Authentifiziert User gegen bestehende HCC Plan Person-Tabelle
    und generiert dynamische VNC-Connection-Config für Guacamole
    
    Args:
        auth_request: Username und Password vom Guacamole Login
        
    Returns:
        AuthResponse mit verfügbaren Connections für den User
        
    Raises:
        HTTPException: Bei Authentication-Fehlern
    """
    try:
        logger.info(f"Authentication attempt for user: {auth_request.username}")
        
        with db_session:
            # 1. Query bestehende HCC Plan Person-Tabelle
            person = PersonModel.select(
                lambda p: p.username == auth_request.username and not p.prep_delete
            ).first()
            
            if not person:
                logger.warning(f"User not found: {auth_request.username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
            
            # 2. Verify Password mit bestehender HCC Plan Authentication
            if not verify(auth_request.password, person.password):
                logger.warning(f"Invalid password for user: {auth_request.username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
            
            # 3. Optional: Role-based Access Control
            if person.role == Role.GUEST:
                logger.info(f"Guest user access denied: {auth_request.username}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Guest users are not allowed for remote access"
                )
            
            # 4. Create or Get User Session via Session Manager
            if session_manager:
                try:
                    user_session = session_manager.create_user_session(auth_request.username)
                    vnc_port = user_session.vnc_port
                    hostname = user_session.container_name
                    session_password = f"vnc-{person.id}"
                    
                    logger.info(f"Session created/retrieved for {auth_request.username}: "
                               f"Container {hostname}, VNC Port {vnc_port}")
                except Exception as e:
                    logger.error(f"Session creation failed for {auth_request.username}: {e}")
                    # Fallback to static configuration
                    vnc_port = calculate_vnc_port(person.id)
                    hostname = f"hcc-session-{person.id}"
                    session_password = generate_session_password(person.id)
            else:
                # Fallback wenn Session Manager nicht verfügbar
                vnc_port = calculate_vnc_port(person.id)
                hostname = f"hcc-session-{person.id}"
                session_password = generate_session_password(person.id)
            
            # 5. Generate VNC Connection Configuration
            connection_params = ConnectionParameters(
                hostname=hostname,
                port=str(vnc_port),
                password=session_password,
                recording_path=f"/recordings/{person.project.id}",
                recording_name=f"HCC-{person.username}-${{GUAC_DATE}}-${{GUAC_TIME}}"
            )
            
            vnc_config = ConnectionConfig(
                protocol="vnc",
                parameters=connection_params
            )
            
            # 6. Response für Guacamole mit verfügbaren Connections
            response = AuthResponse(
                username=person.username,
                expires=get_session_expiry(),
                connections={
                    f"HCC Plan - {person.project.name}": vnc_config
                }
            )
            
            logger.info(f"Authentication successful for user: {auth_request.username}, "
                       f"Project: {person.project.name}, Role: {person.role}")
            
            return response
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Authentication service error for {auth_request.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )

@app.get("/health")
async def health_check():
    """
    Health Check Endpoint für Docker/Monitoring
    
    Returns:
        Service status und basic information
    """
    try:
        # Test database connection
        with db_session:
            # Simple query to test DB connectivity
            user_count = PersonModel.select().count()
            
        return {
            "status": "healthy",
            "service": "hcc-guacamole-auth",
            "version": "1.0.0",
            "database_status": "connected",
            "active_users": user_count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy", 
                "service": "hcc-guacamole-auth",
                "error": "Database connection failed"
            }
        )

@app.get("/users/{username}/session-info")
async def get_user_session_info(username: str):
    """
    Get Session Information für einen User (für Monitoring/Debugging)
    
    Args:
        username: Username des Users
        
    Returns:
        Session-Informationen für den User
    """
    try:
        with db_session:
            person = PersonModel.select(
                lambda p: p.username == username and not p.prep_delete
            ).first()
            
            if not person:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            return {
                "username": person.username,
                "project": person.project.name,
                "role": person.role.value if person.role else None,
                "vnc_port": calculate_vnc_port(person.id),
                "session_hostname": f"hcc-session-{person.id}",
                "full_name": person.full_name
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session info for {username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving session information"
        )

@app.get("/")
async def root():
    """Root endpoint mit Service-Information"""
    return {
        "message": "HCC Plan Guacamole Authentication Service",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }

# Startup Event
@app.on_event("startup")
async def startup_event():
    """Startup initialization"""
    logger.info("HCC Plan Guacamole Authentication Service starting up...")
    logger.info(f"Service will authenticate against HCC Plan database")
    
# Shutdown Event  
@app.on_event("shutdown") 
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("HCC Plan Guacamole Authentication Service shutting down...")

@app.post("/sessions/{username}/start")
async def start_user_session(username: str):
    """
    Explicitly start session for user (für Testing/Manual Management)
    """
    if not session_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session Manager not available"
        )
    
    try:
        with db_session:
            person = PersonModel.select(
                lambda p: p.username == username and not p.prep_delete
            ).first()
            
            if not person:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
        
        session = session_manager.create_user_session(username)
        
        return {
            "message": f"Session started for {username}",
            "container_name": session.container_name,
            "vnc_port": session.vnc_port,
            "status": session.status
        }
        
    except Exception as e:
        logger.error(f"Error starting session for {username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start session: {str(e)}"
        )

@app.delete("/sessions/{username}")
async def cleanup_user_session(username: str):
    """
    Manual Session Cleanup
    """
    if not session_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session Manager not available"
        )
    
    success = session_manager.cleanup_user_session(username)
    
    if success:
        return {"message": f"Session cleaned up for {username}"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session found"
        )

@app.get("/sessions")
async def list_active_sessions():
    """
    List all active sessions (für Monitoring)
    """
    if not session_manager:
        return {"sessions": [], "message": "Session Manager not available"}
    
    sessions = session_manager.list_active_sessions()
    
    return {
        "active_sessions": len(sessions),
        "max_sessions": session_manager.max_sessions,
        "sessions": {
            username: {
                "container_name": session.container_name,
                "vnc_port": session.vnc_port,
                "status": session.status,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat()
            }
            for username, session in sessions.items()
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    # Configuration from environment
    host = os.getenv("AUTH_SERVICE_HOST", "0.0.0.0")
    port = int(os.getenv("AUTH_SERVICE_PORT", "8000"))
    
    logger.info(f"Starting HCC Plan Guacamole Auth Service on {host}:{port}")
    
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        log_level="info"
    )
