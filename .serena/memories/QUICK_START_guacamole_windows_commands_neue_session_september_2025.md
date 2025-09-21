# QUICK START COMMANDS: Guacamole Windows-Session (September 2025)

## 🚀 ERSTE SCHRITTE FÜR NEUE SESSION

### **1. Session initialisieren:**
```bash
serena:activate_project hcc_plan_db_playground
serena:read_memory guacamole_windows_implementation_HANDOVER_session_neue_september_2025
```

### **2. Container-Cleanup (falls nötig):**
```powershell
docker-compose -f docker-compose-sqlite.yml down -v
docker system prune -f
```

### **3. Sofort-Diagnose - Windows Container-Problem:**
```powershell
# Container Status prüfen
docker-compose -f docker-compose-sqlite.yml ps

# WICHTIG: Auth Service Logs anzeigen
docker-compose -f docker-compose-sqlite.yml logs hcc-auth-service

# Windows Environment prüfen
echo $env:LOCALAPPDATA
echo $env:APPDATA
echo $env:USERPROFILE

# HCC Plan Database prüfen
Test-Path "$env:LOCALAPPDATA\happy_code_company\hcc_plan\database\database.sqlite"
```

### **4. Windows-optimierte Container starten:**
```powershell
# Environment setup
copy .env-windows .env

# Windows-Container-Setup starten
docker-compose -f docker-compose-windows.yml up -d

# Logs verfolgen
docker-compose -f docker-compose-windows.yml logs -f hcc-auth-service
```

### **5. Manual Health-Check:**
```powershell
# Warten auf Container-Start
Start-Sleep -Seconds 30

# Auth Service testen
Invoke-WebRequest -Uri "http://localhost:8001/health" -Method GET

# Guacamole testen  
Invoke-WebRequest -Uri "http://localhost:8080" -Method GET
```

## 🔧 PRIORITÄRE FIXES

### **Fix 1: HOME Variable Problem**
```yaml
# In docker-compose-windows.yml
environment:
  - HOME=/root
  - USERPROFILE=/root
```

### **Fix 2: Windows Volume-Mapping**
```yaml
# Hardcoded Windows-Pfade für ersten Test
volumes:
  - C:\Users\tombe\AppData\Local\happy_code_company:/root/AppData/Local/happy_code_company:rw
```

### **Fix 3: Health-Check-Timeout**  
```yaml
# Erweiterte Health Check
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
  interval: 30s
  timeout: 15s
  retries: 5
  start_period: 60s  # Wichtig für Windows!
```

## 📁 DATEIEN-ÜBERBLICK FÜR NEUE SESSION

### **Windows-spezifische Dateien (erstellt):**
- `docker-compose-windows.yml` - ✅ Windows-optimiert
- `.env-windows` - ✅ Windows Environment-Vars
- `diagnose-docker-issues.ps1` - ❌ PowerShell Syntax-Errors  
- `start-guacamole-windows.ps1` - ❌ PowerShell Syntax-Errors

### **Funktionierende Basis-Dateien:**
- `auth-service/main.py` - ✅ FastAPI komplett implementiert
- `docker-compose-sqlite.yml` - ✅ SQLite-Setup (Linux-tauglich)
- `README-Guacamole.md` - ✅ Comprehensive Documentation

## 🎯 KONKRETE TODOS FÜR NEUE SESSION

### **TODO 1: Container-Logs analysieren**
```powershell
# Exakte Fehlermeldung des Auth Service ermitteln
docker-compose -f docker-compose-sqlite.yml logs hcc-auth-service | Out-String
```

### **TODO 2: SQLite-Pfad verifizieren**
```powershell
# Lokale HCC Plan Database lokalisieren
Get-ChildItem -Path "$env:LOCALAPPDATA\happy_code_company" -Recurse -Name "*.sqlite"
```

### **TODO 3: Manual Container-Test**
```powershell
# Auth Service Container direkt testen (ohne Health Check)
docker run -it --rm -p 8001:8000 hcc_plan_db_playground-hcc-auth-service /bin/bash
```

### **TODO 4: Vereinfachte docker-compose**
```yaml
# Minimal-Setup ohne Health-Checks für ersten Test
# Nur Auth Service + Guacamole, keine Scripts
```

## ⚡ ERFOLGSPFAD - STEP BY STEP

### **Phase 1: Problem identifizieren (15 min)**
1. ✅ Container-Logs analysieren → Root cause finden
2. ✅ SQLite-Database-Pfad verifizieren → Windows-Pfad bestätigen  
3. ✅ Volume-Mapping testen → Container kann DB erreichen?

### **Phase 2: Basic Fix (30 min)**
4. ✅ HOME Variable setzen → Environment-Problem lösen
5. ✅ Hardcoded Volume-Pfade → Windows-Mapping funktionsfähig machen
6. ✅ Health-Check deaktivieren → Container-Start ermöglichen

### **Phase 3: Erfolg validieren (15 min)**
7. ✅ Auth Service erreichbar → http://localhost:8001/health
8. ✅ Guacamole erreichbar → http://localhost:8080  
9. ✅ Basic Login-Test → HCC Plan User-Authentication

## 🏆 ERFOLGS-INDIKATOREN

### **MVP erreicht wenn:**
- ✅ `docker-compose ps` zeigt alle Container als "Up" (healthy)
- ✅ `curl http://localhost:8001/health` returniert HTTP 200
- ✅ `curl http://localhost:8080` returniert Guacamole Login-Page  
- ✅ Keine "HOME variable not set" Warnings

### **Full Success erreicht wenn:**
- ✅ Login über http://localhost:8080 mit HCC Plan User funktioniert
- ✅ Multi-User-Sessions funktionieren (mehrere Browser-Tabs)
- ✅ Windows-Setup-Scripts sind korrekt und funktionsfähig

---

**🎯 FOKUS NEUE SESSION**: Container-Startup-Problem beheben mit Windows-spezifischen Fixes
**⏱️ ESTIMATED TIME**: 60-90 Minuten für vollständig funktionierende Lösung
**🎉 END GOAL**: Lokaler Multi-User Guacamole-Test mit bestehender HCC Plan SQLite-DB