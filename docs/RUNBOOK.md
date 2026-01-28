# HCC Plan - Operations Runbook

Dieses Runbook enthält Deployment-Prozeduren, Monitoring und Troubleshooting für HCC Plan.

**Letzte Aktualisierung:** 2026-01-24
**Generiert aus:** docker-compose-DIRECT.yml, .env.example, Projektstruktur

---

## Inhaltsverzeichnis

1. [Deployment-Prozeduren](#deployment-prozeduren)
2. [Container-Management](#container-management)
3. [Monitoring & Health-Checks](#monitoring--health-checks)
4. [Häufige Probleme & Lösungen](#häufige-probleme--lösungen)
5. [Rollback-Prozeduren](#rollback-prozeduren)
6. [Backup & Recovery](#backup--recovery)

---

## Deployment-Prozeduren

### 1. Erstmalige Installation

#### Voraussetzungen prüfen

```bash
# Docker-Version prüfen
docker version

# Docker-Compose prüfen
docker-compose version

# Ports-Verfügbarkeit prüfen
netstat -an | grep -E "8080|8081|5901|5902"
```

#### Environment konfigurieren

```bash
# 1. Environment-Datei erstellen
cp .env.example .env

# 2. Sicheres Passwort setzen
# Editiere .env und ändere POSTGRES_PASSWORD

# 3. Guacamole Secret-Key generieren
openssl rand -hex 32
# Füge den generierten Key in .env als GUACAMOLE_SECRET_KEY ein
```

#### Container starten

**Option A: Direct GUI (Empfohlen)**
```bash
# Windows
start-hcc-direct-gui.bat

# Linux/Mac
docker-compose -f docker-compose-DIRECT.yml up --build -d
```

**Option B: Multi-User Setup**
```bash
# Windows
start-hcc-dynamic-multi-user.bat

# Linux/Mac
docker-compose -f docker-compose-DYNAMIC.yml up --build -d
```

### 2. Update-Deployment

```bash
# 1. Aktuelle Container stoppen
docker-compose -f docker-compose-DIRECT.yml down

# 2. Neue Version pullen
git pull origin master

# 3. Container neu bauen und starten
docker-compose -f docker-compose-DIRECT.yml up --build -d

# 4. Health-Check durchführen
docker-compose -f docker-compose-DIRECT.yml ps
```

---

## Container-Management

### Container-Übersicht

| Container | Image | Port | Funktion |
|-----------|-------|------|----------|
| `hcc-guacd-direct-v2` | guacamole/guacd | - | Guacamole Daemon |
| `hcc-guacamole-direct-v2` | guacamole/guacamole | 8081 | Web-Interface |
| `hcc-vnc-anna-direct-v2` | Custom (Dockerfile-minimal) | 5902, 6902 | HCC Plan GUI |

### Container-Operationen

```bash
# Status aller Container
docker-compose -f docker-compose-DIRECT.yml ps

# Container-Logs (alle)
docker-compose -f docker-compose-DIRECT.yml logs -f

# Logs einzelner Container
docker logs -f hcc-vnc-anna-direct-v2
docker logs -f hcc-guacamole-direct-v2
docker logs -f hcc-guacd-direct-v2

# Container neustarten
docker-compose -f docker-compose-DIRECT.yml restart

# Einzelnen Container neustarten
docker restart hcc-vnc-anna-direct-v2

# Container stoppen (Daten bleiben erhalten)
docker-compose -f docker-compose-DIRECT.yml stop

# Container komplett entfernen
docker-compose -f docker-compose-DIRECT.yml down

# Container + Volumes entfernen (VORSICHT: Datenverlust!)
docker-compose -f docker-compose-DIRECT.yml down -v
```

### Resource-Management

```bash
# Container-Ressourcenverbrauch
docker stats hcc-vnc-anna-direct-v2 hcc-guacamole-direct-v2

# Erwartete Werte (Direct GUI):
# - Memory: ~155MB (statt 350MB bei Desktop-Version)
# - CPU: Minimal bei Idle

# Disk-Usage
docker system df
```

---

## Monitoring & Health-Checks

### Automatische Health-Checks

Der HCC Plan VNC-Container hat integrierte Health-Checks:

```yaml
healthcheck:
  test: ["CMD-SHELL", "pgrep -f 'python.*main.py' && pgrep -f 'Xvfb' && pgrep -f 'x11vnc' || exit 1"]
  interval: 30s
  timeout: 10s
  start_period: 60s
  retries: 3
```

**Geprüfte Prozesse:**
- ✅ `python main.py` - HCC Plan Anwendung
- ✅ `Xvfb` - X Virtual Framebuffer
- ✅ `x11vnc` - VNC Server

### Manuelle Health-Checks

```bash
# 1. Container-Health-Status
docker inspect --format='{{.State.Health.Status}}' hcc-vnc-anna-direct-v2

# 2. Web-Interface erreichbar?
curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/guacamole/

# 3. Auth-Service (falls konfiguriert)
curl http://localhost:8001/health

# 4. VNC-Port erreichbar?
nc -zv localhost 5902

# 5. Prozesse im Container prüfen
docker exec hcc-vnc-anna-direct-v2 ps aux
```

### Wichtige Logs überwachen

```bash
# HCC Plan GUI Logs
docker exec hcc-vnc-anna-direct-v2 tail -f /var/log/hcc-plan.log

# X11/VNC Logs
docker exec hcc-vnc-anna-direct-v2 tail -f /tmp/x11vnc.log

# Guacamole Logs
docker logs -f hcc-guacamole-direct-v2 2>&1 | grep -E "ERROR|WARN"
```

---

## Häufige Probleme & Lösungen

### Problem 1: Container startet nicht

**Symptome:**
- Container bleibt im Status "Restarting"
- Health-Check schlägt fehl

**Diagnose:**
```bash
docker logs hcc-vnc-anna-direct-v2 --tail=100
```

**Lösungen:**
```bash
# 1. Container komplett neu bauen
docker-compose -f docker-compose-DIRECT.yml down
docker-compose -f docker-compose-DIRECT.yml build --no-cache
docker-compose -f docker-compose-DIRECT.yml up -d

# 2. Volumes zurücksetzen (DATENVERLUST!)
docker-compose -f docker-compose-DIRECT.yml down -v
docker-compose -f docker-compose-DIRECT.yml up --build -d
```

### Problem 2: "Docker ist nicht verfügbar"

**Symptome:**
- Batch-Script meldet "FEHLER: Docker ist nicht verfügbar!"

**Lösungen:**
1. Docker Desktop starten
2. Warten bis Docker-Icon "Ready" zeigt
3. Script erneut ausführen

### Problem 3: Port bereits belegt

**Symptome:**
- Error: "port is already allocated"

**Diagnose:**
```bash
# Windows
netstat -ano | findstr :8081

# Linux/Mac
lsof -i :8081
```

**Lösungen:**
```bash
# Option 1: Prozess beenden
# Windows: Task-Manager -> PID beenden
# Linux: kill -9 <PID>

# Option 2: Anderen Port verwenden
# In docker-compose-DIRECT.yml: "8082:8080" statt "8081:8080"
```

### Problem 4: GUI startet nicht im Browser

**Symptome:**
- Guacamole-Login funktioniert
- Nach Verbindung: Schwarzer Bildschirm

**Diagnose:**
```bash
# Prozesse im Container prüfen
docker exec hcc-vnc-anna-direct-v2 pgrep -f "python.*main.py"
docker exec hcc-vnc-anna-direct-v2 pgrep -f "Xvfb"
docker exec hcc-vnc-anna-direct-v2 pgrep -f "x11vnc"
```

**Lösungen:**
```bash
# VNC-Session neu starten
docker exec hcc-vnc-anna-direct-v2 pkill -f x11vnc
docker exec hcc-vnc-anna-direct-v2 /start-vnc.sh &
```

### Problem 5: Datenbank-Fehler

**Symptome:**
- "Database locked" Fehler
- Daten werden nicht gespeichert

**Diagnose:**
```bash
docker exec hcc-vnc-anna-direct-v2 ls -la /root/.local/share/happy_code_company/hcc_plan/database/
```

**Lösungen:**
```bash
# SQLite-Lock beheben
docker restart hcc-vnc-anna-direct-v2

# Bei persistenten Problemen: Berechtigungen prüfen
docker exec hcc-vnc-anna-direct-v2 chmod 664 /root/.local/share/happy_code_company/hcc_plan/database/database.sqlite
```

### Problem 6: Langsamer Start

**Symptome:**
- Startup dauert >60 Sekunden

**Diagnose:**
```bash
# Startup-Zeit messen
time docker-compose -f docker-compose-DIRECT.yml up -d
```

**Lösungen:**
1. Windows Defender Ausschluss hinzufügen (siehe `docs/WINDOWS_DEFENDER_FEATURE.md`)
2. Direct GUI statt Desktop-Version verwenden
3. SSD statt HDD verwenden

---

## Rollback-Prozeduren

### Rollback zu vorheriger Version

```bash
# 1. Container stoppen
docker-compose -f docker-compose-DIRECT.yml down

# 2. Git-Version zurücksetzen
git checkout <previous-commit-hash>

# 3. Container neu bauen
docker-compose -f docker-compose-DIRECT.yml up --build -d
```

### Rollback zu Desktop-Version (Fallback)

Wenn die Direct GUI Probleme macht, zurück zur bewährten Desktop-Version:

```bash
# 1. Direct GUI stoppen
docker-compose -f docker-compose-DIRECT.yml down

# 2. Desktop-Version starten (falls vorhanden)
docker-compose -f docker-compose-PHASE-2B.yml up --build -d

# Zugang: http://localhost:8080/guacamole/
```

### Container-Image Rollback

```bash
# Verfügbare lokale Images anzeigen
docker images | grep hcc

# Spezifisches Image-Tag verwenden
docker tag hcc-plan:previous hcc-plan:latest
docker-compose -f docker-compose-DIRECT.yml up -d
```

---

## Backup & Recovery

### Datenbank-Backup

```bash
# SQLite-Datenbank kopieren
docker cp hcc-vnc-anna-direct-v2:/root/.local/share/happy_code_company/hcc_plan/database/database.sqlite ./backup/database_$(date +%Y%m%d).sqlite

# Backup-Verzeichnis erstellen falls nicht vorhanden
mkdir -p backup
```

### Automatisches Backup (Cron)

```bash
# Crontab editieren
crontab -e

# Tägliches Backup um 3:00 Uhr
0 3 * * * docker cp hcc-vnc-anna-direct-v2:/root/.local/share/happy_code_company/hcc_plan/database/database.sqlite /backup/database_$(date +\%Y\%m\%d).sqlite
```

### Recovery

```bash
# Datenbank wiederherstellen
docker cp ./backup/database_YYYYMMDD.sqlite hcc-vnc-anna-direct-v2:/root/.local/share/happy_code_company/hcc_plan/database/database.sqlite

# Container neustarten
docker restart hcc-vnc-anna-direct-v2
```

### Volume-Backup

```bash
# Alle Volumes listen
docker volume ls | grep hcc

# Volume-Backup erstellen
docker run --rm -v guacamole_recordings_direct:/data -v $(pwd)/backup:/backup alpine tar cvf /backup/recordings_backup.tar /data

# Volume wiederherstellen
docker run --rm -v guacamole_recordings_direct:/data -v $(pwd)/backup:/backup alpine tar xvf /backup/recordings_backup.tar
```

---

## Checkliste für den Betrieb

### Vor dem Deployment
- [ ] Docker läuft
- [ ] `.env` konfiguriert
- [ ] Ports frei (8081, 5902)
- [ ] Ausreichend Disk-Space

### Nach dem Deployment
- [ ] Container im Status "healthy"
- [ ] Web-Interface erreichbar
- [ ] Login funktioniert
- [ ] GUI startet

### Regelmäßige Wartung
- [ ] Logs auf Fehler prüfen
- [ ] Backup durchführen
- [ ] Disk-Space prüfen
- [ ] Container-Updates installieren

---

## Kontakt & Support

- **GitHub Issues:** Bug-Reports und Feature-Requests
- **Lizenz:** EULA (siehe EULA.rtf)
- **Hersteller:** happy code company
