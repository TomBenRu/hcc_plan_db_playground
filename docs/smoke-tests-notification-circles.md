# Smoke-Tests: Notification-Circles pro Arbeitsort

Manuelle End-to-End-Tests für das in Mai 2026 ausgelieferte
Whitelist-Feature pro Arbeitsort. Voraussetzung: gestartete Web-API
gegen eine Test-DB mit mindestens einem Dispatcher-User, einem Team,
einem Arbeitsort und einigen Mitarbeitern.

## Vorbereitung

```bash
# Migration prüfen
uv run alembic current
# erwartet: a4b5c6d7e8f9 (head)

# Spalte verifizieren
psql $DATABASE_URL -c "\d location_of_work" | grep restricted

# Dev-Server starten
uv run --package hcc-plan-web-api uvicorn web_api.main:app --reload
```

Login als Dispatcher → Dashboard → Tile „Benachrichtigungskreise"
klicken → `/dispatcher/notification-circles` öffnet sich.

## Test-Szenarios

### 1. Default-Verhalten unverändert

Frischer Arbeitsort, `notification_circle_restricted = False` (Default).

- Eine Test-Absage an einem Termin am Arbeitsort feuern (über
  `/cancellations/` als Mitarbeiter).
- Erwartung: Mail-Liste enthält denselben Empfängerkreis wie vor dem
  Feature-Rollout (Auto-Kreis aus `compute_notification_circle`
  Schritt B).

### 2. Toggle Restricted + leere Whitelist

- Detail-View des Arbeitsorts → „Eingrenzen"-Button klicken.
- Mode-Card flippt auf „Eingeschränkt", Members-Card wird voll
  sichtbar (keine Opacity), „+ Person hinzufügen"-Button erscheint.
- Test-Absage feuern → Mail geht **nur** an den Dispatcher; kein
  Mitarbeiter erhält die Benachrichtigung.

### 3. Whitelist mit Treffern

- 2 Personen über das Modal hinzufügen (beide aus dem Pool).
- Beide müssen auch im Auto-Kreis sein (= aktive `TeamActorAssign`,
  keine Termin-Kollision, passende `CombLoc`).
- Test-Absage feuern → Dispatcher + diese 2 erhalten die Mail.

### 4. Whitelist-Member nicht im Auto-Kreis

- Gleicher Setup wie Szenario 3, aber einer der Whitelist-Member hat
  am Termin-Tag einen kollidierenden Einsatz.
- Test-Absage feuern → der kollidierende Member wird **nicht**
  benachrichtigt (Auto-Filter schneidet ihn aus, bevor die Whitelist-
  Intersektion greift).

### 5. Karteileiche

- `TeamActorAssign` einer Whitelist-Person beenden (`end < today`).
- Detail-View des Arbeitsorts neu laden → die Person erscheint
  **nicht** mehr in der Member-Liste.
- Direkter DB-Check: Zeile in `location_notification_circle` existiert
  weiterhin (kein Cleanup-Job nötig, Soft-Filter im Read).

### 6. Pool-Validierung 403

```bash
curl -X POST -H "Cookie: <session>" \
     -d "web_user_ids=<uuid_aus_fremdem_team>" \
     /dispatcher/notification-circles/<loc_id>/members
# erwartet: 403 Forbidden, Detail nennt die Out-of-Pool-IDs.
```

### 7. Multi-Team-Person im Pool

- Person ist in zwei Teams, beide Teams sind via `TeamLocationAssign`
  mit demselben Arbeitsort verbunden.
- Add-Member-Modal öffnen → die Person erscheint **genau einmal**
  (Service hat `DISTINCT web_user.id`).

### 8. Visibility Cross-Team

- Dispatcher von Team A (kein Dispatcher in Team B).
- Direkter URL-Aufruf zur Detail-View eines Arbeitsorts, der nur in
  Team B liegt: `GET /dispatcher/notification-circles/<loc_id_team_b>`.
- Erwartung: 403 Forbidden (`assert_dispatcher_owns_location`).

### 9. Tile-Counter-Polling

- 2 Arbeitsorte auf restricted toggeln.
- Zurück zum Dashboard.
- Innerhalb von max. 30 s zeigt der Tile-Badge „2".
- Einen Arbeitsort wieder auf „Alle" stellen → nach max. 30 s zeigt
  der Badge „1".

### 10. Render-Deploy

- `git push` löst Pre-Deploy-Hook auf Render aus.
- Hook-Log enthält `alembic upgrade … a4b5c6d7e8f9`.
- Web-Service startet ohne ImportError.

## Bekannte Spec-Abweichungen

- Im additiven Original-PRD-Modell wurde `NotificationSource.preconfigured`
  als Empfänger-Quelle gesetzt. Im neuen Modell ist die Whitelist ein
  Filter — alle Empfänger sind per Definition `auto_computed`. Die
  Enum-Werte `preconfigured` und `both` bleiben aus
  Backwards-Compat-Gründen erhalten, werden aber nicht mehr gesetzt.

- PRD-Pfad `/settings/location/{id}/circle` wurde zu
  `/dispatcher/notification-circles/{loc_id}` (konsistent mit der
  Notification-Groups-View).
