# PRD: Teams & Standorte (Admin-Verwaltung)

**Datum:** 2026-05-14 (aktualisiert 2026-05-15)
**Status:** Phase 1.0–1.5 umgesetzt; Plan-Konfig-Pfad (Phase 1.2) am 2026-05-15 wieder zurueckgebaut
**Bezug:** `database/models.py` (`Team`, `LocationOfWork`, `Address`, `TeamActorAssign`, `TeamLocationAssign`), `web_api/admin/`, `web_api/dashboard/router.py` (Tile `Teams & Standorte`)

> **Architektur-Leitentscheidung (Stand 2026-05-15):** Die Web-UI uebernimmt **organisatorische** Stellschrauben (Team-/Standort-Stammdaten, Adressen, Personen-/Standort-Zuordnungen, Dispatcher-Wechsel). **Plan-Intelligenz** (Besetzungsstaerke, TimesOfDay, FixedCast, SkillGroups auf allen Ebenen) bleibt vollstaendig im Desktop. Diese Trennlinie wurde am 2026-05-15 nach kurzer Plan-Konfig-Implementation auf Location-Ebene bewusst gezogen: konsistente Verantwortlichkeit ueber alle vier Konfig-Ebenen statt punktueller Teil-Migration. Eine eventuelle spaetere Voll-Portierung des Desktop-Editor-Pfads bleibt eigenstaendig zu planen.

---

## 1. Problem

Die Tile **„Teams & Standorte"** auf dem Admin-Dashboard verlinkt auf `/admin/teams`, eine Route, die heute nicht existiert. Die zugrundeliegende Organisationsstruktur (Teams, Standorte, Personen-Zuordnungen, Dispatcher-Verantwortung) lässt sich aktuell ausschließlich im Desktop-Client (`FrmMasterData`) pflegen. Das hat drei konkrete Folgen:

- **Administratoren ohne Desktop-Zugang** können neue Standorte/Teams nicht selbst anlegen.
- **Dispatcher** können einfache Plan-Konfigurations-Felder (Default-Besetzungsstärke, Fixed-Cast) nicht web-basiert ändern — sie sind auf den Desktop angewiesen oder müssen den Admin bitten.
- Die strikte Trennung zwischen administrativen Stammdaten (Organisationsstruktur) und operativen Plan-Konfigurations-Werten ist im Desktop nicht durchgesetzt; jeder mit FrmMasterData-Zugriff kann alles ändern.

---

## 2. Lösungsüberblick

Eine neue Web-UI unter `/admin/teams` mit zwei Hauptbereichen:

```
/admin/teams
├── Teams (Liste mit Detail-Drawer)
│   • Name, Dispatcher, Anzahl Mitarbeiter, Anzahl Standorte
│   • Detail: Stammdaten + Personen-Zuordnungen + Standort-Zuordnungen
│
└── Standorte (Liste mit Detail-Drawer)
    • Name, Adresse, Team-Zugehörigkeit(en), nr_actors
    • Detail: Stammdaten (Name + Adresse) + Soft-/Hard-Delete
```

`/admin/teams` ist **strikt admin-only**. Beide Bereiche teilen sich denselben Detail-Drawer.

**Dashboard-Zugang:** Admins erreichen die Seite über die bestehende Tile `Teams & Standorte` im Admin-Block. Es gibt **kein Dispatcher-Tile** auf `/admin/teams` — Dispatcher pflegen Plan-Konfig am Desktop.

Zuordnungen (Person↔Team, Standort↔Team) werden als **zeitabschnittsbasierte Mitgliedschaften** abgebildet, konsistent mit dem bestehenden Datenmodell (`TeamActorAssign.start/end`, `TeamLocationAssign.start/end`). Die UI abstrahiert das primär auf den heutigen Zustand, erlaubt aber explizites Future-Dating und Future-Canceling.

---

## 3. Scope

### In Scope (Phase 1)
- Liste + Filter (aktiv/inaktiv, Suche) für Teams und Standorte
- CRUD für **Team**: anlegen, umbenennen, Dispatcher zuweisen/wechseln, Notes pflegen, soft-deleten
- CRUD für **Standort**: anlegen, umbenennen, Adresse pflegen, soft-deleten
- Personen-Zuordnung zu Teams (M:N, zeitabschnittsbasiert, Multi-Team erlaubt)
- Standort-Zuordnung zu Teams (M:N, zeitabschnittsbasiert)
- Adress-Autocomplete (Vorschlag bestehender Adressen während Inline-Eingabe)
- Hard-Delete für soft-gelöschte Einträge (mit Name-Bestätigung)
- Strikte Admin-Beschränkung — keine Dispatcher-Pfade

### Out of Scope (bewusste Auslassungen)
- **Plan-Konfig auf Standort-Ebene** (`nr_actors`, `fixed_cast`, `fixed_cast_only_if_available`, Plan-`notes`) — **bleibt Desktop**. Eine kurzlebige Implementierung in Phase 1.2 (Commits `3f66a3a`, `20dea3d`, `7b3b673`) wurde am 2026-05-15 wieder zurueckgebaut: konsistente Trennlinie zwischen Plan-Intelligenz (Desktop) und Organisation (Web) statt punktueller Teil-Migration.
- **`notification_circle_restricted`** — lebt in `/dispatcher/notification-circles`, dort ist auch der Empfängerkreis-Pool definiert.
- **Default-TimeOfDays** pro Standort — bleibt Desktop (`DlgTimeOfDay`).
- **`CombinationLocationsPossible`** — bleibt Desktop (`DlgCombLocPossibleEditList`).
- **`ActorLocationPref`** — bleibt Desktop.
- **`SkillGroup` pro Standort** — bleibt Desktop.
- **`ExcelExportSettings` pro Team** — separate Feature-Schiene (siehe `project_excel_settings_copy_on_write_todo`).
- **Multi-Projekt-Verwaltung** — System ist Single-Tenant; das aktuelle Project wird via `get_admin_project()` gelöst.

### Phasen-Empfehlung
1. **Phase 1.0** – Read-only-Liste + Detail-Drawer (Teams und Standorte sichtbar) ✓
2. **Phase 1.1** – Stammdaten-CRUD (Admin-Felder) ✓
3. ~~**Phase 1.2** – Plan-Konfig-CRUD (Dispatcher-Felder)~~ **verworfen 2026-05-15**
4. **Phase 1.3** – Zuordnungen (Personen↔Team, Standort↔Team) mit Future-Dating/Canceling ✓
5. **Phase 1.4** – Adress-Autocomplete ✓
6. **Phase 1.5** – Hard-Delete-Pfad aus Inaktiv-Filter ✓

---

## 4. User Stories

### US-01 — Admin legt neues Team an
Als Admin möchte ich ein neues Team mit Name und Dispatcher anlegen, damit neue Organisationseinheiten ohne Desktop-Client einsatzbereit werden.

**Akzeptanzkriterien:**
- Pflichtfelder: `name` (max. 50 Zeichen, eindeutig pro Projekt). Notes optional.
- Dispatcher-Auswahl: Dropdown beschränkt auf Personen mit `WebUserRole.dispatcher`. Auswahl optional bei Anlage; das Team kann initial ohne Dispatcher angelegt werden.
- Validierung: Duplikat-Namen werden serverseitig abgelehnt mit klarer Fehlermeldung; UniqueConstraint `(project_id, name)`.
- Nach Anlage: neues Team erscheint sofort in der Liste, Detail-Drawer öffnet sich.

### US-02 — Admin legt neuen Standort an
Als Admin möchte ich einen neuen Standort mit Name und Adresse anlegen, damit er für die Team-Zuordnung verfügbar ist.

**Akzeptanzkriterien:**
- Pflichtfelder: `name` (max. 50 Zeichen, eindeutig pro Projekt).
- Optional bei Anlage: Adresse (mit Autocomplete aus bestehenden Adressen), `nr_actors` (Default: 2).
- Validierung: Duplikat-Namen serverseitig abgelehnt (UniqueConstraint `(project_id, name)`).
- Beim Anlegen werden Default-TimeOfDays vom Project geerbt — Mechanismus über `before_flush`-Listener (siehe Memory `feedback_orm_pass_relations_not_fk`); der Endpoint muss daher die `Project`-Relation als Objekt setzen, nicht nur die FK-ID. Ohne diesen Schritt entstehen Plan-Period-Erstellungs-Fehler später.

### US-03 — Admin weist einem Team einen Dispatcher zu
Als Admin möchte ich den Dispatcher eines Teams ändern, damit Personalwechsel in der Verantwortlichkeit abgebildet werden.

**Akzeptanzkriterien:**
- Auswahl im Team-Detail-Drawer; Dropdown beschränkt auf Personen mit `WebUserRole.dispatcher`.
- Bei `dispatcher_id = NULL` zeigt das UI eine **gelbe Warn-Markierung** „Kein Dispatcher zugewiesen".
- Wechsel ist sofort wirksam, keine Übergangs-Historie nötig (im Gegensatz zu Mitgliedschaften ist Dispatcher-Verantwortung ein punktueller Zustand).
- Unter dem Dropdown ein Hinweis-Link: „Person fehlt? Erst Web-Zugang anlegen und Dispatcher-Rolle vergeben → `/admin/users`." Damit ist der einzige Pfad zur Dispatcher-Erweiterung klar dokumentiert.

### US-04 — Admin weist Personen einem Team zu (mit optionalem Start-Datum)
Als Admin möchte ich Personen einem Team zuordnen, optional mit zukünftigem Start-Datum, damit personelle Übergaben planbar werden.

**Akzeptanzkriterien:**
- Personen-Selector zeigt alle Personen des Projekts (inkl. Hinweis auf aktuell aktive Team-Mitgliedschaften — „Anna ist aktuell in: Team Hamburg").
- Mehrfach-Mitgliedschaft ist erlaubt: Person darf gleichzeitig in mehreren Teams aktiv sein.
- Default: `start = heute`, `end = NULL` (offene Mitgliedschaft).
- Optional: Future-Dating — Admin kann `start` auf ein zukünftiges Datum setzen.
- Konfliktprüfung: Wenn ein bestehender Eintrag (gleiche Person × gleiches Team) noch offen ist, wird der neue Eintrag abgelehnt mit Vorschlag „Bestehende Mitgliedschaft beenden?".
- Bestätigung schreibt einen neuen `TeamActorAssign`-Datensatz.

### US-05 — Admin beendet eine Team-Mitgliedschaft (auch zukünftig)
Als Admin möchte ich eine Team-Mitgliedschaft zu einem bestimmten Datum beenden, auch in der Zukunft (z. B. zum Monatsende), damit Wechsel im Voraus geplant werden können.

**Akzeptanzkriterien:**
- Aus dem Team-Detail erreichbar pro Personen-Zeile: Button „Mitgliedschaft beenden".
- Eingabefeld für `end`-Datum mit Default „heute"; freie Wahl zwischen heute und Zukunft.
- Validierung: `end > start` erforderlich; Vergangenheit unterhalb `start` wird abgelehnt.
- Nach dem Setzen bleibt der `TeamActorAssign`-Eintrag bestehen (kein DELETE). Die Person verschwindet aus der "aktiven Mitgliederliste" ab dem `end`-Datum.
- Ein zukünftiges `end` ist **revertierbar**: bis das Datum eintritt, kann das `end`-Feld zurück auf NULL gesetzt werden.

### US-06 — Admin weist Standorte einem Team zu (mit Future-Dating)
Als Admin möchte ich Standorte einem Team zuordnen, optional mit zukünftigem Start-Datum, damit ich z. B. einen neuen Standort einem Team bereits vorab zuweisen kann.

**Akzeptanzkriterien:**
- Analog zu US-04, aber mit `TeamLocationAssign`-Datensätzen.
- Mehrfach-Zuordnung erlaubt: ein Standort kann mehreren Teams gleichzeitig zugeordnet sein (das ist real für geteilte Häuser).
- Default `start = heute`, `end = NULL`. Future-Dating optional.

### US-07 — Admin beendet eine Standort-Team-Zuordnung
Wie US-05, aber für Standort↔Team.

### US-08 — Admin bearbeitet Name und Adresse eines Standorts
Als Admin möchte ich Name und Adresse eines Standorts ändern, damit Umbenennungen und Umzüge gepflegt werden.

**Akzeptanzkriterien:**
- Felder im Standort-Detail-Drawer: `name`, `address.street`, `address.postal_code`, `address.city`, `address.name` (interne Bezeichnung, optional).
- Adress-Autocomplete: während der Eingabe in `street` oder `name` werden bestehende Adress-Zeilen des Projekts als Vorschläge angeboten (HTMX-Live-Suche analog zu `viewer/persons`, commit `fcf36fe`). Pool: alle nicht-soft-gelöschten `Address`-Zeilen des Projekts, unabhängig davon, ob sie aktuell an einem Standort, einer Person oder einem EmployeeEvent hängen.
- Auswahl eines Vorschlags **kopiert die Adress-Felder vor**; bei Speichern wird **immer eine neue `Address`-Zeile** angelegt und mit dem Standort verknüpft. Adressen werden nicht zwischen Datensätzen geteilt — das hält die Back-Relation `Address.location_of_work` (Optional, singular, `database/models.py:351`) ORM-konsistent 1:1.
- Manuelle Eingabe ohne Vorschlag verhält sich identisch: neue `Address`-Zeile, neue Verknüpfung.
- Modifikation an einer bestehenden Adresse desselben Standorts: in-place Update der vorhandenen `Address`-Zeile (kein Sharing-Risiko, da 1:1).
- Bei Löschung der Address-Verknüpfung (Adresse-Felder werden geleert): `LocationOfWork.address_id = NULL`. Die alte `Address`-Zeile bleibt für die Autocomplete-Pool-Suche stehen, bis sie projektweit aufgeräumt wird (siehe Memory `project_general_db_cleanup_planned`).

### ~~US-09 — Dispatcher bearbeitet Plan-Konfig-Felder eines Standorts~~ (verworfen 2026-05-15)

**Status:** umgesetzt in `3f66a3a` / `20dea3d` / `7b3b673`, am **2026-05-15** wieder zurueckgebaut.

**Begruendung des Rueckbaus:** Plan-Konfig existiert auf vier Ebenen (Projekt, Location, PlanPeriod, PlanPeriod-Location). Nur die Location-Ebene ins Web zu portieren bricht die Konsistenz fuer Nutzer. Die Plan-Intelligenz bleibt deshalb komplett im Desktop; die Web-UI behaelt **rein organisatorische** Stellschrauben. Eine spaetere Voll-Portierung des Desktop-Editor-Pfads ist eine eigenstaendige Entscheidung.

### US-10 — Admin sieht Inaktiv-Filter (Soft-Delete)
Als Admin oder Dispatcher möchte ich soft-gelöschte Teams und Standorte unter einem „Inaktiv"-Filter wiederfinden, damit ich versehentlich entfernte Einträge reaktivieren kann.

**Akzeptanzkriterien:**
- Sidebar-Filter: „Aktiv" (Default), „Inaktiv".
- Inaktive Einträge: `prep_delete IS NOT NULL`. Sortierung absteigend nach `prep_delete` (zuletzt entfernte zuerst).
- Im Detail-Drawer eines inaktiven Eintrags: Button „Wiederherstellen" setzt `prep_delete = NULL`.

### US-11 — Admin soft-deleted ein Team oder einen Standort
Als Admin möchte ich Teams und Standorte soft-deleten, damit sie aus den aktiven Listen verschwinden, aber historische Pläne weiterhin konsistent bleiben.

**Akzeptanzkriterien:**
- Aktion im Detail-Drawer: „In Inaktiv verschieben".
- Vorab-Prüfung: existieren aktive (nicht abgeschlossene) **PlanPeriods** für das Team? Wenn ja, **blockieren** mit Hinweis „Team kann nicht entfernt werden — aktive Planungsperiode XYZ.".
- Vorab-Prüfung Standort: existieren aktive `LocationPlanPeriod` für nicht abgeschlossene `PlanPeriod`s? Wenn ja, ebenfalls blockieren.
- Soft-Delete für ein Team setzt `prep_delete = now()` auf `Team`. Offene `TeamActorAssign`- und `TeamLocationAssign`-Einträge (`end IS NULL` und `start <= today`) werden mit `end = today` geschlossen (Audit-Konsistenz). Future-Start-Einträge (`start > today`) werden komplett gelöscht — sie waren noch nicht aktiv und tragen keine historische Information.
- Soft-Delete für einen Standort setzt `prep_delete = now()` auf `LocationOfWork`. Offene `TeamLocationAssign`-Einträge werden analog behandelt.

### US-12 — Admin hard-deleted einen soft-gelöschten Eintrag (nur wenn nie produktiv genutzt)
Als Admin möchte ich aus dem Inaktiv-Filter heraus einen Eintrag endgültig löschen, damit versehentlich angelegte Stammdaten dauerhaft entfernt werden können.

**Akzeptanzkriterien:**
- Aktion **nur** aus Detail-Drawer eines inaktiven Eintrags („Endgültig löschen").
- **Strikter Schutz:** Hard-Delete ist nur möglich, wenn der Eintrag **niemals** mit einer `PlanPeriod` (für Team) bzw. `LocationPlanPeriod` (für Standort) verknüpft war — also auch keine abgeschlossenen oder archivierten. Grund: `Team.plan_periods` und nachgelagerte Relationen sind mit `cascade_delete=True` definiert (`database/models.py:781`), Hard-Delete würde sonst **abgeschlossene Pläne inkl. Appointments, CancellationRequests und Inbox-Einträge** kaskadiert mitlöschen — irreversibler Datenverlust auf Jahre zurück.
- Sobald irgendeine Plan-Period-Referenz existiert (geprüft vor Anzeige des Buttons), erscheint statt des Buttons der Hinweis: „Endgültiges Löschen nicht möglich, weil bereits Planungs-Historie existiert. Eintrag bleibt im Inaktiv-Filter erhalten."
- Confirm-Modal (nur bei reinen Schutt-Datensätzen ohne Historie):
    - Liste der kaskadiert gelöschten Hilfs-Tabellen (`TeamActorAssign`, `TeamLocationAssign`, `NotificationGroup` für ein Team; M:N-Links für einen Standort).
    - Pflicht-Eingabe: Name des Datensatzes wortgleich tippen, sonst bleibt der „Löschen"-Button deaktiviert.
- Nach Bestätigung: `session.delete(team)` bzw. `session.delete(location)`. Cascade-Verhalten folgt den FK-Definitionen, ist aber durch den Schutz oben auf risikolose Tabellen begrenzt.
- Aktion ist irreversibel.

---

## 5. Datenmodell-Bezug

Keine Schema-Änderungen geplant. Genutzte Tabellen:

| Tabelle | Rolle | Relevante Felder |
|---|---|---|
| `team` | Stammdaten Team | `name`, `notes`, `dispatcher_id`, `project_id`, `prep_delete` |
| `location_of_work` | Stammdaten Standort + Plan-Konfig | `name`, `notes`, `nr_actors`, `fixed_cast`, `fixed_cast_only_if_available`, `address_id`, `project_id`, `prep_delete` |
| `address` | Adresse | `name`, `street`, `postal_code`, `city`, `project_id`, `prep_delete` |
| `team_actor_assign` | Person↔Team-Mitgliedschaft | `person_id`, `team_id`, `start`, `end` |
| `team_location_assign` | Standort↔Team-Zuordnung | `location_of_work_id`, `team_id`, `start`, `end` |
| `web_user` | Berechtigungsprüfung | `roles` (für Dispatcher-Pool und Rollen-Gating) |

**Wahrheitsdefinition „aktive Mitgliedschaft":** `start <= today AND (end IS NULL OR today < end)`.

---

## 6. Berechtigungen

`/admin/teams` ist **strikt admin-only** (siehe Entscheidung 2026-05-15 im Header). Reiner Dispatcher: 403 auf jeden Endpoint. Doppel-Rollen-User (Admin + Dispatcher): voller Admin-Zugriff.

| Aktion | Admin | Dispatcher |
|---|:---:|:---:|
| Team anlegen / löschen / umbenennen | ✓ | — |
| Team-Notes pflegen | ✓ | — |
| Dispatcher zuweisen | ✓ | — |
| Personen↔Team-Zuordnung | ✓ | — |
| Standort↔Team-Zuordnung | ✓ | — |
| Standort anlegen / löschen | ✓ | — |
| Standort-Name + Adresse pflegen | ✓ | — |
| Sicht auf Liste + Detail-Drawer | ✓ | — |
| Hard-Delete aus Inaktiv-Filter | ✓ | — |
| Wiederherstellen aus Inaktiv-Filter | ✓ | — |

Plan-Konfig-Felder (`nr_actors`, `fixed_cast`, `fixed_cast_only_if_available`, Plan-`notes`) sind in keinem Web-Pfad editierbar — Pflege ausschliesslich im Desktop (Begruendung: US-09).

Auf Endpoint-Ebene: jede Route hat `require_role(WebUserRole.admin)`. Es gibt keine `LoggedInUser`-typed Read-Endpoints in diesem Bereich.

---

## 7. UI-Struktur

### Dashboard-Integration

`web_api/dashboard/router.py` bekommt zwei kleine Anpassungen:

1. Die bestehende Tile `Teams & Standorte` im `WebUserRole.admin`-Block bleibt unverändert auf `/admin/teams`.
2. Im `WebUserRole.dispatcher`-Block wird eine **neue Tile** ergänzt:
    - Titel: `Standorte`
    - Beschreibung: `Besetzungsstärke und Fix-Cast pflegen`
    - URL: `/admin/teams?tab=locations`
    - Icon: passendes Heroicon (z. B. Office-/Building-Icon)
    - Branding-Farbe: Dispatcher-Block (aus `ROLE_BRANDING[dispatcher]`)

Damit haben beide Rollen einen Einstiegspunkt und der Code teilt sich genau eine Route — Mental-Model-Sauberkeit ohne Routen-Duplikation.

### Routen
```
GET  /admin/teams                           → Übersichtsseite mit Tab „Teams"
GET  /admin/teams?tab=locations             → Tab „Standorte"
GET  /admin/teams/teams/{id}                → Team-Detail-Drawer (HTMX-Partial)
GET  /admin/teams/locations/{id}            → Standort-Detail-Drawer (HTMX-Partial)
POST /admin/teams/teams                     → Team anlegen
POST /admin/teams/locations                 → Standort anlegen
PATCH /admin/teams/teams/{id}               → Team-Stammdaten ändern
PATCH /admin/teams/locations/{id}/stammdaten   → Admin-Felder ändern
PATCH /admin/teams/locations/{id}/plan-konfig  → Dispatcher-Felder ändern
POST /admin/teams/teams/{id}/members        → Person zuweisen
PATCH /admin/teams/members/{assign_id}      → end-Datum setzen / revertieren
POST /admin/teams/teams/{id}/locations      → Standort zuweisen
PATCH /admin/teams/team-locations/{assign_id} → end-Datum setzen / revertieren
POST /admin/teams/{kind}/{id}/soft-delete   → prep_delete setzen
POST /admin/teams/{kind}/{id}/restore       → prep_delete = NULL
DELETE /admin/teams/{kind}/{id}             → Hard-Delete (nach Name-Confirm-Eingabe)
GET  /admin/teams/addresses/suggest?q=…     → Autocomplete-Endpoint
```

### Layout
- **Sidebar-Layout** analog `cancellations/index.html` (CLAUDE.md-Referenz): Filter-Buttons (Aktiv / Inaktiv / Suche) links, Kartenliste rechts.
- Tabwechsel Teams/Standorte über Sidebar-Sektion.
- **Detail-Drawer** öffnet rechts (oder als Modal auf <1024px) — HTMX-Swap, kein Page-Reload.
- Listen-Karten zeigen den Linken Farb-Streifen (`status_color`) entsprechend Aktiv/Inaktiv (grau für Inaktiv).
- **Live-Suche + Live-Filter** wie in `viewer/persons` (HTMX-OOB, commit `fcf36fe`).

### Detail-Drawer Inhalte

**Team-Detail:**
1. Stammdaten-Block (`name`, `notes`, `dispatcher_id`)
2. Personen-Block: Tabelle aktuelle Mitglieder, Future-Member-Liste separat darunter; Button „Person zuweisen" öffnet Sub-Modal mit Personen-Selector + optional Start-Datum
3. Standort-Block: analog Personen-Block für Standorte
4. Verlauf-Reiter (sekundär, einklappbar): historische Mitgliedschaften nach Datum sortiert
5. Aktions-Footer: „In Inaktiv verschieben" (Admin)

**Standort-Detail:**
1. Stammdaten-Block (`name`, Adresse mit Autocomplete) — Admin editierbar, Dispatcher read-only
2. Plan-Konfig-Block (`nr_actors`, `fixed_cast`, `fixed_cast_only_if_available`, `notes`) — Dispatcher editierbar, Admin read-only
3. Team-Zugehörigkeit: Liste aktuelle Teams + Future-Wechsel + Sub-Modal für neue Zuordnung
4. Verlauf-Reiter
5. Aktions-Footer: „In Inaktiv verschieben" (Admin)

---

## 8. Validierung & Konflikt-Handling

### Name-Duplikate
- Server-Validierung via UniqueConstraint `(project_id, name)`. Bei Verletzung: HTTP 422 mit Feldfehler im Form-Card-Partial.

### Personen↔Team-Konflikt
- Vor Anlage eines neuen `TeamActorAssign`: prüfen, ob bereits ein offener Eintrag (gleiche Person × gleiches Team, `end IS NULL OR end > today`) existiert.
- Wenn ja: 409-Antwort mit zwei Optionen im UI:
    1. „Bestehende Mitgliedschaft am … beenden und neue beginnen"
    2. „Abbrechen"

### Standort↔Team-Konflikt
- Analog zu Personen↔Team.

### Future-Dating-Validierung
- `start <= end` falls beide gesetzt; sonst 422.
- `start > today` ist erlaubt (Future-Dating).
- `end > today` ist erlaubt (Future-Canceling).

### Soft-Delete-Schutz
- Vor `prep_delete`-Setzung: prüfen, ob aktive `PlanPeriod` (für Team) bzw. `LocationPlanPeriod` (für Standort) existiert. „Aktiv" = `prep_delete IS NULL` und ggf. Datum-Constraint im PlanPeriod-Modell (zu prüfen bei Implementierung).
- Bei Treffer: 409 mit konkretem Namen der blockierenden PlanPeriod.

### Hard-Delete-Schutz (verschärft)
- Hard-Delete ist **nur** zulässig, wenn der Eintrag nie mit einer `PlanPeriod`/`LocationPlanPeriod` verknüpft war — auch nicht historisch oder soft-gelöscht. Begründung siehe US-12.
- Vor dem Anzeigen des „Endgültig löschen"-Buttons im Inaktiv-Drawer: COUNT-Query auf `plan_period.team_id == this.id` (für Team) bzw. `location_plan_period.location_of_work_id == this.id` (für Standort). Bei `count > 0`: Button entfernen, Hinweistext anzeigen.

### Address-Verlinkung beim Speichern
- Speicher-Logik: Wenn die Adress-Felder im Drawer geändert wurden, prüfen, ob die alte `Address`-Zeile noch verknüpft ist. Je nach Eingabe (Autocomplete-Auswahl, manueller Edit, Leeren der Felder) wird:
    - eine **neue** `Address`-Zeile angelegt und mit dem Standort verlinkt (Autocomplete-Auswahl oder neuer Inhalt)
    - die **bestehende** `Address`-Zeile in-place aktualisiert (Edit ohne Quell-Wechsel)
    - die Verknüpfung gelöst, ohne die Address-Zeile zu löschen (Felder geleert)
- Diese Regel hält das 1:1-Modell ORM-konsistent (siehe US-08).

### Default-TimeOfDays bei Standort-Anlage
- Endpoint muss `LocationOfWork(..., project=session_project_obj)` setzen, **nicht** nur `project_id=...`. Sonst feuert der `before_flush`-Listener das Default-Kopieren nicht (siehe Memory `feedback_orm_pass_relations_not_fk`). Akzeptanztest: nach Anlage muss `loc.time_of_days` und `loc.time_of_day_standards` nicht-leer sein.

---

## 9. Audit & Logging

Bis die zentrale `audit_log`-Tabelle existiert (TODO `todo_audit_infrastructure_april2026`), wird jede strukturelle Änderung mit `logger.info(...)` und strukturiertem `extra={"event": ..., "actor": user_id, "target": team_id, ...}` festgehalten. Mindestens:
- `team_created`, `team_renamed`, `team_dispatcher_changed`, `team_soft_deleted`, `team_hard_deleted`, `team_restored`
- `location_created`, `location_renamed`, `location_address_changed`, `location_plan_config_changed`, `location_soft_deleted`, `location_hard_deleted`, `location_restored`
- `team_member_added`, `team_member_ended`, `team_member_reactivated`
- `team_location_added`, `team_location_ended`, `team_location_reactivated`

Sobald die Audit-Infrastruktur kommt, wird `logger.info` durch `audit_log.write(...)` ersetzt — Loggin-Calls bleiben strukturell identisch.

---

## 10. Migration aus dem Desktop

Bestehende Daten bleiben unverändert; das PRD ist additiv:
- Keine Datenbank-Migration nötig.
- Desktop-`FrmMasterData` und die neue Web-UI greifen auf dieselben Tabellen zu. Eventual-Consistency ist nicht erforderlich — bei gleichzeitiger Bearbeitung gewinnt die zuletzt geschriebene Änderung (Standard SQLAlchemy-Verhalten).
- Spätere PRDs können `FrmMasterData` als deprecated kennzeichnen und perspektivisch entfernen.

---

## 11. Offene Punkte für die Implementierungs-Phase

Folgende Aspekte werden im **Implementierungsplan** (separates Dokument nach Genehmigung dieses PRDs) konkretisiert:
- Pydantic-Schemas für Request/Response (analog zu bestehenden `web_api/schemas/`-Konventionen)
- Service-Layer-Aufteilung (`team_service.py`, `location_service.py`, `assignment_service.py`)
- HTMX-Partial-Templates (Detail-Drawer, Liste, Sub-Modals)
- Test-Strategie (Pytest, Smoke-Tests analog `reference_smoke_tests_audit_post_auth`)
- Concurrency-Edge-Cases (zwei Admins ändern denselben Eintrag gleichzeitig)
- Performance: erwartete Listengrößen sind unkritisch (<200 Teams, <500 Standorte pro Projekt). Keine besonderen Optimierungen vorgesehen.

---

## 12. Akzeptanz dieses PRDs

Bevor der Implementierungsplan startet, sollen folgende Punkte explizit bestätigt werden:
- [ ] Team-Notes-Pflege fällt komplett in den Admin-Bereich (im PRD so angenommen)
- [ ] Standort-Notes fallen in den Dispatcher-Bereich (im PRD so angenommen)
- [ ] `Team.excel_export_settings_id` wird in diesem PRD nicht angefasst (separates Feature)
- [ ] Hard-Delete-Confirm via Name-Eingabe ist UX-mäßig akzeptabel
- [ ] Future-Dating wird im UI **gleichberechtigt** mit „Heute starten" angeboten (kein Hidden Feature)
- [ ] Eine **eigene Dispatcher-Tile** `Standorte` darf in den `WebUserRole.dispatcher`-Block aufgenommen werden (Dashboard-Anpassung in `web_api/dashboard/router.py`)

### Bereits durch Review geklärte Punkte (nach Adviser-Pass 2026-05-14)
- ✓ **Dispatcher-Zugang**: separate Tile im Dispatcher-Block, gleiche URL `/admin/teams?tab=locations` (siehe Abschnitt 2 + 7).
- ✓ **Hard-Delete-Schutz**: blockiert, sobald *irgendeine* PlanPeriod/LocationPlanPeriod existiert — auch historisch abgeschlossene (siehe US-12 + Abschnitt 8). Verhindert kaskadierten Verlust historischer Pläne via `Team.plan_periods cascade_delete=True`.
- ✓ **Adress-Modell**: kein Sharing, immer neue Adress-Zeile pro Standort. Hält ORM-Back-Relation `Address.location_of_work` (singular Optional) konsistent (siehe US-08 + Abschnitt 8).
