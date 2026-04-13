# PRD: Absage-Workflow (Cancellation Workflow)

**Datum:** 2026-04-12  
**Status:** Anforderungen finalisiert, Implementierung ausstehend  
**Bezug:** `database/models.py`, `web_api/`, `web_api/models/web_models.py`

> **Architektur-Leitentscheidung:** Der Desktop-Klient greift für Aktionen dieses Workflows
> **nicht** direkt auf die DB zu, sondern ruft die Web-API-Endpoints auf. Dies ist der erste
> Anwendungsfall der mittelfristigen Umstellung „Desktop → API-first". Die gesamte
> Geschäftslogik (Plan-Anpassung, Inbox, E-Mail) lebt ausschließlich in der Web-API.

---

## 1. Problem

Mitarbeiter müssen Termine absagen können, ohne den Dispatcher direkt anrufen oder eine E-Mail schreiben zu müssen. Gleichzeitig müssen Ersatz-Optionen strukturiert kommuniziert werden: Wer kann einspringen? Wer ist bereit zum Tauschen? Der Dispatcher braucht eine zentrale Übersicht und soll einfache Aktionen (Übernahme bestätigen) direkt in der Web-Oberfläche ausführen können.

---

## 2. Lösungsüberblick

Ein strukturierter Workflow in drei Stufen:

```
Stufe 1 — Absage (Phase 1)
  Mitarbeiter sagt Appointment ab → CancellationRequest (pending)
  → Email + Inbox: Dispatcher + Benachrichtigungs-Kreis

Stufe 2 — Reaktionen (Phase 2)
  Mitarbeiter macht Übernahmeangebot → TakeoverOffer
  Mitarbeiter stellt Tausch-Anfrage → SwapRequest
  → Email + Inbox: Dispatcher + Betroffene

Stufe 3 — Abschluss (Phase 2)
  Dispatcher bestätigt Übernahme oder Tausch → Plan-Anpassung
  → Email + Inbox: alle Beteiligten
  → CancellationRequest → resolved
```

---

## 3. Scope

### Phase 1 (Pflicht)
- CancellationRequest erstellen und anzeigen
- Absage-Frist-Prüfung (konfigurierbar)
- Benachrichtigungs-Kreis berechnen (auto + vorab-konfiguriert)
- E-Mail-Versand (Dispatcher + Kreis)
- Inbox-System (Dispatcher + Mitarbeiter)
- Absage zurückziehen
- Dispatcher-Inbox: Absagen-Übersicht

### Phase 2 (Defer)
- Übernahmeangebote (TakeoverOffer)
- Tausch-Anfragen (SwapRequest)
- Dispatcher bestätigt Übernahme → automatische Plan-Anpassung (via Web-API)
- Dispatcher bestätigt Tausch → automatische Plan-Anpassung (via Web-API)
- Dispatcher-Einstellungen für Benachrichtigungs-Kreis pro Arbeitsort (UI)
- Desktop-Klient: Übernahme/Tausch bestätigen via Web-API-Aufruf (HTTP-Client im Desktop)

---

## 4. User Stories

### US-01 — Mitarbeiter sagt Termin ab
Als Mitarbeiter möchte ich einen Termin aus meinem verbindlichen Kalender absagen können, damit der Dispatcher und geeignete Kollegen informiert werden.

**Akzeptanzkriterien:**
- Nur Appointments aus dem verbindlichen Plan (is_binding=True) können abgesagt werden
- Absage ist nur möglich, solange die konfigurierte Absagefrist nicht überschritten ist
- Optionales Freitext-Feld für Begründung
- Nach Absage: sofortige Email + Inbox-Benachrichtigung an Dispatcher und Benachrichtigungs-Kreis

### US-02 — Mitarbeiter zieht Absage zurück
Als Mitarbeiter möchte ich eine noch offene Absage zurückziehen können, damit mein Termin wieder als verbindlich gilt.

**Akzeptanzkriterien:**
- Rückzug nur möglich, solange `status = pending`
- Nach Rückzug: gleiche Benachrichtigungen wie bei Absage (Email + Inbox an Dispatcher + Kreis)
- `CancellationRequest` wird nicht gelöscht, sondern erhält `status = withdrawn` (Audit-Trail)

### US-03 — Dispatcher sieht Absagen-Übersicht
Als Dispatcher möchte ich alle offenen Absagen meines Teams sehen, damit ich schnell reagieren kann.

**Akzeptanzkriterien:**
- Liste aller `pending`-Absagen, sortiert nach Termin-Datum (nächster zuerst)
- Pro Absage: Mitarbeiter, Einsatzort, Datum/Uhrzeit, Planperiode, Begründung, Benachrichtigungs-Kreis
- Filterung nach Planperiode und Status

### US-04 — Mitarbeiter macht Übernahmeangebot (Phase 2)
Als Mitarbeiter möchte ich für einen abgesagten Termin ein Übernahmeangebot machen, damit der Dispatcher es einfach bestätigen kann.

**Akzeptanzkriterien:**
- Nur für Appointments im Benachrichtigungs-Kreis der Absage sichtbar
- Optionale Nachricht
- Sofortige Email + Inbox an Dispatcher
- Dispatcher sieht alle Angebote in der Absage-Detailansicht

### US-05 — Dispatcher bestätigt Übernahme (Phase 2)
Als Dispatcher möchte ich ein Übernahmeangebot direkt bestätigen — aus der Web-Oberfläche
oder aus dem Desktop-Klienten —, damit die Plan-Anpassung automatisch erfolgt.

**Akzeptanzkriterien:**
- Bestätigung über Web-UI **oder** Desktop-Klient (Desktop ruft denselben API-Endpoint auf)
- Bestätigung markiert TakeoverOffer als `accepted`
- System passt den Plan an (AvailDayAppointmentLink umschreiben)
- Falls übernehmender Mitarbeiter keinen AvailDay für diesen Tag hat: automatisch anlegen
- `CancellationRequest` → `resolved`
- Email + Inbox an alle: ursprünglicher Mitarbeiter, Übernehmer, alle im Benachrichtigungs-Kreis

### US-06 — Mitarbeiter stellt Tausch-Anfrage (Phase 2)
Als Mitarbeiter möchte ich meinen Termin gegen einen bestimmten Termin eines anderen Mitarbeiters tauschen.

**Akzeptanzkriterien:**
- Auswahl: eigener Termin (Quelle) + konkreter Termin des Ziel-Mitarbeiters
- Ziel-Mitarbeiter erhält Email + Inbox mit Tausch-Anfrage
- Dispatcher erhält Email + Inbox über die Anfrage
- Ziel-Mitarbeiter muss aktiv akzeptieren oder ablehnen
- Bei Akzeptanz durch Ziel-Mitarbeiter: Dispatcher muss final bestätigen
- Dispatcher-Bestätigung möglich via Web-UI **oder** Desktop-Klient (gleicher API-Endpoint)
- Nach Dispatcher-Bestätigung: Plan-Anpassung + Benachrichtigungen

### US-07 — Admin konfiguriert Absagefrist
Als Admin möchte ich die Absagefrist pro Projekt festlegen, damit kurzfristige Web-Absagen verhindert werden.

**Akzeptanzkriterien:**
- Frist in Stunden konfigurierbar (z.B. 48 = keine Absage weniger als 48h vor Termin)
- Pro Projekt; Dispatcher kann pro Team überschreiben
- Frist = 0 bedeutet: keine Frist (immer absagbar)

### US-08 — Dispatcher konfiguriert Benachrichtigungs-Kreis (Phase 2 UI)
Als Dispatcher möchte ich vorab festlegen, welche Mitarbeiter bei Absagen an einem bestimmten Arbeitsort immer benachrichtigt werden.

**Akzeptanzkriterien:**
- Liste von WebUsern pro LocationOfWork verwaltbar (add/remove)
- Diese Liste ergänzt die automatisch berechneten Kandidaten

---

## 5. Datenmodell

### 5.1 Neue Tabellen

#### `project_settings`
```sql
id                          UUID PK
project_id                  UUID FK → project (UNIQUE)
cancellation_deadline_hours INT NOT NULL DEFAULT 48
created_at                  TIMESTAMP
last_modified               TIMESTAMP
```

#### `team_notification_settings`
```sql
id                          UUID PK
team_id                     UUID FK → team (UNIQUE)
cancellation_deadline_hours INT NULL  -- NULL = erbt von project_settings
created_at                  TIMESTAMP
last_modified               TIMESTAMP
```

#### `location_notification_circle`
Vorab-konfigurierter Abonnenten-Kreis pro Arbeitsort (durch Dispatcher verwaltet).
```sql
location_of_work_id  UUID FK → location_of_work  \
web_user_id          UUID FK → web_user            / PK (composite)
added_by_id          UUID FK → web_user
created_at           TIMESTAMP
```

#### `cancellation_request`
```sql
id                      UUID PK
appointment_id          UUID FK → appointment
web_user_id             UUID FK → web_user  (Antragsteller)
reason                  TEXT NULL
status                  ENUM (pending, resolved, withdrawn)
created_at              TIMESTAMP
resolved_at             TIMESTAMP NULL
resolved_by_id          UUID FK → web_user NULL
```

#### `cancellation_notification_recipient`
Audit-Snapshot: Wer wurde beim Erstellen der Absage benachrichtigt und warum.
```sql
id                        UUID PK
cancellation_request_id   UUID FK → cancellation_request
web_user_id               UUID FK → web_user
source                    ENUM (auto_computed, preconfigured, both)
```

#### `takeover_offer` (Phase 2)
```sql
id                        UUID PK
cancellation_request_id   UUID FK → cancellation_request
web_user_id               UUID FK → web_user  (Anbieter)
message                   TEXT NULL
status                    ENUM (pending, accepted, rejected)
created_at                TIMESTAMP
```

#### `swap_request` (Phase 2)
```sql
id                          UUID PK
requester_web_user_id       UUID FK → web_user
requester_appointment_id    UUID FK → appointment
target_web_user_id          UUID FK → web_user
target_appointment_id       UUID FK → appointment
message                     TEXT NULL
status                      ENUM (pending, accepted_by_target, rejected_by_target,
                                   confirmed_by_dispatcher, rejected_by_dispatcher,
                                   withdrawn)
created_at                  TIMESTAMP
```

#### `inbox_message`
```sql
id                      UUID PK
recipient_web_user_id   UUID FK → web_user
type                    ENUM (s.u.)
reference_id            UUID  (polymorphic — CancellationRequest / TakeoverOffer / SwapRequest)
reference_type          VARCHAR  (cancellation_request / takeover_offer / swap_request)
is_read                 BOOLEAN DEFAULT FALSE
created_at              TIMESTAMP
snapshot_data           JSONB  (Display-relevante Daten zum Erstellungszeitpunkt: Name,
                                 Einsatzort, Datum — damit Inbox auch nach Plan-Änderungen
                                 korrekt bleibt)
```

**InboxMessage-Typen:**
| Typ | Empfänger | Auslöser |
|---|---|---|
| `cancellation_new` | Dispatcher + Kreis | Neue Absage |
| `cancellation_withdrawn` | Dispatcher + Kreis | Absage zurückgezogen |
| `cancellation_resolved` | Dispatcher + Kreis + Beteiligter | Absage gelöst |
| `takeover_offer_received` | Dispatcher | Neues Übernahmeangebot |
| `takeover_accepted` | Anbieter + Kreis + Absager | Übernahme bestätigt |
| `swap_request_received` | Ziel-Mitarbeiter + Dispatcher | Neue Tausch-Anfrage |
| `swap_accepted_by_target` | Dispatcher | Ziel hat Tausch akzeptiert |
| `swap_confirmed` | Anfragender + Ziel + Dispatcher | Dispatcher hat Tausch bestätigt |
| `swap_rejected` | Anfragender | Tausch abgelehnt (Ziel oder Dispatcher) |

---

## 6. Benachrichtigungs-Kreis: Berechnungslogik

### Eingabe
- `appointment`: Der abgesagte Termin (hat `event_id` → `event` → `location_of_work_id`, `date`)
- `plan_period`: Über `appointment.plan.plan_period_id`

### Schritt 1 — Vorab-konfigurierte Abonnenten
```sql
SELECT web_user_id FROM location_notification_circle
WHERE location_of_work_id = :loc_id
```

### Schritt 2 — Auto-berechnete Kandidaten
Alle `ActorPlanPeriod`-Einträge der gleichen `PlanPeriod`, die am Termin-Datum verfügbar sind:

**Kandidat ist verfügbar wenn:**

**(A) Kein anderer Appointment an diesem Datum** (aus dem verbindlichen Plan):
```sql
NOT EXISTS (
  SELECT 1
  FROM avail_day_appointment_link adal
  JOIN appointment a ON a.id = adal.appointment_id
  JOIN plan p ON p.id = a.plan_id
  JOIN event e ON e.id = a.event_id
  WHERE adal.avail_day_id = avail_day.id
    AND e.date = :event_date
    AND p.is_binding = TRUE
    AND p.prep_delete IS NULL
)
```

**(B) ODER CombinationLocationsPossible lässt Kombination zu:**
Die `ActorPlanPeriod` des Kandidaten hat einen `CombinationLocationsPossible`-Eintrag, der sowohl die Location des bestehenden Appointments als auch die des abgesagten Termins enthält UND `time_span_between` zwischen beiden Terminen eingehalten ist.

### Schritt 3 — Ausschlüsse
- Der Mitarbeiter, der absagt, wird nie in seinen eigenen Kreis aufgenommen
- Nur Mitarbeiter mit einem `WebUser`-Eintrag (ohne Web-Login → keine Benachrichtigung)

### Schritt 4 — Merge & Deduplizieren
Union aus Schritt 1 + Schritt 2, dedupliziert nach `web_user_id`.

---

## 7. Absage-Workflow (Phase 1): Detailablauf

```
┌─────────────────────────────────────────────────────────┐
│  Mitarbeiter: Kalender → Termin → "Absagen"             │
│                                                         │
│  Prüfung: is_binding=True? ✓                            │
│  Prüfung: Absagefrist eingehalten? ✓                    │
│  Eingabe: Begründung (optional)                         │
│  → POST /cancellations                                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Service: create_cancellation_request()                 │
│                                                         │
│  1. CancellationRequest(status=pending) → DB            │
│  2. Benachrichtigungs-Kreis berechnen                   │
│  3. CancellationNotificationRecipient[] → DB            │
│  4. InboxMessage → Dispatcher                           │
│  5. InboxMessage → jeder im Kreis                       │
│  6. Email → Dispatcher                                  │
│  7. Email → jeder im Kreis                              │
└─────────────────────────────────────────────────────────┘
```

### Absage zurückziehen:
```
Mitarbeiter: Kalender → abgesagter Termin → "Absage zurückziehen"
→ PATCH /cancellations/{id}/withdraw

Service:
1. CancellationRequest.status = withdrawn
2. gleiche Benachrichtigungen wie bei Erstellung
   (Typ: cancellation_withdrawn statt cancellation_new)
```

---

## 8. Übernahme-Workflow (Phase 2): Detailablauf

```
┌──────────────────────────────────────────────────────────┐
│  Mitarbeiter: Inbox → Absage-Karte → "Übernahme anbieten"│
│  → POST /cancellations/{id}/takeover-offers              │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│  Service: create_takeover_offer()                        │
│  1. TakeoverOffer(status=pending) → DB                   │
│  2. InboxMessage(takeover_offer_received) → Dispatcher   │
│  3. Email → Dispatcher                                   │
└──────────────────────────────────────────────────────────┘
                     │
                     │ Dispatcher bestätigt
                     ▼
┌──────────────────────────────────────────────────────────┐
│  Dispatcher: Absage-Detail → Übernahmeangebot → "Bestätigen"│
│  → POST /cancellations/{id}/takeover-offers/{oid}/accept │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│  Service: accept_takeover_offer()                        │
│                                                         │
│  Plan-Anpassung:                                         │
│  1. AvailDayAppointmentLink des alten Mitarbeiters       │
│     entfernen (für diesen Appointment)                   │
│  2. AvailDay für neuen Mitarbeiter an diesem Datum       │
│     suchen oder anlegen (s. Abschnitt 9)                 │
│  3. AvailDayAppointmentLink für neuen Mitarbeiter → DB   │
│                                                         │
│  Abschluss:                                              │
│  4. TakeoverOffer.status = accepted                      │
│  5. Andere TakeoverOffers für diese Absage → rejected    │
│  6. CancellationRequest.status = resolved                │
│  7. InboxMessage(cancellation_resolved) → alle im Kreis  │
│     + Absager + Übernehmer                              │
│  8. Emails entsprechend                                  │
└──────────────────────────────────────────────────────────┘
```

---

## 9. Automatische AvailDay-Erstellung (Phase 2)

Wenn der übernehmende Mitarbeiter keinen AvailDay für das Termin-Datum hat:

1. `ActorPlanPeriod` des Mitarbeiters für die betreffende PlanPeriod laden
2. Neuen `AvailDay` anlegen mit:
   - `date` = Termin-Datum
   - `actor_plan_period_id` = wie oben
   - `time_of_day_id` = TimeOfDay des Termins (vom Event)
3. Einrichtungs-/Mitarbeiterpräferenzen: alle auf **Normal** (Standard-Wert) setzen
   - `AvailDayLocPrefLink`-Einträge: preference = normal
   - `AvailDayPartnerPrefLink`-Einträge: preference = normal
4. Fixed Cast der übergeordneten CastGroup: `fixed_cast = None` für diesen AvailDay
   (d.h. keine speziellen Fixed-Cast-Constraints für diesen neuen AvailDay)
5. `AvailDayAppointmentLink` erstellen

---

## 10. Tausch-Workflow (Phase 2): Detailablauf

```
┌──────────────────────────────────────────────────────────┐
│  Mitarbeiter A: Kalender → Termin X → "Tausch anfragen"  │
│  Auswahl: Termin Y von Mitarbeiter B                     │
│  → POST /swap-requests                                   │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│  Service: create_swap_request()                          │
│  1. SwapRequest(status=pending) → DB                     │
│  2. InboxMessage(swap_request_received) → B + Dispatcher │
│  3. Email → B + Dispatcher                               │
└──────────────────────────────────────────────────────────┘
                     │
              B akzeptiert/lehnt ab
                     │
         ┌───────────┴───────────────┐
         │ akzeptiert                │ abgelehnt
         ▼                           ▼
┌────────────────────┐   ┌──────────────────────────────────┐
│ status =           │   │ status = rejected_by_target       │
│ accepted_by_target │   │ InboxMessage(swap_rejected) → A   │
│ InboxMessage       │   │ Email → A                        │
│ (swap_accepted)    │   └──────────────────────────────────┘
│ → Dispatcher       │
└──────┬─────────────┘
       │ Dispatcher bestätigt/lehnt ab
       │
  ┌────┴──────┐
  │ bestätigt │
  ▼           ▼ abgelehnt
┌───────────────────────────────────────────────────────┐
│  Service: confirm_swap()                              │
│  1. AvailDayAppointmentLink A↔X + B↔Y tauschen       │
│  2. SwapRequest.status = confirmed_by_dispatcher      │
│  3. InboxMessage(swap_confirmed) → A + B + Dispatcher │
│  4. Emails entsprechend                               │
└───────────────────────────────────────────────────────┘
```

---

## 11. Konfiguration: Absagefrist

### Vererbungs-Hierarchie
```
project_settings.cancellation_deadline_hours  (Standard: 48h)
    └── team_notification_settings.cancellation_deadline_hours
            (NULL = erbt von Project; Wert = überschreibt Project)
```

### Effektive Frist berechnen:
```python
def get_effective_deadline(team_id, session) -> int:
    team_setting = session.exec(
        select(TeamNotificationSettings).where(...team_id...)
    ).first()
    if team_setting and team_setting.cancellation_deadline_hours is not None:
        return team_setting.cancellation_deadline_hours
    project = team.plan_period.team.project  # via Team → Project
    project_setting = session.exec(
        select(ProjectSettings).where(...project_id...)
    ).first()
    return project_setting.cancellation_deadline_hours if project_setting else 48
```

### Frist-Prüfung:
```python
appointment_datetime = datetime.combine(event.date, time_of_day.start)
deadline_hours = get_effective_deadline(team_id, session)
if deadline_hours > 0:
    cutoff = appointment_datetime - timedelta(hours=deadline_hours)
    if datetime.utcnow() > cutoff:
        raise CancellationDeadlineExceeded(deadline_hours)
```

---

## 12. E-Mail-Service

Kein E-Mail-Service existiert bisher in der Web-API. Neu zu implementieren:

### `web_api/email/service.py`
```python
class EmailService:
    def send(self, to: list[str], subject: str, html_body: str) -> None: ...
```

**Provider:** SMTP (konfigurierbar via Settings: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`)  
**Fallback:** Console-Logger (für lokale Entwicklung: `EMAIL_BACKEND=console`)

### E-Mail-Templates (Jinja2, HTML):
| Template | Typ |
|---|---|
| `emails/cancellation_new.html` | Neue Absage (an Dispatcher + Kreis) |
| `emails/cancellation_withdrawn.html` | Absage zurückgezogen |
| `emails/cancellation_resolved.html` | Absage gelöst |
| `emails/takeover_offer_received.html` | Neues Übernahmeangebot (an Dispatcher) |
| `emails/takeover_accepted.html` | Übernahme bestätigt (an Beteiligte) |
| `emails/swap_request_received.html` | Tausch-Anfrage (an Ziel + Dispatcher) |
| `emails/swap_confirmed.html` | Tausch bestätigt |
| `emails/swap_rejected.html` | Tausch abgelehnt |

---

## 13. Web-API Endpoints

### Phase 1

| Method | Path | Beschreibung | Rolle |
|---|---|---|---|
| `POST` | `/cancellations` | Absage erstellen | employee |
| `PATCH` | `/cancellations/{id}/withdraw` | Absage zurückziehen | employee (eigene) |
| `GET` | `/cancellations` | Alle Absagen (eigene oder team) | employee/dispatcher |
| `GET` | `/cancellations/{id}` | Absage-Detail | employee/dispatcher |
| `GET` | `/inbox` | Inbox des aktuellen Users | alle |
| `PATCH` | `/inbox/{id}/read` | Nachricht als gelesen markieren | alle |
| `GET` | `/settings/project/{id}` | Projekt-Einstellungen | admin |
| `PUT` | `/settings/project/{id}` | Projekt-Einstellungen speichern | admin |
| `GET` | `/settings/team/{id}` | Team-Einstellungen | dispatcher |
| `PUT` | `/settings/team/{id}` | Team-Einstellungen speichern | dispatcher |

### Phase 2 (zusätzlich)

| Method | Path | Beschreibung | Rolle |
|---|---|---|---|
| `POST` | `/cancellations/{id}/takeover-offers` | Übernahmeangebot erstellen | employee |
| `POST` | `/cancellations/{id}/takeover-offers/{oid}/accept` | Übernahme bestätigen | dispatcher |
| `POST` | `/swap-requests` | Tausch-Anfrage stellen | employee |
| `POST` | `/swap-requests/{id}/accept` | Tausch akzeptieren (Ziel) | employee |
| `POST` | `/swap-requests/{id}/reject` | Tausch ablehnen (Ziel) | employee |
| `POST` | `/swap-requests/{id}/confirm` | Tausch bestätigen (Dispatcher) | dispatcher |
| `POST` | `/swap-requests/{id}/withdraw` | Tausch zurückziehen (Anfragender) | employee |
| `GET` | `/settings/location/{id}/circle` | Benachrichtigungs-Kreis anzeigen | dispatcher |
| `PUT` | `/settings/location/{id}/circle` | Benachrichtigungs-Kreis konfigurieren | dispatcher |

---

## 14. Web-Seiten (Templates)

### Phase 1

| Route | Template | Beschreibung |
|---|---|---|
| `GET /cancellations` | `cancellations/index.html` | Dispatcher: Absagen-Übersicht |
| `GET /cancellations/{id}` | `cancellations/detail.html` | Absage-Detail (Phase 2: + Übernahmeangebote) |
| `GET /inbox` | `inbox/index.html` | Inbox des aktuellen Users |
| HTMX-Partial | `cancellations/partials/cancel_form.html` | Absage-Formular im Kalender |
| HTMX-Partial | `inbox/partials/inbox_badge.html` | Ungelesene Nachrichten (Badge in Nav) |

### Phase 2 (zusätzlich)
| Route | Template | Beschreibung |
|---|---|---|
| `GET /swap-requests` | `swap_requests/index.html` | Eigene Tausch-Anfragen |
| `GET /settings/notifications` | `settings/notifications.html` | Dispatcher: Kreis pro Arbeitsort |

---

## 15. Betroffene Dateien

### Neue Dateien
| Datei | Inhalt |
|---|---|
| `web_api/email/service.py` | EmailService (SMTP + Console-Backend) |
| `web_api/email/templates/` | Jinja2 HTML-Email-Templates |
| `web_api/cancellations/router.py` | Phase 1 Endpoints |
| `web_api/cancellations/service.py` | Geschäftslogik inkl. Kreis-Berechnung |
| `web_api/cancellations/schemas.py` | Pydantic-Request/Response-Schemas |
| `web_api/inbox/router.py` | Inbox-Endpoints |
| `web_api/inbox/service.py` | InboxMessage-Logik |
| `web_api/settings/router.py` | Einstellungs-Endpoints |
| `web_api/settings/service.py` | Frist-Berechnung, Kreis-Konfiguration |
| `web_api/templates/cancellations/` | HTML-Templates |
| `web_api/templates/inbox/` | HTML-Templates |
| `alembic/versions/XXXX_add_cancellation_workflow.py` | DB-Migration |

### Geänderte Dateien
| Datei | Änderung |
|---|---|
| `web_api/main.py` | Neue Router registrieren |
| `web_api/config.py` | SMTP-Einstellungen ergänzen |
| `web_api/models/web_models.py` | Neue SQLModel-Klassen |
| `web_api/templates/base.html` | Inbox-Badge in Nav |
| `web_api/templates/employees/calendar.html` | "Absagen"-Button pro Termin |

---

## 16. Geschäftsregeln & Constraints

| # | Regel |
|---|---|
| BR-01 | Nur Appointments aus dem verbindlichen Plan (is_binding=True) können abgesagt werden |
| BR-02 | Pro Appointment kann max. 1 aktiver CancellationRequest existieren (status=pending) |
| BR-03 | Absage nur möglich, wenn Absagefrist nicht überschritten (Frist=0 → immer möglich) |
| BR-04 | Rückzug nur möglich, solange status=pending |
| BR-05 | Mitarbeiter sieht nur eigene Absagen; Dispatcher sieht alle Absagen seines Teams |
| BR-06 | CancellationRequest wird nie gelöscht (Audit-Trail) |
| BR-07 | Übernahmeangebot nur möglich, wenn man im Benachrichtigungs-Kreis ist |
| BR-08 | Tausch-Anfrage: Quelle und Ziel-Termin müssen in derselben PlanPeriod liegen |
| BR-09 | Bei Übernahme-Bestätigung: alle anderen TakeoverOffers derselben Absage → rejected |
| BR-10 | Email-Versand erfolgt async (APScheduler oder Background Task) — kein Blockieren der Response |

---

## 17. Desktop-Integration (Phase 2)

### Prinzip: API-first

Der Desktop-Klient ruft für alle Aktionen dieses Workflows die Web-API-Endpoints auf, statt
direkt auf die DB zuzugreifen. Dies ist der erste Schritt der mittelfristigen Umstellung des
Desktop-Klienten auf eine API-basierte Architektur.

```
Desktop-Klient                    Web-API
      │                               │
      │  POST /cancellations/{id}/    │
      │  takeover-offers/{oid}/accept │
      │──────────────────────────────►│
      │                               │  Plan-Anpassung (DB)
      │                               │  Inbox-Einträge (DB)
      │                               │  E-Mail-Versand (SMTP)
      │◄──────────────────────────────│
      │  200 OK                       │
```

**Konsequenz:** Alle Benachrichtigungen (Inbox + E-Mail) laufen immer durch dieselbe
Web-API-Logik — unabhängig davon, ob ein Dispatcher über die Web-Oberfläche oder den
Desktop-Klienten handelt. Kein Risiko von doppelten Benachrichtigungen.

### Neue Desktop-Komponenten (Phase 2)

| Komponente | Beschreibung |
|---|---|
| `gui/web_api_client.py` | Dünner HTTP-Client (httpx oder requests) mit Base-URL aus Settings + JWT-Auth |
| `gui/frm_cancellations.py` | Dialog/Fenster: Liste offener Absagen mit Übernahmeangeboten |
| Menüeintrag in `main_window.py` | „Absagen" im Schedule-Menü |

### Authentifizierung Desktop → API

Der Desktop-Klient authentifiziert sich gegenüber der Web-API mit einem
**Service-Account-JWT** (Rolle: `dispatcher`) oder einem dedizierten
`admin`/`dispatcher`-Token aus den Desktop-Settings. Der genaue Mechanismus
wird im Implementierungsplan festgelegt.

---

## 18. Out of Scope

- Web-Endpoint zum Setzen von `Plan.is_binding` (bleibt Desktop-only)
- Push-Notifications (Browser)
- Absagen historischer Planperioden (vergangene Termine)
- Automatische Absage bei Krankheitsmeldung
- Dispatcher kann Absage ablehnen (kein `rejected`-Status für Phase 1+2)
- Mobile App
- Vollständige Umstellung des Desktop-Klienten auf API-first (nur dieser Workflow als erster Schritt)

---

## 18. Verifikation (End-to-End)

1. **Absage-Frist**: Dispatcher setzt Frist auf 1h, Mitarbeiter versucht Termin heute abzusagen → Fehlermeldung
2. **Absage-Flow**: Mitarbeiter sagt Termin ab → Dispatcher und Kreis erhalten Email + Inbox
3. **Kreis-Berechnung**: Mitarbeiter mit bestehendem Appointment an diesem Tag + CombLoc → korrekt ein-/ausgeschlossen
4. **Rückzug**: Mitarbeiter zieht Absage zurück → Kreis wird erneut benachrichtigt; Termin erscheint wieder im Kalender
5. **Übernahme (Phase 2)**: Mitarbeiter macht Angebot → Dispatcher bestätigt → AvailDay wird angelegt → Plan korrekt angepasst
6. **Tausch (Phase 2)**: A fragt B → B akzeptiert → Dispatcher bestätigt → Appointments korrekt getauscht
7. **Inbox-Badge**: Ungelesene Nachrichten erscheinen als Badge in der Nav
