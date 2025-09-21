#!/bin/bash
# docker/start-session.sh
# HCC Plan VNC Session Startup Script
# Initialisiert X11 Display, VNC Server und HCC Plan Application für Multi-User

set -e

echo "=== HCC Plan Multi-User Session Startup ==="
echo "User ID: ${HCC_USER_ID}"
echo "Project ID: ${HCC_PROJECT_ID}"
echo "Display: ${DISPLAY}"
echo "VNC Port: ${VNC_PORT}"

# Cleanup existing X11 locks (falls vorhanden)
rm -rf /tmp/.X*-lock /tmp/.X11-unix/X*

# Set VNC Password basierend auf Environment Variable
if [ -n "${VNC_PASSWORD}" ]; then
    echo "Setting VNC password from environment..."
    mkdir -p /root/.vnc
    echo "${VNC_PASSWORD}" | vncpasswd -f > /root/.vnc/passwd
    chmod 600 /root/.vnc/passwd
    echo "VNC password configured."
fi

# Validate required Environment Variables
if [ -z "${HCC_PROJECT_ID}" ]; then
    echo "ERROR: HCC_PROJECT_ID environment variable not set"
    exit 1
fi

if [ -z "${HCC_USER_ID}" ]; then
    echo "ERROR: HCC_USER_ID environment variable not set"  
    exit 1
fi

if [ -z "${DATABASE_URL}" ]; then
    echo "ERROR: DATABASE_URL environment variable not set"
    exit 1
fi

# Create X11 socket directory
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

# Create log directories
mkdir -p /var/log/supervisor
mkdir -p /recordings/${HCC_PROJECT_ID}

# Set Display number from DISPLAY environment variable (:1, :2, etc.)
DISPLAY_NUM=$(echo "${DISPLAY}" | sed 's/://')
export DISPLAY_NUM

echo "Starting X11 and VNC services..."
echo "Display Number: ${DISPLAY_NUM}"

# Test Database Connection before starting GUI
echo "Testing database connection..."
python -c "
import os
import sys
sys.path.insert(0, '/app')
from database.database import db_session
from database.models import Person
try:
    with db_session:
        count = Person.select().count()
        print(f'Database connection OK. Found {count} persons.')
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "Database connection failed, exiting."
    exit 1
fi

echo "Database connection successful. Starting GUI services..."

# Start Supervisor to manage all processes
echo "Starting Supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf