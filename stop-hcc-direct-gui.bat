@echo off
REM stop-hcc-direct-gui.bat
REM HCC Plan Direct GUI - Container Stopper
REM Stoppt alle Direct GUI Container sauber

echo ===============================================
echo HCC Plan Direct GUI - Container Stopper
echo ===============================================
echo.

REM Prüfe ob Docker läuft
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNUNG: Docker ist nicht verfügbar!
    echo Container können möglicherweise nicht gestoppt werden.
    echo.
    pause
    exit /b 1
)

echo Docker verfügbar ✓
echo.

echo ===============================================
echo STOPPE HCC PLAN DIRECT GUI CONTAINER...
echo ===============================================
echo.

REM Zeige aktuellen Status
echo AKTUELLER STATUS:
docker-compose -f docker-compose-DIRECT.yml ps

echo.
echo Stoppe Container...

REM Stoppe alle DIRECT Container
docker-compose -f docker-compose-DIRECT.yml down

if %errorlevel% neq 0 (
    echo.
    echo WARNUNG: Beim Stoppen sind Fehler aufgetreten.
    echo Versuche manuelles Cleanup...
    echo.
    
    REM Manual cleanup falls nötig
    docker stop hcc-guacd-direct-v2 hcc-guacamole-direct-v2 hcc-vnc-anna-direct-v2 2>nul
    docker rm hcc-guacd-direct-v2 hcc-guacamole-direct-v2 hcc-vnc-anna-direct-v2 2>nul
    
    echo Manual cleanup durchgeführt.
) else (
    echo.
    echo ===============================================
    echo CONTAINER ERFOLGREICH GESTOPPT!
    echo ===============================================
)

echo.
echo FINALER STATUS:
docker-compose -f docker-compose-DIRECT.yml ps

echo.
echo ===============================================
echo HCC PLAN DIRECT GUI GESTOPPT
echo ===============================================
echo.
echo Container sind heruntergefahren.
echo Ressourcen wurden freigegeben.
echo.
echo ZUM NEUSTARTEN:
echo start-hcc-direct-gui.bat
echo.

pause