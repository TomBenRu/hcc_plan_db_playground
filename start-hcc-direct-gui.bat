@echo off
REM start-hcc-direct-gui.bat
REM HCC Plan Direct GUI - Production Starter
REM Startet die optimierte Direct GUI Container ohne Desktop-Environment

echo ===============================================
echo HCC Plan Direct GUI - Production Starter
echo ===============================================
echo.
echo DIRECT GUI: Optimierte HCC Plan GUI ohne Desktop
echo MEMORY: 55%% Reduktion gegenueber Desktop-Version
echo STARTUP: Deutlich schnellerer Start
echo.

REM Prüfe ob Docker läuft
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Docker ist nicht verfügbar!
    echo Bitte Docker Desktop starten und erneut versuchen.
    pause
    exit /b 1
)

echo Docker verfügbar ✓
echo.

REM Stoppe existierende DIRECT Container (für sauberen Neustart)
echo Stoppe existierende Container (falls vorhanden)...
docker-compose -f docker-compose-DIRECT.yml down --remove-orphans 2>nul
echo.

echo ===============================================
echo STARTE HCC PLAN DIRECT GUI CONTAINER...
echo ===============================================
echo.
echo Build und Start kann einige Minuten dauern...
echo Container werden erstellt und gestartet...
echo.

REM Starte DIRECT Container mit Build
docker-compose -f docker-compose-DIRECT.yml up --build -d

if %errorlevel% neq 0 (
    echo.
    echo ===============================================
    echo FEHLER: Container-Start fehlgeschlagen!
    echo ===============================================
    echo.
    echo DEBUG-INFORMATIONEN:
    docker-compose -f docker-compose-DIRECT.yml logs --tail=50
    echo.
    echo MÖGLICHE LÖSUNGEN:
    echo 1. Docker Desktop neu starten
    echo 2. Script erneut ausführen
    echo 3. Ports 8081, 5902, 6902 freigeben
    echo.
    pause
    exit /b 1
)

echo.
echo ===============================================
echo CONTAINER ERFOLGREICH GESTARTET!
echo ===============================================
echo.

REM Warte auf Container-Startup und Health-Checks
echo Warte auf Container-Initialisierung (45 Sekunden)...
echo HCC Plan GUI wird gestartet...
echo.

REM Countdown mit Progress-Anzeige
for /l %%i in (45,-5,5) do (
    echo Noch %%i Sekunden... Container starten...
    timeout /t 5 /nobreak >nul
)

echo.
echo ===============================================
echo CONTAINER STATUS:
echo ===============================================
docker-compose -f docker-compose-DIRECT.yml ps

echo.
echo ===============================================
echo HCC PLAN DIRECT GUI BEREIT!
echo ===============================================
echo.
echo ZUGANG:
echo URL:    http://localhost:8081/guacamole/
echo Login:  anna
echo Pass:   test123
echo.
echo VERBINDUNG:
echo "HCC Plan" \(direkte Verbindung\)
echo.
echo ERWARTUNG:
echo ✓ HCC Plan GUI startet automatisch
echo ✓ Keine Desktop-Umgebung sichtbar
echo ✓ Alle Dialoge funktionieren normal
echo ✓ Deutlich schnellerer Start
echo.

REM Auto-Browser-Start Abfrage
set /p BROWSER_START=Browser automatisch öffnen? (j/n): 
if /i "%BROWSER_START%"=="j" (
    echo.
    echo Browser wird geöffnet...
    start http://localhost:8081/guacamole/
    echo.
)

echo ===============================================
echo CONTAINER-VERWALTUNG:
echo ===============================================
echo.
echo CONTAINER STOPPEN:
echo docker-compose -f docker-compose-DIRECT.yml down
echo.
echo CONTAINER NEUSTARTEN:
echo docker-compose -f docker-compose-DIRECT.yml restart
echo.
echo LOGS ANZEIGEN:
echo docker-compose -f docker-compose-DIRECT.yml logs -f
echo.
echo STATUS PRÜFEN:
echo docker-compose -f docker-compose-DIRECT.yml ps
echo.

echo ===============================================
echo HCC PLAN DIRECT GUI ERFOLGREICH GESTARTET!
echo ===============================================
echo.
echo Container laufen im Hintergrund.
echo Browser: http://localhost:8081/guacamole/
echo Login: anna / test123
echo.

pause