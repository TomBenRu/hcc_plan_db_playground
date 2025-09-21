@echo off
REM status-hcc-direct-gui.bat
REM HCC Plan Direct GUI - Status Checker
REM Zeigt den aktuellen Status aller Container und Services

echo ===============================================
echo HCC Plan Direct GUI - Status Check
echo ===============================================
echo.

REM Prüfe ob Docker läuft
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Docker ist nicht verfügbar!
    echo Bitte Docker Desktop starten.
    echo.
    pause
    exit /b 1
)

echo Docker verfügbar ✓
echo.

echo ===============================================
echo CONTAINER STATUS:
echo ===============================================
docker-compose -f docker-compose-DIRECT.yml ps

echo.
echo ===============================================
echo CONTAINER HEALTH:
echo ===============================================
docker ps --filter "name=hcc-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo ===============================================
echo NETWORK STATUS:
echo ===============================================
docker network ls | findstr guac-network-direct

echo.
echo ===============================================
echo RESOURCE USAGE:
echo ===============================================
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" hcc-guacd-direct-v2 hcc-guacamole-direct-v2 hcc-vnc-anna-direct-v2 2>nul

echo.
echo ===============================================
echo SERVICE-ZUGANG:
echo ===============================================
echo.
echo GUACAMOLE WEB-INTERFACE:
echo URL:    http://localhost:8081/guacamole/
echo Login:  anna / test123
echo.
echo VNC DIRECT ACCESS (optional):
echo Port:   localhost:5902
echo Pass:   vncpass123
echo.
echo CONTAINER-PORTS:
echo 8081 → Guacamole Web-Interface
echo 5902 → VNC-Server (HCC Plan GUI)  
echo 6902 → noVNC Web-Interface
echo.

REM Test ob Services erreichbar sind
echo ===============================================
echo CONNECTIVITY CHECK:
echo ===============================================
echo.

echo Teste Guacamole Web-Interface...
curl -s -o nul -w "HTTP Status: %%{http_code}\n" http://localhost:8081/guacamole/ --connect-timeout 5
if %errorlevel% neq 0 (
    echo WARNUNG: Guacamole Web-Interface nicht erreichbar!
) else (
    echo Guacamole Web-Interface ✓
)

echo.
echo ===============================================
echo LOGS (LETZTE 10 ZEILEN):
echo ===============================================
echo.
echo HCC PLAN CONTAINER:
docker-compose -f docker-compose-DIRECT.yml logs --tail=5 hcc-anna-direct 2>nul

echo.
echo GUACAMOLE:
docker-compose -f docker-compose-DIRECT.yml logs --tail=5 guacamole-direct 2>nul

echo.
echo ===============================================
echo STATUS CHECK COMPLETE
echo ===============================================
echo.
echo VERFÜGBARE SCRIPTS:
echo start-hcc-direct-gui.bat   → Container starten
echo stop-hcc-direct-gui.bat    → Container stoppen  
echo status-hcc-direct-gui.bat  → Dieser Status-Check
echo.

pause