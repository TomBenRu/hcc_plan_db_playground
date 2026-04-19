# Smoke-Test-Plan — Audit-Migration + Auth-Phase

**Stand:** 2026-04-18, nach Abschluss der Auth-Phase (Silent-Login
empirisch verifiziert). Vor diesem Plan standen die Runtime-Tests der
Audit-Kat-A/B-Migration (~40 GUI-Writes umgestellt) aus, weil sie eine
funktionierende Authentifizierung voraussetzen.

**Update 2026-04-19:** Alle **Undo-bezogenen** Smoke-Tests (Ctrl+Z /
Ctrl+Shift+Z) sind **zurueckgestellt** — Undo in ActorPlanPeriod und
LocationPlanPeriod ist aktuell nicht dringend, und die Implementierung
eines globalen Ctrl+Z-Handlers hat Side-Effects. Im Folgenden mit
`[~] UNDO zurueckgestellt` markiert.

**Zweck:** Systematisch durchtesten, dass die in der vorherigen Session
migrierten Widgets + die neu angelegten Commands im echten Flow
funktionieren. Keine Unit-Tests — das ist manuelles Klicken + Beobachten.

---

## Voraussetzungen

- [ ] FastAPI-Server laeuft (`uvicorn web_api.main:app` o. ae.),
  erreichbar unter `DESKTOP_API_URL` (Default `http://localhost:8000`).
- [ ] Mindestens ein WebUser mit Rolle `admin` oder `dispatcher`
  existiert (`uv run scripts/create_admin.py --email owner@test.de`).
- [ ] Projekt + Team + mindestens eine PlanPeriod sind vorhanden,
  sonst sind die Maskentests leer.
- [ ] Desktop-App startet sauber (Login-Flow durchlaeuft).

Bei jedem Fehler: **Logs mitschreiben** (Console-Output der Desktop-App),
Commit-Hash des getesteten Standes notieren.

---

## 1. Auth-Phase (Smoke-Check, bereits erledigt)

- [x] **Bootstrap-CLI** legt Admin an: `uv run scripts/create_admin.py --email ...`
- [x] **Login-Dialog** erscheint beim ersten Start, Credentials akzeptiert
- [x] **Keyring-Persistenz**: `hcc-plan-desktop` im Windows Credential Manager
- [x] **Silent-Login** beim Neustart ohne Dialog (INFO-Log "Silent-Login erfolgreich.")

**Offen** (wenn Interesse):

- [ ] **Keyring abgelehnt**: was passiert bei headless Linux (keine Secret
  Service)? Erwartet: App laeuft, aber "Angemeldet bleiben" hat keinen Effekt.
- [ ] **Refresh-Token abgelaufen**: ACCESS_TOKEN_EXPIRE_MINUTES runterdrehen,
  mehrere Minuten warten, Mutation auslösen — Interceptor muss 401 abfangen,
  Refresh einmalig durchziehen, Request wiederholen. Bei Refresh-Token
  selbst abgelaufen: Auth-Exception landet im Widget.

---

## 2. Audit Kat-A — Widget-Umstellungen

### 2.1 Notes-Focus-Out-Pattern

Betrifft: `frm_actor_plan_period.py` (A1, commit `f0bcec8`),
`frm_location_plan_period.py` (A2, commit `c5cf537`).

- [x] **Akteur-Notizen persistieren** (getestet 2026-04-18):
    1. Akteur-Planungsmaske oeffnen, Person auswaehlen.
    2. In "Infos zum Planungszeitraum" tippen.
    3. Tab-Taste (Fokus-Wechsel) → es darf **kein** DB-Write pro Keystroke
       passieren, sondern genau **einer** am Tab-Zeitpunkt.
    4. App schliessen, neu starten, selber Akteur → Text ist da.
    **Ergebnis:** 422-Bug auf `PATCH /persons/{id}/notes` gefunden und
    behoben (commit `5a865db` — neuer `Person.UpdateNotes`-Command +
    `update_notes`-Service). Notes-Pfad funktional.

- [x] **Personen-Wechsel-Race** (getestet 2026-04-19, kein Bug):
    1. Notiz fuer Person A tippen.
    2. **Direkt** auf Person B in der Liste klicken (ohne Tab).
    3. App schliessen, neu starten, Person A oeffnen → ist die Notiz bei A
       gespeichert? (Erwartet: ja.)
    4. Falls Notiz verloren oder bei Person B landet: Bug. Fix ist trivial
       (Snapshot der person_id auf NotesTextEdit zur Setup-Zeit).
    **Ergebnis:** Notiz landete korrekt bei Person A — Qt-Event-Reihenfolge
    (Focus-Out vor Personen-Wechsel) schuetzt den Pfad empirisch.

- [x] **LPP-Notizen + Location-Notizen persistieren** (getestet 2026-04-19):
  gleiche Prozedur fuer `te_notes_pp` + `te_notes_location` in der
  Standort-Planungsmaske. Beide Felder persistieren korrekt nach
  App-Restart.

### 2.2 Reset-Pfade (Inkonsistenz-Repair)

Betrifft: `ButtonLocationCombinations._reset_to_defaults` +
`ButtonLocationPreferences._reset_to_defaults` (A1).

- [x] Inkonsistenz war im Bestand vorhanden (unbeabsichtigt), Auto-Reset
  wurde dadurch beim Oeffnen der Maske fuer einen Mitarbeiter getriggert.
- [x] Akteur-Maske neu laden → QMessageBox "reset to default" erscheint.
- [x] Danach sind alle AvailDays am Tag DB-seitig mit APP-Defaults (bewiesen
  durch App-Restart: nach Restart tritt die Message nicht mehr auf).
  **ABER: Bug entdeckt** — `_ensure_consistency` invalidiert den Entities-
  Cache nicht, dadurch feuert die Message bei jedem Person-Reload ohne
  Restart erneut. Dokumentiert in Memory
  `bug_ensure_consistency_no_cache_invalidate.md`. Fix zurueckgestellt.
- [~] **Ein** `ReplaceAvailDayCombLocPossibles`-Eintrag im Undo-Stack, **nicht** 2N.
  UNDO zurueckgestellt.

### 2.3 Person-Delete + Undo

Betrifft: `frm_masterdata.py:183` (A3, commit `1ac3693`).

- [x] Person via Masterdaten loeschen → Bestaetigungs-Dialog → OK (getestet 2026-04-19).
- [x] Person verschwindet aus der Tabelle (soft-delete, DELETE /persons/{id} fehlerfrei).
- [~] Ctrl+Z (Undo) → Person wieder da (via `api_person.undelete`). UNDO zurueckgestellt.
- [~] Ctrl+Shift+Z (Redo) → Person erneut geloescht. UNDO zurueckgestellt.

### 2.4 Project.update_name + Admin-Wechsel

Betrifft: `frm_project_settings.py:124/141` (A4 + B1).

- [x] Projekt-Einstellungen oeffnen, Namen aendern, Speichern → Message,
  UI spiegelt neuen Namen (getestet 2026-04-19, fehlerfrei).
  [~] Ctrl+Z → alter Name zurueck. UNDO zurueckgestellt.
- [x] Admin-Dropdown auf andere Person aendern, Speichern → Message
  (getestet 2026-04-19, fehlerfrei).
  [~] Ctrl+Z → vorheriger Admin wiederhergestellt. Falls vorher kein Admin
  gesetzt war: Undo entfernt die Zuordnung komplett (clear_admin_of_project).
  UNDO zurueckgestellt.

### 2.5 PlanPeriod- und Plan-Cleanup

- [~] **PlanPeriod prep-deletes hart loeschen** (A5, commit `e7ae225`):
  Zurueckgestellt 2026-04-19 — keine prep-deleted PlanPerioden im aktuellen
  DB-Stand. Runtime-Check nachholen, sobald entsprechende Testdaten anfallen.

- [x] **Plan prep-deletes per Team hart loeschen** (A7, commit `fdf4deb`)
  (getestet 2026-04-19, fehlerfrei):
  Hauptmenue "Plaene des Teams endgueltig loeschen" → Bestaetigung → weg.
  Undo no-op.

### 2.6 Team-Assignments (Plan-Perioden-Bulk-Create)

Betrifft: `frm_team_assignments.py:154/155` (A6, commit `66ce076`).

- [x] Person einem Team zuweisen, "Plan-Perioden erstellen?" → Ja
  (getestet 2026-04-19, fehlerfrei).
- [x] Fuer jede offene PlanPeriod entstehen APP + AvailDayGroup (2 Undo-
  Schritte pro PlanPeriod — bewusst akzeptiert).

---

## 3. Audit Kat-B — Neue Endpoints + Commands

### 3.1 ExcelExportSettings.update

Betrifft: `frm_project_settings.py`, `main_window.py` (B3, commit `0f358bb`).

- [x] **Projekt-Excel-Settings** aendern, Speichern → Farbvorschau aktualisiert
  (getestet 2026-04-19, fehlerfrei).
  [~] Ctrl+Z → alte Farben zurueck. UNDO zurueckgestellt.
- [x] **Team-Excel-Settings** (main_window): gleich (getestet 2026-04-19, fehlerfrei).
  [~] Undo pruefen zurueckgestellt.
- [x] **Plan-Excel-Settings** (main_window): gleich (getestet 2026-04-19, fehlerfrei).
  [~] Undo pruefen zurueckgestellt.

### 3.2 TimeOfDay-Cleanup

Betrifft: `frm_actor_plan_period` / `frm_location_plan_period` /
`frm_time_of_day` (B4, commit `65069d4`).

- [x] Im TimeOfDay-Edit-Dialog einen TimeOfDay anlegen, dann Dialog
  OHNE Anwendung schliessen (Cancel) → `delete_unused` entfernt den
  orphaned Eintrag (getestet 2026-04-19, fehlerfrei).
- [x] `delete_prep_deletes` laeuft nach "TimeOfDay-Standard zuruecksetzen"
  in beiden Planungsmasken; kein Crash (getestet 2026-04-19).

### 3.3 Team CRUD

Betrifft: `frm_team.py` (B5, commit `3a79358`).

- [x] **Team erstellen** (neues Team im Dialog, Speichern): erscheint in
  Tabelle (getestet 2026-04-19, fehlerfrei).
  [~] Ctrl+Z → verschwindet. [~] Ctrl+Shift+Z → wieder da (undelete).
  UNDO zurueckgestellt.
- [x] **Team aendern** (Name + Dispatcher) (getestet 2026-04-19, fehlerfrei).
  [~] Ctrl+Z → alte Werte. UNDO zurueckgestellt.
- [x] **Team loeschen**: Soft-Delete, aus Anzeige weg (getestet 2026-04-19, fehlerfrei).
  [~] Ctrl+Z → zurueck. UNDO zurueckgestellt.

### 3.4 LocationOfWork CRUD

Betrifft: `frm_masterdata.py`, `frm_location_plan_period.py` (B6, commit `9045114`).

- [x] **Standort erstellen** via Masterdaten → in Tabelle (getestet 2026-04-19).
  [~] Ctrl+Z → weg. [~] Ctrl+Shift+Z → wieder da. UNDO zurueckgestellt.
  **Ergebnis:** IntegrityError bei Name-Kollision lieferte 500 statt 409.
  Behoben (commit `784cb54` — globaler IntegrityError-Handler + UX-Dialog
  in `frm_masterdata.py`).
- [x] **Standort loeschen**: Soft (getestet 2026-04-19). [~] Ctrl+Z restored.
  UNDO zurueckgestellt.
  **Ergebnis:** `delete_location` las `location_id` aus falscher Quelle
  → Delete griff nicht. Behoben (commit `925be82`).
- [x] **Standort-Notizen** in Standort-Planungsmaske bearbeiten: Focus-Out
  speichert (getestet 2026-04-19, fehlerfrei).
  [~] Ctrl+Z stellt alten Text wieder her (A2-TODO final geschlossen).
  UNDO zurueckgestellt.

---

## 4. Uebergreifend — Auth-Integration

- [x] **401-Interceptor**: Mutation-Aufruf nach abgelaufenem Access-Token
  → Interceptor refresht einmalig + wiederholt Request, User merkt nichts
  (getestet 2026-04-19 mit `ACCESS_TOKEN_EXPIRE_MINUTES=1` + Re-Login).
- [x] **Logout bei abgelaufenem Refresh-Token** (getestet 2026-04-19 via
  SECRET_KEY-Rotation):
  Wenn Refresh auch abgelaufen / ungueltig, Access-Token-Wiederholung
  scheitert → `ApiAuthError` propagiert zum Excepthook. Ergebnis der
  Testrunde: zwei Bugs gefunden und behoben.
  **Fix 1**: Vorher zeigte der generische Crash-Dialog "Ein kritischer
  Fehler ist aufgetreten... Log-Datei an Support". Jetzt: `crash_handler.py`
  erkennt `ApiAuthError` per Klassenname, 401 → "Sitzung abgelaufen"
  Warning-Dialog + App-Quit, 403 → "Keine Berechtigung" Warning-Dialog
  (App laeuft weiter).
  **Fix 2**: `_try_refresh_on_401` persistierte rotierte Refresh-Tokens
  unbedingt im Keyring, auch wenn der User bei Login "Angemeldet bleiben"
  **nicht** gesetzt hatte. Jetzt: neues Consent-Flag `_persist_refresh`
  respektiert die Login-Entscheidung bei allen Refresh-Rotationen.
- [x] **Logout-Funktion**: `client.logout()` loescht Keyring + Session-
  Cookies + Access-Token. UI-Einstieg: **File → Logout** (mit Warning-
  Dialog Yes/No, Default No) implementiert und getestet 2026-04-19.
  Keyring-Eintrag wird geleert, naechster Start zeigt Login-Dialog statt
  Silent-Login.

---

## 5. Performance-Spotchecks

Nicht kritisch, aber gelegentlich nachmessen — vor allem mit remote DB:

- [~] **Silent-Login-Latenz**: beim empirischen Verify waren es 2.2s — warum?
  Erwartet auf localhost <100ms. Ursache vermutlich FastAPI-Lazy-Init.
  Wird erst spannend, wenn der Wert nach dem 2. Login auch >500ms bleibt.
  Zurueckgestellt 2026-04-19 — "bei Gelegenheit" nachmessen.
- [~] **Notes-Save-Latenz**: Focus-Out → erster DB-Write. Mit remote DB
  sollten <200ms sinnvoll sein, sonst wirkt der Tab-Wechsel laggy.
  Zurueckgestellt 2026-04-19 — "bei Gelegenheit" nachmessen.
- [~] **Reset-to-Defaults**: 1 Roundtrip statt 2N — nachmessen, dass das
  auch empirisch so ist. Zurueckgestellt 2026-04-19 — "bei Gelegenheit"
  nachmessen.

---

## 6. Abschluss-Kriterien

- [ ] Alle **kritischen Checkboxen** in Abschnitt 2-3 gruen (Notes,
  Reset-Pfade, CRUD-Undo/Redo).
- [ ] **Personen-Wechsel-Race** ausdrücklich getestet und dokumentiert —
  ob Bug oder nicht.
- [ ] **Keine regressions** in Widgets, die nicht angefasst wurden
  (stichprobenhaft: Appointment-Verschiebung, Cast-Group-Dialog,
  Gruppen-Modus).

Alle offenen Checkboxen, die danach noch als "reproducibly broken"
markiert sind, wandern in ein Followup-Backlog (neue Memory-Eintraege
`bug_*.md`).

---

## Querverweise

- Kat-A/B-Migration (Ausgangspunkt): Memory
  `project_desktop_api_audit_2026_04_18.md`
- Auth-Phase-Stand: Memory `project_auth_phase_COMPLETE_april2026.md`
- Audit-Planfile: `C:\Users\tombe\.claude\plans\desktop-api-migration.md`
- Feedback "stets Commands": Memory `feedback_always_use_command_pattern.md`

---

**Letzte Aktualisierung:** 2026-04-19 — Smoke-Test-Session abgeschlossen.
Abschnitte 2-4 strukturell verifiziert (ausser Undo-Subchecks und 2.5a —
keine Testdaten). Abschnitt 5 (Performance) zurueckgestellt "bei
Gelegenheit".

**Heute gefundene und behobene Bugs:**
1. `_ensure_consistency` ohne Cache-Invalidation (bug_*.md festgehalten,
   Fix zurueckgestellt).
2. Cryptic Crash-Dialog fuer `ApiAuthError` — gefixt in `crash_handler.py`
   (401/403-spezifische Warning-Dialoge statt Crash-Cascade).
3. Refresh-on-401 ignorierte "Angemeldet bleiben"-Opt-Out — gefixt in
   `api_client/client.py` via `_persist_refresh`-Flag.