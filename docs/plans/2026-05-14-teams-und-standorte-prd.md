# PRD: Teams & Zuordnungen (Admin-Verwaltung)

**Datum:** 2026-05-14 (umfassender Sync 2026-05-15)
**Status:** Phase 1.0–1.6 umgesetzt; offen nur noch Mobile-Polish + manuelle End-to-End-Klick-Probe. Plan-Konfig-Pfad (urspruengliche Phase 1.2) am 2026-05-15 wieder zurueckgebaut.
**Bezug:** `database/models.py` (`Team`, `LocationOfWork`, `Address`, `Person`, `TeamActorAssign`, `TeamLocationAssign`, `PlanPeriod`, `ActorPlanPeriod`), `web_api/admin/teams/`, `web_api/dashboard/router.py` (Tile `Teams & Zuordnungen`)

> **Architektur-Leitentscheidung (Stand 2026-05-15):** Die Web-UI uebernimmt **organisatorische** Stellschrauben (Team-/Standort-/Personen-Stammdaten, Adressen, Personen-/Standort-Zuordnungen, Dispatcher-Wechsel). **Plan-Intelligenz** (Besetzungsstaerke, TimesOfDay, FixedCast, SkillGroups auf allen Ebenen) bleibt vollstaendig im Desktop. Diese Trennlinie wurde am 2026-05-15 nach kurzer Plan-Konfig-Implementation auf Location-Ebene bewusst gezogen: konsistente Verantwortlichkeit ueber alle vier Konfig-Ebenen statt punktueller Teil-Migration. Eine eventuelle spaetere Voll-Portierung des Desktop-Editor-Pfads bleibt eigenstaendig zu planen.

> **Hinweis zu diesem Dokument (Stand 2026-05-15):** Die urspruengliche Fassung dieses PRDs sah zwei Tabs (Teams / Standorte) und einen Dispatcher-Zugang zur Plan-Konfig vor. Beides hat sich im Lauf der Umsetzung geaendert: heute drei Tabs (Teams / Standorte / Mitglieder), strikt admin-only, mit einem entschlackten Team-Drawer (Counts + Links statt eingebetteter Listen). Die alten Sektionen unten wurden in-place aktualisiert, der `~~strikethrough~~`-Text markiert Pfade, die wieder zurueckgebaut wurden.

---

## 1. Problem

Die Organisationsstruktur (Teams, Standorte, Personen, Dispatcher-Verantwortung) ließ sich bisher ausschließlich im Desktop-Client (`FrmMasterData`) pflegen. Daraus ergaben sich drei konkrete Folgen, die dieses PRD adressiert:

- **Administratoren ohne Desktop-Zugang** konnten neue Standorte, Teams und Personen nicht selbst anlegen.
- Personen-Stammdaten — selbst trivialer Tippfehler im Namen — erforderten Desktop-Zugriff. Das `/account/profile`-Self-Service erreicht nur Personen mit aktivem `WebUser`-Account; für die Mehrzahl der planungsrelevanten Personen ohne Login-Konto war das wirkungslos.
- ~~Dispatcher konnten einfache Plan-Konfigurations-Felder (Default-Besetzungsstärke, Fixed-Cast) nicht web-basiert ändern.~~ Punkt durch den Rückbau vom 2026-05-15 obsolet — Plan-Konfig bleibt bewusst im Desktop (siehe Header-Hinweis und Architektur-Leitentscheidung).

---

## 2. Lösungsüberblick

Eine neue Web-UI unter `/admin/teams` mit **drei top-level Tabs**:

```
/admin/teams  (Seitentitel: „Teams & Zuordnungen")
├── Teams       (Liste mit Detail-Drawer)
│   • Spalten: Name, Dispatcher, Mitglieder-Count, Standorte-Count, Status
│   • Drawer: Stammdaten + Dispatcher-Auswahl + Links zu Mitglieder-/
│     Standorte-Tab (gefiltert auf das Team) + Aktionen (Soft-/Hard-Delete)
│     + Verlauf-Reiter
│
├── Standorte   (Liste mit Detail-Drawer)
│   • Spalten: Name, Adresse, Soll-Besetzung, Teams (Chips), Status
│   • Drawer: Stammdaten (Name + Adresse) + Team-Zugehörigkeit
│     (Active/Future/End/Future-DELETE + Team-Search) + Aktionen
│     + Verlauf-Reiter
│
└── Mitglieder  (Liste mit Detail-Drawer)
    • Pool: alle aktiven Personen des Projekts (auch ohne WebUser-Account)
    • Spalten: Name, E-Mail, Teams (Chips), Status
    • Drawer: Stammdaten (Name editierbar, restliche Felder Desktop-Pflege)
      + Team-Mitgliedschaften (Active/Future/End/Future-DELETE/Team-Search)
      + Aktionen (Soft-/Hard-Delete) + Verlauf-Reiter
```

`/admin/teams` ist **strikt admin-only**. Reiner Dispatcher: 403 auf jedem Endpoint. Doppel-Rollen-User (Admin + Dispatcher): voller Admin-Zugriff.

**Tab-Drill-Down per `?team=<uuid>`-Query-Param:** Aus dem Team-Drawer führen zwei Links in die Mitglieder- bzw. Standorte-Tab gefiltert auf nur die aktiv zugeordneten Einträge. Banner mit "Filter aufheben" macht den Status sichtbar.

**Dashboard-Zugang:** Admins erreichen die Seite über die Tile `Teams & Zuordnungen` im Admin-Block (`web_api/dashboard/router.py`). ~~Eigene Dispatcher-Tile~~ — verworfen mit dem Plan-Konfig-Rückbau; es gibt kein Dispatcher-Tile mehr.

**Zuordnungen** (Person↔Team, Standort↔Team) werden als **zeitabschnittsbasierte Mitgliedschaften** abgebildet, konsistent mit dem bestehenden Datenmodell (`TeamActorAssign.start/end`, `TeamLocationAssign.start/end`). Die UI unterscheidet drei Zustände: **Active** (`start <= today AND (end IS NULL OR end > today)`), **Future** (`start > today`), **Past** (`end <= today`). Active und Future sind editierbar, Past erscheint nur im einklappbaren Verlauf-Reiter.

**Folge-Frage „APP anlegen?"** Nach erfolgreicher Anlage einer Team-Mitgliedschaft prüft der Server, ob offene Planperioden (`PlanPeriod.closed = False`) des Teams mit dem Mitgliedschafts-Zeitraum überlappen und die Person dort noch keinen `ActorPlanPeriod` hat. Bei Treffer wird statt des Drawer-Renders ein Dialog mit Checkbox-Liste (alle vorausgewählt) gezeigt. Submit erzeugt die `ActorPlanPeriod`s idempotent; Skip lädt den Quell-Drawer.

---

## 3. Scope

### In Scope (Phase 1)
- Liste + Filter (aktiv/inaktiv, Suche) für **drei Tabs**: Teams, Standorte, Mitglieder (= Personen)
- CRUD für **Team**: anlegen, umbenennen, Dispatcher zuweisen/wechseln, Notes pflegen, soft-/hard-deleten
- CRUD für **Standort**: anlegen, umbenennen, Adresse pflegen, soft-/hard-deleten
- CRUD für **Person**: anlegen (Pflicht: Vor-/Nachname + E-Mail; optional Gender; Username/Password auto-generiert), Vor-/Nachnamen ändern, soft-/hard-deleten
- Personen↔Team-Zuordnung (M:N, zeitabschnittsbasiert, Multi-Team erlaubt) — pflegbar aus Team-Drawer **und** Mitglieder-Drawer
- Standort↔Team-Zuordnung (M:N, zeitabschnittsbasiert) — pflegbar aus Standort-Drawer und Team-Drawer
- Adress-Autocomplete (Vorschlag bestehender Adressen während Inline-Eingabe)
- Hard-Delete für soft-gelöschte Einträge (mit Vor-+Nachname-Bestätigung)
- Tab-Drill-Down via `?team=<uuid>` (Standorte- und Mitglieder-Tab filterbar auf ein Team)
- Team-Namen als Chips in Standorte- und Mitglieder-Liste (bis 3 + "+N"-Überlauf, Tooltip mit Vollliste)
- APP-Anlage-Dialog: bei TAA-Anlage prüfen, ob offene PPs überlappen und ggf. `ActorPlanPeriod`s mit anlegen lassen
- Verlauf-Reiter in jedem Drawer (einklappbar, vergangene Zuordnungen `end <= today`)
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

### Phasen-Empfehlung (Stand 2026-05-15: alle ausser Mobile-Polish + Klick-Probe abgeschlossen)
1. **Phase 1.0** – Read-only-Liste + Detail-Drawer (Teams und Standorte sichtbar) ✓ (`a4a200e`)
2. **Phase 1.1** – Stammdaten-CRUD (Admin-Felder) ✓ (`c4a134a`)
3. ~~**Phase 1.2** – Plan-Konfig-CRUD (Dispatcher-Felder)~~ **verworfen 2026-05-15** (`2697531`, `491ee16`)
4. **Phase 1.3** – Zuordnungen (Personen↔Team, Standort↔Team) mit Future-Dating/Canceling ✓ (`09b8e55`)
5. **Phase 1.3b** – Standort-Drawer: Team-Zugehörigkeit vollständig editierbar (`be0db84`)
6. **Phase 1.3c** – Mitglieder-Tab + Person-Drawer + Person-Side TAA-Pflege; Team-Drawer entschlackt auf Counts + Links (`594fc23`)
7. **Phase 1.3d** – APP-Anlage-Dialog nach Add-Member (`c913041`)
8. **Phase 1.4** – Adress-Autocomplete ✓ (`a07b00b`)
9. **Phase 1.5** – Hard-Delete-Pfad aus Inaktiv-Filter (Team + Standort) ✓ (`7c59058`)
10. **Phase 1.5b** – Soft-/Hard-Delete für Personen (analog) ✓ (`204b9dd`)
11. **Phase 1.6** – Person-Anlage im Web + Name-Edit (`dee745e`); Team-Chips in Listen + Batch-Query (`14c8d63`); Verlauf-Reiter in allen Drawern ✓ (`f8cf6fd`)
12. **Polish-Fixes** ✓ — diverse: Spalten-Alignment (`204b9dd`, `b92f5ce`, `af6bf7b`), Dashboard-Tile-Sync (`b92f5ce`), Tojson-in-HTML-Attribut-Falle (`10f74f3`), HTMX-DELETE-Body→Query (`00b6832`), Status-Count-Drift (`ef4bb81`)

**Offen:** Mobile-Polish (<1024px), manuelle End-to-End-Klick-Probe (Liste in Memory `todo_admin_teams_folge_ui_may2026`).

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
Als Admin möchte ich soft-gelöschte Teams, Standorte und Personen unter einem „Inaktiv"-Filter wiederfinden, damit ich versehentlich entfernte Einträge reaktivieren kann.

**Akzeptanzkriterien:**
- Sidebar-Filter: „Aktiv" (Default), „Inaktiv" — pro Tab. Status-Counts zeigen den jeweiligen Tab-Pool.
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

### US-13 — Admin legt eine neue Person im Web an
Als Admin möchte ich Personen ohne Desktop-Zugang im Web anlegen können, damit die Pflege auch funktioniert, wenn die Person keinen WebUser-Account hat (Mitarbeiter, die nicht im System einloggen).

**Akzeptanzkriterien:**
- Erreichbar via „+ Neue Person"-Button im Mitglieder-Tab.
- Pflichtfelder: `f_name`, `l_name`, `email` (jeweils max. 50 Zeichen). Optional: Geschlecht (Dropdown — weiblich / männlich / divers / leer).
- `username` wird deterministisch aus dem Namen + 6-stelligem Hex generiert (`<l>.<f>-<hex>`), `password` als Random-Token. Web-Login läuft separat über `/admin/users` (WebUser-Anlage); Desktop-Login bekommt die Person später per `FrmMasterData`.
- Validierung: UniqueConstraint auf `(f_name, l_name, project_id)`; 409 mit Form-Vorbelegung, damit der User nicht neu tippen muss.
- Restliche Felder (Adresse, Telefon, Rolle, etc.) bleiben Desktop-Pflege.

### US-14 — Admin korrigiert den Namen einer Person
Als Admin möchte ich Vor- und Nachname einer Person im Web ändern, damit Tippfehler oder Namensänderungen (z. B. nach Heirat) korrigiert werden können, ohne dass die Person dafür einen WebUser-Account haben muss.

**Akzeptanzkriterien:**
- Inline-Form im Mitglieder-Drawer, Speichern-Button setzt `f_name` + `l_name`. E-Mail/Telefon bleiben Desktop-Pflege (Hinweis im Drawer).
- Validierung: nicht-leer (nach Strip), max. 50 Zeichen. Bei leerem Pflichtfeld: Drawer mit Error-Banner.
- `/account/profile`-Self-Service bleibt unverändert — adressiert eine andere Population (WebUser-Inhaber) und ergänzt diesen Pfad, ersetzt ihn nicht.

### US-15 — Admin soft-/hard-deletet eine Person
Als Admin möchte ich Personen soft-deleten und (bei reinen Schutt-Datensätzen) hard-deleten, analog zu Teams und Standorten.

**Akzeptanzkriterien:**
- Aktionen-Section im Mitglieder-Drawer, identisches UX-Pattern wie Standort/Team.
- Soft-Delete: schließt offene TAAs auf `end=today`, löscht Future-TAAs, setzt `Person.prep_delete = now()`. Blockiert bei aktiver `ActorPlanPeriod` (die Person ist noch in Planung).
- Hard-Delete: nur aus dem Inaktiv-Filter. Confirm-Input erwartet exakt „Vorname Nachname". Blockiert bei **jeder** existierenden `ActorPlanPeriod` (auch historisch — Cascade-Schutz für Planungs-Daten).

### US-16 — Admin bekommt nach TAA-Anlage die Folge-Frage „APP anlegen?"
Als Admin möchte ich nach der Anlage einer Team-Mitgliedschaft direkt entscheiden, ob die Person in den noch offenen Planperioden des Teams als verplanbar erscheint, damit ich nicht in zwei Schritten denken muss.

**Akzeptanzkriterien:**
- Trigger: erfolgreicher Submit von `POST /admin/teams/teams/{team_id}/members` ODER `POST /admin/teams/persons/{person_id}/teams`.
- Server prüft: gibt es PPs des Teams mit `closed=False AND prep_delete IS NULL`, deren Zeitraum mit dem TAA-Mitgliedschafts-Zeitraum überlappt (`taa.start <= pp.end AND (taa.end IS NULL OR pp.start <= taa.end)`) und für die noch **kein** APP der Person existiert?
- Bei ≥1 Treffer: statt Drawer-Render zeigt der Server `apply_apps_dialog.html` mit Checkbox-Liste (alle vorausgewählt) der betroffenen PPs (Start–End + Notes).
- Submit von `POST /admin/teams/members/{taa_id}/apply-apps` erzeugt die `ActorPlanPeriod`s idempotent (kein Duplikat-APP). `return_drawer`-Form-Param entscheidet, ob anschließend Team- oder Mitglieder-Drawer gerendert wird.
- Skip-Button im Dialog lädt den Quell-Drawer per GET — keine APPs werden erzeugt.

### US-17 — Admin sieht historische Zuordnungen im einklappbaren Verlauf-Reiter
Als Admin möchte ich pro Drawer einsehen können, welche Zuordnungen in der Vergangenheit lagen, damit ich Kontext habe ohne den primären Drawer-Inhalt zu überfrachten.

**Akzeptanzkriterien:**
- `<details>`-Block am Drawer-Ende, eingeklappt by default. Summary: „Verlauf (N)".
- Display-only — keine Edit-Aktionen (vergangene Zuordnungen sind unveränderlich für Audit).
- Inhalt: pro Zeile Name + Zeitraum (Start–End, DD.MM.YYYY).
- Sortierung: `end DESC` (zuletzt beendete zuerst).
- Team-Drawer kombiniert beide Sub-Historien (Mitglieder + Standorte) mit Sub-Headlines.
- Section erscheint nur, wenn ≥1 Eintrag.

---

## 5. Datenmodell-Bezug

Keine Schema-Änderungen. Genutzte Tabellen:

| Tabelle | Rolle | Relevante Felder |
|---|---|---|
| `team` | Stammdaten Team | `name`, `notes`, `dispatcher_id`, `project_id`, `prep_delete` |
| `location_of_work` | Stammdaten Standort (Plan-Konfig nur Desktop) | `name`, `notes`, `nr_actors`, `fixed_cast`, `fixed_cast_only_if_available`, `address_id`, `project_id`, `prep_delete` |
| `person` | Stammdaten Person (Web-Pflege: Name) | `f_name`, `l_name`, `email`, `gender`, `username`, `password`, `project_id`, `prep_delete` |
| `address` | Adresse | `name`, `street`, `postal_code`, `city`, `project_id`, `prep_delete` |
| `team_actor_assign` | Person↔Team-Mitgliedschaft | `person_id`, `team_id`, `start`, `end` |
| `team_location_assign` | Standort↔Team-Zuordnung | `location_of_work_id`, `team_id`, `start`, `end` |
| `plan_period` | Planperiode (für Soft-/Hard-Delete-Schutz + APP-Dialog) | `team_id`, `start`, `end`, `closed`, `prep_delete` |
| `actor_plan_period` | Person↔PlanPeriod (APP-Dialog + Hard-Delete-Schutz) | `person_id`, `plan_period_id` |
| `location_plan_period` | Standort↔PlanPeriod (Soft-/Hard-Delete-Schutz) | `location_of_work_id`, `plan_period_id` |
| `web_user` | Berechtigungsprüfung | `roles` (Rollen-Gating, Dispatcher-Pool) |

**Wahrheitsdefinitionen:**
- Aktive Mitgliedschaft/Zuordnung: `start <= today AND (end IS NULL OR today < end)`
- Future-Eintrag: `start > today`
- Past-Eintrag (Verlauf): `end IS NOT NULL AND end <= today`
- Offene Planperiode (für APP-Dialog): `closed = False AND prep_delete IS NULL`

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
| **Person anlegen / Vor-+Nachname pflegen** | ✓ | — |
| **Person soft-/hard-deleten** | ✓ | — |
| **ActorPlanPeriod via APP-Dialog erzeugen** | ✓ | — |
| Sicht auf Liste + Detail-Drawer (alle Tabs) | ✓ | — |
| Hard-Delete aus Inaktiv-Filter | ✓ | — |
| Wiederherstellen aus Inaktiv-Filter | ✓ | — |

Plan-Konfig-Felder (`nr_actors`, `fixed_cast`, `fixed_cast_only_if_available`, Plan-`notes`) sind in keinem Web-Pfad editierbar — Pflege ausschliesslich im Desktop (Begruendung: US-09).

Auf Endpoint-Ebene: jede Route hat `require_role(WebUserRole.admin)`. Es gibt keine `LoggedInUser`-typed Read-Endpoints in diesem Bereich.

---

## 7. UI-Struktur

### Dashboard-Integration

`web_api/dashboard/router.py` enthält im `WebUserRole.admin`-Block eine Tile **„Teams & Zuordnungen"** (URL `/admin/teams`, Subtitel „Struktur, Standorte und Mitgliedschaften pflegen"). ~~Im Dispatcher-Block keine Tile~~ — Dispatcher hat keinen Zugang zur Seite (Plan-Konfig blieb Desktop).

### Routen (Stand 2026-05-15)

**Seite + Tab-Auswahl:**
```
GET  /admin/teams                                 → Übersichtsseite, Default-Tab „Teams"
GET  /admin/teams?tab=locations                   → Tab „Standorte"
GET  /admin/teams?tab=members                     → Tab „Mitglieder"
GET  /admin/teams?tab=members&team=<uuid>         → Mitglieder gefiltert auf Team
GET  /admin/teams?tab=locations&team=<uuid>       → Standorte gefiltert auf Team
GET  /admin/teams?status=inactive                 → Inaktiv-Filter (pro Tab)
```

**Drawer + Stammdaten-CRUD:**
```
GET  /admin/teams/teams/{id}/drawer               → Team-Drawer
GET  /admin/teams/locations/{id}/drawer           → Standort-Drawer
GET  /admin/teams/persons/{id}/drawer             → Mitglieder-Drawer
GET  /admin/teams/teams/new                       → Empty-Drawer für neues Team
GET  /admin/teams/locations/new                   → Empty-Drawer für neuen Standort
GET  /admin/teams/persons/new                     → Empty-Drawer für neue Person
POST /admin/teams/teams                           → Team anlegen
POST /admin/teams/locations                       → Standort anlegen
POST /admin/teams/persons                         → Person anlegen (f_name/l_name/email/gender)
PATCH /admin/teams/teams/{id}                     → Team-Stammdaten ändern
PATCH /admin/teams/locations/{id}/stammdaten      → Name + Adresse ändern
PATCH /admin/teams/persons/{id}/name              → Vor-/Nachname ändern
POST /admin/teams/teams/{id}/dispatcher           → Dispatcher zuweisen/entfernen
```

**Suche-Endpoints (HTMX-Live-Suche im Drawer):**
```
GET  /admin/teams/addresses/suggest?q=…           → Adress-Autocomplete
GET  /admin/teams/teams/{id}/dispatcher-search?q= → Dispatcher-Pool
GET  /admin/teams/teams/{id}/member-search?q=     → Personen-Pool (von Team-Seite)
GET  /admin/teams/teams/{id}/location-search?q=   → Standort-Pool (von Team-Seite)
GET  /admin/teams/locations/{id}/team-search?q=   → Team-Pool (von Standort-Seite)
GET  /admin/teams/persons/{id}/team-search?q=     → Team-Pool (von Person-Seite)
```

**Zuordnungen (TAA, TLA) — symmetrisch von beiden Seiten:**
```
POST /admin/teams/teams/{id}/members              → TAA von Team-Seite anlegen
POST /admin/teams/teams/{id}/locations            → TLA von Team-Seite anlegen
POST /admin/teams/persons/{id}/teams              → TAA von Person-Seite anlegen
POST /admin/teams/locations/{id}/teams            → TLA von Standort-Seite anlegen
PATCH /admin/teams/members/{assign_id}            → TAA-end setzen (rendert Team-Drawer)
PATCH /admin/teams/team-locations/{assign_id}     → TLA-end setzen (rendert Team-Drawer)
PATCH /admin/teams/person-teams/{assign_id}       → TAA-end setzen (rendert Member-Drawer)
PATCH /admin/teams/location-teams/{assign_id}     → TLA-end setzen (rendert Location-Drawer)
DELETE /admin/teams/members/{assign_id}           → Future-TAA löschen
DELETE /admin/teams/team-locations/{assign_id}    → Future-TLA löschen (rendert Team-Drawer)
DELETE /admin/teams/person-teams/{assign_id}      → Future-TAA löschen (rendert Member-Drawer)
DELETE /admin/teams/location-teams/{assign_id}    → Future-TLA löschen (rendert Location-Drawer)
```

**Folge-Dialog APP-Anlage:**
```
POST /admin/teams/members/{taa_id}/apply-apps     → ActorPlanPeriods erzeugen + return_drawer
```

**Lifecycle (Soft-/Hard-Delete für Team, Standort, Person):**
```
POST /admin/teams/teams/{id}/soft-delete          → prep_delete setzen
POST /admin/teams/locations/{id}/soft-delete
POST /admin/teams/persons/{id}/soft-delete
POST /admin/teams/teams/{id}/restore              → prep_delete = NULL
POST /admin/teams/locations/{id}/restore
POST /admin/teams/persons/{id}/restore
DELETE /admin/teams/teams/{id}                    → Hard-Delete mit Name-Confirm
DELETE /admin/teams/locations/{id}                → Hard-Delete mit Name-Confirm
DELETE /admin/teams/persons/{id}                  → Hard-Delete mit Vor-+Nachname-Confirm
```

Hinweis zu DELETE-Endpoints mit Confirm-Form: HTMX schickt Form-Werte bei `hx-delete` als URL-Query-Parameter, nicht im Body. Der Helper `_read_name_confirmation(request)` liest beide Quellen (Query + Body-Fallback), damit Browser- und Test-Pfad funktionieren — siehe Memory `feedback_jinja_tojson_html_attribute.md`.

### Layout
- **Sidebar-Layout** analog `cancellations/index.html` (CLAUDE.md-Referenz): drei Tab-Buttons (Teams/Standorte/Mitglieder, mit Status-Dots in Sky/Emerald/Violet), Status-Filter Aktiv/Inaktiv, Live-Suche oben rechts auf der Content-Seite.
- **Tab-Wechsel** räumt den `team`-Filter auf (das `qs`-Macro setzt `team=''`).
- **Detail-Drawer** öffnet rechts (oder als Modal auf <1024px — Mobile-Polish offen) — HTMX-Swap, kein Page-Reload.
- **Live-Suche + Live-Filter** wie in `viewer/persons` (HTMX-OOB, commit `fcf36fe`); Suche pro Tab eigenständig.
- **Spalten-Alignment** in den Listen: Text/Chips text-left, numerische Counts (Soll-Besetzung, Mitglieder, Standorte) text-center.

### Detail-Drawer Inhalte (Stand 2026-05-15)

**Team-Drawer (entschlackt):**
1. Stammdaten-Block (`name`, `notes`)
2. Dispatcher-Auswahl mit Pool-Suche
3. Zuordnungen-Block: zwei Count-Links auf die Mitglieder- bzw. Standorte-Tab gefiltert auf das Team („3 aktive Mitglieder pflegen ↗" / „2 aktive Standorte pflegen ↗")
4. Verlauf-Reiter (einklappbar, vergangene Mitglieder + Standorte, mit Sub-Headlines + Sub-Counts)
5. Aktions-Footer: „In Inaktiv verschieben" / Restore + Hard-Delete-Confirm
~~Eingebettete Mitglieder-/Standorte-Listen direkt im Team-Drawer~~ — durch Drei-Tab-Layout abgelöst, Pflege passiert in den jeweiligen Tabs.

**Standort-Drawer:**
1. Stammdaten-Block (`name`, Adresse mit Autocomplete)
2. ~~Plan-Konfig-Block~~ — entfernt mit Plan-Konfig-Rückbau 2026-05-15
3. Team-Zugehörigkeit: Active-Liste (Inline-End-Datum + Beenden/Ändern), Future-Liste (DELETE), Team-Search-Input
4. Verlauf-Reiter (einklappbar, vergangene Team-Zuordnungen)
5. Aktions-Footer: „In Inaktiv verschieben" / Restore + Hard-Delete-Confirm

**Mitglieder-Drawer (neu seit 2026-05-15):**
1. Header: „Neue Person" oder vorhandener Name + ggf. „Inaktiv seit"-Badge
2. Stammdaten-Block: Inline-Form für Vor-/Nachname (editierbar); E-Mail und Telefon read-only mit Hinweis „Pflege im Desktop"; bei `person=None` Create-Form mit Pflicht-Feldern + Auto-Gen-Hinweis
3. Team-Mitgliedschaften: Active-Liste (Inline-End-Datum), Future-Liste (DELETE), Team-Search-Input
4. Verlauf-Reiter (einklappbar, vergangene Team-Mitgliedschaften)
5. Aktions-Footer: „In Inaktiv verschieben" / Restore + Hard-Delete-Confirm mit Vor-+Nachname-Eingabe

---

## 8. Validierung & Konflikt-Handling

### Name-Duplikate
- Team/Standort: UniqueConstraint `(project_id, name)`. Bei Verletzung 409 mit Form-Vorbelegung.
- Person: UniqueConstraint `(f_name, l_name, project_id)`. 409-Behandlung identisch.
- `DuplicateNameError`-Meldung ist genus-agnostisch („Person «Max Muster» existiert bereits.") — passt für Team, Standort, Person ohne Sonder-Logik.

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
- **Team:** blockiert bei aktiver `PlanPeriod` (`prep_delete IS NULL`).
- **Standort:** blockiert bei aktiver `LocationPlanPeriod` (`LocationPlanPeriod` hat kein eigenes `prep_delete` — alle existierenden zählen).
- **Person:** blockiert bei aktiver `ActorPlanPeriod` (analog: kein eigenes `prep_delete`).
- Bei Treffer: 409 + Drawer mit Fehler-Banner, kein Schreibvorgang.

### Hard-Delete-Schutz (verschärft)
- Hard-Delete ist **nur** zulässig, wenn der Eintrag nie mit einer `PlanPeriod` (Team) / `LocationPlanPeriod` (Standort) / `ActorPlanPeriod` (Person) verknüpft war — auch nicht historisch oder soft-gelöscht. Begründung siehe US-12.
- Vor dem Anzeigen des „Endgültig löschen"-Buttons im Inaktiv-Drawer: COUNT-Query. Bei `count > 0`: Button entfernen, Hinweistext anzeigen.
- Name-Confirm-Input: erwartet exakt den Namen (Team/Standort) bzw. „Vorname Nachname" (Person). UX-Pattern: `data-expected`-Attribut transportiert den Soll-Wert, JS-Vergleich enabled den Submit. ~~Inline-Tojson im `oninput`-Attribut~~ — abgelöst wegen vorzeitigem Attribut-Schluss durch JSON-Anführungszeichen (siehe Memory `feedback_jinja_tojson_html_attribute.md`).

### APP-Anlage-Dialog (Trigger nach TAA-Anlage)
- Bedingung: nach erfolgreichem `assignments.add_team_member` → `assignments.list_open_overlapping_plan_periods_for_taa(taa)` ≥ 1.
- Render: `apply_apps_dialog.html` statt Drawer; Form-Submit auf `POST /admin/teams/members/{taa_id}/apply-apps` mit Hidden-Field `return_drawer` ∈ {team, member}.
- `mutations.create_actor_plan_periods` ist idempotent (kein Duplikat-APP), validiert Project-Match.
- Skip-Button (HTML-only): `hx-get`-Reload des Quell-Drawers — keine APPs erzeugt.

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

Bis die zentrale `audit_log`-Tabelle existiert (TODO `todo_audit_infrastructure_april2026`), wird jede strukturelle Änderung mit `logger.info("teams_admin_action", extra={...})` festgehalten. Aktuelle Action-Strings:
- **Team:** `team_created`, `team_renamed`, `team_notes_changed`, `team_dispatcher_changed`, `team_soft_deleted`, `team_hard_deleted`, `team_restored`
- **Standort:** `location_created`, `location_renamed`, `location_address_changed`, `location_soft_deleted`, `location_hard_deleted`, `location_restored` ~~+ `location_plan_config_changed`~~ (verworfen mit Plan-Konfig-Rückbau)
- **Person:** `person_created`, `person_renamed`, `person_soft_deleted`, `person_hard_deleted`, `person_restored`
- **Zuordnungen TAA:** `team_member_added`, `team_member_ended`, `team_member_reactivated`, `team_actor_future_deleted`
- **Zuordnungen TLA:** `team_location_added`, `team_location_ended`, `team_location_reactivated`, `team_location_future_deleted`
- **APP-Anlage:** `actor_plan_period_created` (mit zusätzlichen `person_id` + `plan_period_id` im `extra`)

Sobald die Audit-Infrastruktur kommt, wird `logger.info` durch `audit_log.write(...)` ersetzt — Logging-Calls bleiben strukturell identisch.

---

## 10. Migration aus dem Desktop

Bestehende Daten bleiben unverändert; das PRD ist additiv:
- Keine Datenbank-Migration nötig.
- Desktop-`FrmMasterData` und die neue Web-UI greifen auf dieselben Tabellen zu. Eventual-Consistency ist nicht erforderlich — bei gleichzeitiger Bearbeitung gewinnt die zuletzt geschriebene Änderung (Standard SQLAlchemy-Verhalten).
- Spätere PRDs können `FrmMasterData` als deprecated kennzeichnen und perspektivisch entfernen.

---

## 11. Offene Punkte (Stand 2026-05-15)

Funktional ist die Phase-1-Implementation abgeschlossen. Offen geblieben sind nur noch UX-/Polish-Punkte:
- **Mobile-Polish** (<1024px): die responsive Sidebar-Collapse-Logik ist im CSS angelegt (`index.html` Z. ~30-46), eine systematische visuelle Probe steht aus.
- **Manuelle End-to-End-Klick-Probe**: vollständige Sequenz (Team anlegen → Mitglieder hinzufügen → APP-Dialog → Standort zuordnen → Hard-Delete-Pfad) am Browser durchspielen; Findings als kleine Polish-Iterationen ein.
- **Concurrency-Edge-Cases**: zwei Admins ändern denselben Eintrag gleichzeitig. Standard SQLAlchemy-Verhalten (last-write-wins) wurde bewusst akzeptiert; ein Smoke-Test mit zwei parallelen Sessions wäre nice-to-have.
- **Performance:** erwartete Listengrößen sind unkritisch (<200 Teams, <500 Standorte, <500 Personen pro Projekt). Bereits umgesetzt: Batch-Query für Team-Chips (1 Query statt N+1 pro Liste). Keine weiteren Optimierungen vorgesehen.

---

## 12. Akzeptanz dieses PRDs

Stand 2026-05-15 — Implementation abgeschlossen, Review-Items aus dem ursprünglichen PRD-Pass:
- ✓ Team-Notes-Pflege fällt komplett in den Admin-Bereich.
- ~~Standort-Notes fallen in den Dispatcher-Bereich~~ — durch Plan-Konfig-Rückbau hinfällig; Standort-Notes existieren als Feld weiter, werden aber nur über Desktop gepflegt.
- ✓ `Team.excel_export_settings_id` wurde nicht angefasst (separate Feature-Schiene).
- ✓ Hard-Delete-Confirm via Name-Eingabe ist UX-mäßig akzeptiert; bei Person zusätzlich „Vorname Nachname" exakt.
- ✓ Future-Dating wird im UI gleichberechtigt mit „Heute starten" angeboten (Date-Input pro Zuweisungs-Form).
- ~~Eigene Dispatcher-Tile~~ — verworfen mit dem Plan-Konfig-Rückbau (Dashboard zeigt nur die Admin-Tile).

### Architektur-Entscheidungen, die im Lauf der Umsetzung getroffen wurden
- **Plan-Konfig-Rückbau** (2026-05-15, `2697531`, `491ee16`): Plan-Konfig auf Standort-Ebene war für ~12h im Web; danach komplett zurück in den Desktop. Begründung: konsistente Verantwortlichkeit über alle vier Konfig-Ebenen statt punktueller Teil-Migration. Siehe Memory `project_admin_teams_plan_config_rollback_may2026`.
- **Drei-Tab-Layout** (`594fc23`): drei top-level Tabs (Teams/Standorte/Mitglieder) statt zwei. Team-Drawer wurde auf Stammdaten + Counts + Links entschlackt; die M:N-Pflege passiert in den jeweiligen Tabs.
- **Mitglieder-Tab + Person-CRUD im Web** (`594fc23`, `dee745e`, `204b9dd`): Personen-Anlage, Name-Edit und Soft-/Hard-Delete im Web — schließt die Coverage-Lücke für Personen ohne WebUser-Account.
- **APP-Anlage-Dialog** (`c913041`): Folge-Frage nach TAA-Anlage, ob `ActorPlanPeriod`s für offene PPs mit angelegt werden sollen — symmetrisch für beide Add-Pfade.
- **Verlauf-Reiter** (`f8cf6fd`): einklappbares `<details>` in jedem Drawer für vergangene Zuordnungen.
- ✓ **Hard-Delete-Schutz**: blockiert, sobald *irgendeine* PlanPeriod / LocationPlanPeriod / ActorPlanPeriod existiert.
- ✓ **Adress-Modell**: kein Sharing, immer neue Adress-Zeile pro Standort.
