# Web-API Architektur — hcc_plan

**Datum:** 2026-03-22
**Status:** Planung

---

## Überblick

Ziel ist der Aufbau einer vollständigen Web-Plattform als Erweiterung des bestehenden Desktop-Planungstools. Die Plattform teilt dieselbe PostgreSQL-Datenbank mit dem Desktop-Tool und bietet Mitarbeitern, Dispatchern, Admins und Buchhaltern rollenbasierte Web-Oberflächen.

---

## Tech-Stack

| Komponente       | Technologie                              |
|------------------|------------------------------------------|
| Backend / API    | FastAPI (Python) — neue, eigenständige App |
| Frontend         | Jinja2 + HTMX (server-side rendering)   |
| Kalender-UI      | FullCalendar.js (nur diese Komponente)   |
| Datenbank        | PostgreSQL (render.com Managed)          |
| ORM / Migration  | SQLModel + Alembic (wie Desktop-Tool)    |
| Auth             | OAuth2 Password Flow + JWT               |
| E-Mail           | Abstrahierter Service (Provider TBD)     |
| Scheduling       | APScheduler (AsyncIOScheduler + SQLAlchemyJobStore auf PostgreSQL) |
| Deployment       | render.com (Web Service + PostgreSQL)    |

---

## Deployment-Architektur

```
render.com
├── Web Service (FastAPI)
│   ├── Jinja2-Templates (HTMX-enhanced)
│   ├── REST-Endpoints (interne API für HTMX)
│   └── BackgroundTasks (E-Mail-Notifications)
└── PostgreSQL (Managed Database)
    ├── Bestehende Tabellen (Desktop-Tool, ~60 Tabellen)
    └── Neue Web-Tabellen (web_user, cancellation_request, ...)
```

Das Desktop-Planungstool verbindet sich nach der SQLite→PostgreSQL-Migration ebenfalls direkt mit dieser Datenbank.

---

## Projektstruktur (Monorepo + uv Workspaces)

### Entscheidung: Monorepo

Die Web-API wird **im bestehenden Repo** entwickelt, nicht in einem separaten Repository.

**Begründung:** `database/models.py` und `alembic/` sind zwischen Desktop-Tool und Web-API geteilt. Eine einzige Quelle für das DB-Schema ist zwingend — zwei Repos würden unweigerlich zu Drift führen (unterschiedliche Model-Versionen, doppelte Migration-Historien).

### uv Workspaces

Um trotz Monorepo unabhängige Abhängigkeiten zu ermöglichen (PySide6 nicht im Web-Environment, FastAPI nicht im Desktop-Environment), wird **uv workspaces** eingesetzt. Das folgende Layout beschreibt die **Zielstruktur** nach dem Workspace-Umbau (aktuell liegen alle Dependencies in der Root-`pyproject.toml` und `gui/` hat kein eigenes `pyproject.toml`):

```
hcc_plan_db_playground/          ← Workspace Root
├── pyproject.toml               ← [tool.uv.workspace] + gemeinsame Deps (database, alembic)
├── database/                    ← geteilt (models.py, db_services/)
├── alembic/                     ← geteilt (eine Migration-History für eine DB)
├── gui/                         ← Desktop-Tool
│   └── pyproject.toml           ← PySide6, etc. — nur hier
├── web_api/                     ← Web-API
│   └── pyproject.toml           ← FastAPI, uvicorn, APScheduler, etc. — nur hier
└── ...
```

Die Root-`pyproject.toml` deklariert die Workspace-Members:

```toml
[tool.uv.workspace]
members = ["gui", "web_api"]
```

Sowohl `gui` als auch `web_api` greifen auf den gemeinsamen `database`-Code zu. Wie genau dieser referenziert wird (eigenes Workspace-Member mit `pyproject.toml` oder einfacher `src`-Pfad), ist noch offen — siehe Offene Entscheidungen.

### render.com Deployment

render.com unterstützt Monorepos nativ: Im Web-Service-Setup wird **Root Directory** auf `web_api/` gesetzt. Damit bezieht sich der Build-Context nur auf das Web-API-Sub-Package — PySide6 und Desktop-spezifische Dependencies werden nie installiert.

---

## Rollen-Modell

| Rolle        | Beschreibung                                                    |
|--------------|-----------------------------------------------------------------|
| `admin`      | Volle Systemkontrolle, User-Verwaltung, Rollen-Vergabe         |
| `dispatcher` | Planungsperioden erstellen/bearbeiten, Besetzungsfreigaben      |
| `employee`   | Eigener Kalender, Verfügbarkeit, Absagen melden                 |
| `accountant` | Nur-Lese-Zugriff auf abrechnungsrelevante Daten                 |

Rollen werden als Claims im JWT gespeichert und per FastAPI-Dependency in jedem Endpoint geprüft.

---

## Modul-Struktur (App-Layout)

```
web_api/
├── main.py                  # FastAPI-App, Router-Registrierung
├── config.py                # Settings (Pydantic BaseSettings, .env)
├── dependencies.py          # Globale FastAPI-Dependencies (get_session, current_user)
│
├── auth/                    # OAuth2 + JWT
│   ├── router.py            # /auth/login, /auth/refresh, /auth/logout
│   ├── service.py           # Token-Generierung, Passwort-Hashing
│   └── dependencies.py      # require_role(), get_current_user()
│
├── employees/               # Mitarbeiter-Ansichten
│   ├── router.py            # /employees/calendar, /employees/appointments
│   ├── service.py
│   └── templates/
│
├── scheduling/              # Planungsperioden, Termine, Besetzungen (Read-Only für Web)
│   ├── router.py
│   └── service.py
│
├── availability/            # Verfügbarkeits-Einträge
│   ├── router.py            # /availability/
│   ├── service.py
│   └── templates/
│
├── cancellations/           # Absagen + Freiwilligen-Workflow
│   ├── router.py
│   ├── service.py
│   └── templates/
│
├── notifications/           # E-Mail-Service (abstrakt)
│   ├── base.py              # AbstractEmailService
│   ├── smtp.py              # SMTPEmailService
│   └── sendgrid.py          # SendGridEmailService (optional)
│
├── scheduler/               # Terminierte Benachrichtigungen (APScheduler)
│   ├── setup.py             # AsyncIOScheduler + SQLAlchemyJobStore (PostgreSQL)
│   └── jobs.py              # Job-Definitionen (Deadline-Erinnerungen etc.)
│
├── dispatcher/              # Dispatcher-Bereich
│   ├── router.py            # /dispatcher/periods, /dispatcher/assignments
│   ├── service.py
│   └── templates/
│
├── admin/                   # Admin-Bereich
│   ├── router.py            # /admin/users, /admin/teams, /admin/locations
│   ├── service.py
│   └── templates/
│
├── accounting/              # Buchhaltungs-Schnittstelle
│   ├── router.py            # /accounting/export
│   ├── service.py
│   └── templates/
│
├── models/                  # Neue Web-spezifische DB-Tabellen
│   └── web_models.py        # WebUser, CancellationRequest, VolunteerApplication, ...
│                            # Ort TBD — siehe Offene Entscheidungen
│
└── templates/               # Basis-Templates (base.html, nav, auth-pages)
```

---

## Neue Datenbank-Tabellen (Web-spezifisch)

Diese Tabellen ergänzen das bestehende Schema, ohne es zu verändern:

### `web_user`
Verknüpft einen Web-Login (E-Mail + Passwort-Hash) mit dem bestehenden `person`-Eintrag.

```
web_user
├── id (UUID, PK)
├── person_id (FK → person.id, UNIQUE)  ← Verknüpfung zum Kern-Modell
├── email (UNIQUE, NOT NULL)
├── hashed_password
├── role (Enum: admin, dispatcher, employee, accountant)
├── is_active (bool)
├── created_at
└── last_modified
```

### Dispatcher ↔ Teams: keine neue Tabelle nötig

Das Kern-Modell enthält bereits `team.dispatcher_id (FK → person.id, N:1)`.
Ein Dispatcher kann mehrere Teams verwalten; ein Team hat genau einen Dispatcher.

Die Verknüpfung im Web-System erfolgt über die vorhandene Kette:
```
web_user.person_id → person.id ← team.dispatcher_id
```

Die `require_scope_access`-Dependency prüft damit:
```python
team.dispatcher_id == current_user.person_id
```

**Keine neue DB-Tabelle erforderlich.**

---

### `cancellation_request`
Wenn ein Mitarbeiter einen geplanten Termin absagt.

```
cancellation_request
├── id (UUID, PK)
├── appointment_id (FK → appointment.id)
├── requested_by_id (FK → web_user.id)
├── reason (Text, optional)
├── status (Enum: pending, approved, rejected)
├── created_at
└── resolved_at
```

### `volunteer_application`
Wenn ein Mitarbeiter sich auf einen abgesagten Termin meldet.

```
volunteer_application
├── id (UUID, PK)
├── cancellation_request_id (FK → cancellation_request.id)
├── applicant_id (FK → web_user.id)
├── status (Enum: pending, accepted, rejected)
├── dispatcher_note (Text, optional)
└── created_at
```

### `period_note`
Anmerkungen eines Mitarbeiters zu einer ganzen Planungsperiode.

```
period_note
├── id (UUID, PK)
├── plan_period_id (FK → plan_period.id)
├── author_id (FK → web_user.id)
├── note (Text)
├── created_at
└── last_modified
```

---

## Kernfunktionen je Modul

### Mitarbeiter (`/employees`)
- Kalender-Ansicht: eigene Termine der aktuellen/nächsten Planungsperiode
- Filter: nach Kategorie (Skill, Standort, Tageszeit), Freitext-Suche
- Termin-Detail: Anmerkungen lesen/schreiben
- Verfügbarkeit eintragen (delegiert an `/availability`)
- Termin absagen (delegiert an `/cancellations`)

### Verfügbarkeit (`/availability`)
- Kalender-Ansicht zur Verfügbarkeits-Eingabe
- Anmerkungen je Verfügbarkeitstag
- Anmerkungen zur gesamten Planungsperiode (`period_note`)

### Absagen & Freiwillige (`/cancellations`)
- Absage einreichen → E-Mail-Benachrichtigung an betroffene Mitarbeiter
- Freiwillige melden sich → E-Mail-Benachrichtigung an Dispatcher
- Dispatcher gibt neue Besetzung frei → Plan im Desktop-Tool wird aktualisiert

### Dispatcher (`/dispatcher`)
- Planungsperioden anlegen, bearbeiten, löschen
- Offene Freiwilligen-Meldungen einsehen und freigeben

### Admin (`/admin`)
- Neue Mitarbeiter registrieren (erstellt `web_user` + verknüpft mit `person`)
- Teams + Standorte zuweisen
- Rollen vergeben

### Buchhaltung (`/accounting`)
- Abrechnungsrelevante Daten als CSV/Excel exportieren
- Filter: Zeitraum, Team, Standort

---

## Schnittstelle zum Desktop-Tool

**Strategie: Geteilte PostgreSQL-Datenbank**

- Desktop-Tool und Web-API teilen dieselbe DB (kein doppeltes Datenhalten)
- Desktop-Tool schreibt Planungsdaten → Web-API liest sie (Kalender-Ansicht)
- Web-API schreibt Verfügbarkeiten → Desktop-Tool liest sie (Solver-Input)
- Keine direkte API-zu-API-Kommunikation nötig

**Voraussetzung:** SQLite → PostgreSQL-Migration im Desktop-Tool muss abgeschlossen sein.

---

## E-Mail-Service (abstrakt)

```python
# notifications/base.py
class AbstractEmailService(ABC):
    @abstractmethod
    async def send(self, to: list[str], subject: str, body: str) -> None: ...
```

Konkrete Implementierungen (`SMTPEmailService`, `SendGridEmailService`) werden per Dependency Injection eingebunden. Provider-Wechsel erfordert keine Änderung am aufrufenden Code.

---

## Terminierte Benachrichtigungen (APScheduler)

Für Deadline-Erinnerungen und andere zeitgesteuerte Notifications wird **APScheduler** mit dem `AsyncIOScheduler` eingesetzt.

### Warum SQLAlchemyJobStore?
render.com startet den Web Service bei jedem Deploy neu. Ohne persistenten Job-Store gehen alle geplanten Jobs dabei verloren. Der `SQLAlchemyJobStore` speichert Jobs direkt in PostgreSQL — sie überleben Neustarts und sind in der DB einsehbar.

### Integration in FastAPI (lifespan)

```python
# scheduler/setup.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

def create_scheduler(db_url: str) -> AsyncIOScheduler:
    jobstores = {"default": SQLAlchemyJobStore(url=db_url)}
    return AsyncIOScheduler(jobstores=jobstores)

# main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()
```

### Geplante Job-Typen

| Job | Auslöser | Beschreibung |
|-----|----------|--------------|
| `availability_deadline_reminder` | X Tage vor Deadline | E-Mail an Mitarbeiter, die noch keine Verfügbarkeit eingetragen haben |
| `open_question_reminder` | Konfigurierbar | Erinnerung bei offenen Rückmeldefragen |
| `cancellation_deadline_reminder` | X Stunden vor Termin | Letzte Erinnerung an unbesetzte abgesagte Termine |

### DB-Tabellen für Dispatcher-konfigurierbare Benachrichtigungen

Zwei Tabellen: **Templates** (wiederverwendbare Vorlagen) und **geplante Jobs** (konkrete Ausführung pro Planungsperiode).

#### Scope-Konzept: Wer darf was verwalten?

| Scope | Erstellt/verwaltet von | Empfänger |
|---|---|---|
| `project` | **Admin** | Alle Mitarbeiter projektübergreifend |
| `team` | **Dispatcher** (nur eigene Teams) | Mitarbeiter des jeweiligen Teams |

Die Zugriffskontrolle wird als FastAPI-Dependency umgesetzt (`require_scope_access`), sodass ein Dispatcher keine projektweiten Benachrichtigungen anlegen oder bearbeiten kann.

#### `notification_template`
Wiederverwendbare Vorlagen mit anpassbarem Betreff und Text.
Unterstützt Platzhalter wie `{name}`, `{deadline}`, `{plan_period}`.

```
notification_template
├── id (UUID, PK)
├── name (VARCHAR)                    ← z.B. "Verfügbarkeits-Erinnerung"
├── subject (VARCHAR)                 ← E-Mail-Betreff (mit Platzhaltern)
├── body (Text)                       ← E-Mail-Text (mit Platzhaltern)
├── type (Enum: availability_deadline, open_question, cancellation, ...)
├── scope (Enum: project, team)       ← project → nur Admin; team → Dispatcher
├── team_id (FK → team.id, nullable)  ← gesetzt wenn scope=team
├── created_by_id (FK → web_user.id)
├── created_at
└── last_modified
```

#### `scheduled_notification`
Konkret geplante Benachrichtigung, verknüpft mit einer Planungsperiode.
Die `apscheduler_job_id` verknüpft diesen Eintrag mit dem laufenden APScheduler-Job.

```
scheduled_notification
├── id (UUID, PK)
├── template_id (FK → notification_template.id)
├── plan_period_id (FK → plan_period.id)
├── trigger_at (DateTime)             ← Frei konfigurierbar (Admin/Dispatcher)
├── scope (Enum: project, team)       ← übernommen vom Template, zur Laufzeit geprüft
├── team_id (FK → team.id, nullable)  ← gesetzt wenn scope=team
├── apscheduler_job_id (VARCHAR)      ← Referenz auf den APScheduler-Job
├── status (Enum: scheduled, sent, cancelled)
├── created_by_id (FK → web_user.id)
├── created_at
└── sent_at (nullable)
```

#### Ablauf: Dispatcher ändert Benachrichtigungszeitpunkt

```
Dispatcher ändert trigger_at in UI
    → PATCH /dispatcher/notifications/{id}
        → DB aktualisieren
        → scheduler.reschedule_job(apscheduler_job_id, trigger=DateTrigger(trigger_at))

App-Start nach Deploy (Resync)
    → Alle scheduled_notifications mit status=scheduled aus DB laden
    → Fehlende Jobs im Scheduler neu anlegen (idempotent)
```

---

## Entwicklungsreihenfolge

| Phase | Inhalt                                               | Abhängigkeit        |
|-------|------------------------------------------------------|---------------------|
| 1     | SQLite → PostgreSQL-Migration (Desktop-Tool)         | —                   |
| 1b    | uv Workspace-Setup: Root-`pyproject.toml` umbauen, `gui/pyproject.toml` + `web_api/pyproject.toml` erstellen | Phase 1 |
| 2     | Neue FastAPI-App: Grundstruktur + Config + DB-Setup  | Phase 1b            |
| 3     | Auth: OAuth2 + JWT + Rollen-Middleware               | Phase 2             |
| 4     | Mitarbeiter-Kalender (Lesen, Filtern, Suchen)        | Phase 3             |
| 5     | Verfügbarkeiten + Anmerkungen                        | Phase 3             |
| 6     | Absagen + Freiwilligen-Workflow + E-Mail             | Phase 4 + 5         |
| 7     | APScheduler: Deadline-Erinnerungen                   | Phase 6             |
| 8     | Dispatcher-Bereich                                   | Phase 6             |
| 9     | Admin-Bereich                                        | Phase 3             |
| 10    | Buchhaltungs-Export                                  | Phase 4             |

---

## Offene Entscheidungen

- [x] ~~Neues Repo oder Monorepo?~~ → **Monorepo** (geteilte `database/models.py` + `alembic/`)
- [ ] Genaue Package-Struktur für geteilten `database/`-Code: Soll `database/` ein eigenes uv-Workspace-Member sein (mit eigenem `pyproject.toml`) oder als einfaches Verzeichnis ohne eigene Package-Deklaration referenziert werden?
- [ ] E-Mail-Provider: SMTP (Firmenmailserver) oder SendGrid?
- [x] ~~Soll das Desktop-Tool per direktem DB-Zugriff oder per REST-API-Call Daten schreiben?~~ → **Direkter DB-Zugriff** (geteilte PostgreSQL-DB, keine API-zu-API-Kommunikation)
- [ ] Wo leben die neuen Web-spezifischen DB-Models (`web_user`, `cancellation_request` etc.)? In `database/models.py` (Alembic sieht sie automatisch, eine Quelle) oder in `web_api/models/` (erfordert erweitertes `target_metadata` in `alembic/env.py`)?
- [ ] Welche konkreten Felder braucht die Buchhaltungs-Schnittstelle?
- [ ] Soll es einen separaten Webhook/Notification-Kanal geben (z.B. Push-Notifications im Browser)?
