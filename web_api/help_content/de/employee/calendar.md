---
title: Mein Kalender
roles: [employee]
category: Mitarbeiter
order: 20
updated: 2026-05-07
anchors:
  - was-zeigt-der-kalender
  - eigene-vs-team-ansicht
  - nur-unterbesetzte
  - termin-details
  - aktionen-am-termin
  - haeufige-fragen
related:
  - employee/availability
  - employee/cancellation
  - employee/swap-request
---

**Mein Kalender** zeigt dir alle Termine und Schichten, für die du eingeplant bist — und auf Wunsch
auch die deiner Kolleg:innen, sodass du das Team-Geschehen rund um deine Einsätze siehst. Du erreichst
die Seite über die Dashboard-Kachel **„Mein Kalender"** oder direkt unter `/employees/calendar`.

## Was zeigt der Kalender? {#was-zeigt-der-kalender}

- **Eigene Termine** — alle Schichten, für die du fest eingeteilt bist (oder durch ein angenommenes
  Einsprung-Angebot zusätzlich gebucht wurdest).
- **Team-Termine** — Termine deiner Kolleg:innen (per Toggle einblendbar).
- **Unterbesetzungs-Marker** — Termine, die noch nicht ausreichend besetzt sind, tragen einen
  kleinen roten Punkt oben rechts (in der Listen-Ansicht vor dem Titel). Über den Toggle
  **„Nur unterbesetzte"** kannst du gezielt nach diesen Terminen filtern.
- **Farbcodierung** — jeder Einsatzort hat eine eigene Farbe; identische Farben in deiner Eigen- und
  Team-Ansicht ermöglichen schnelles Erkennen.
- **Legende** — unten/seitlich findest du die Farb-Zuordnung der Standorte.

> **Tipp:** Die Farben kannst du in deinen **Einstellungen** (Persönlich → Einstellungen) selbst
> anpassen, falls die System-Farben für dich schwer zu unterscheiden sind.

## Eigene Termine vs. Team-Ansicht {#eigene-vs-team-ansicht}

Über den **„Alle anzeigen"-Toggle** oben wechselst du zwischen zwei Modi:

| Modus | Zeigt |
|---|---|
| **Aus** (Standard) | Nur deine eigenen Termine |
| **Ein** | Eigene Termine + alle Termine deines Teams |

Die Team-Ansicht ist nützlich, wenn du z. B. eine Tauschanfrage stellen möchtest — du siehst direkt,
wer an welchem Tag verfügbar ist, und kannst gezielt jemanden ansprechen.

## Nur unterbesetzte Termine {#nur-unterbesetzte}

Mit dem Toggle **„Nur unterbesetzte"** in der Sidebar blendest du alle Termine aus, die schon
vollständig besetzt sind. Übrig bleiben nur jene mit dem **roten Markierungs-Punkt** — also
Schichten, bei denen noch Personen fehlen.

| Modus | Zeigt |
|---|---|
| **Aus** (Standard) | Alle Termine (gemäß „Alle Termine der Periode"-Einstellung) |
| **Ein** | Nur Termine mit Unterbesetzungs-Marker |

Beide Toggles lassen sich **kombinieren**: „Alle Termine der Periode" + „Nur unterbesetzte" zeigt
team-weit jeden Termin, bei dem noch jemand fehlt — praktisch, um zu sehen, wo du **einspringen**
könntest.

> **Tipp:** Der Filter-Zustand wird in der URL gespeichert (`?only_understaffed=1`), sodass du dir
> einen gefilterten Kalender als Lesezeichen ablegen oder den Link teilen kannst.

## Termin-Details öffnen {#termin-details}

Klicke auf einen Termin im Kalender, um Details zu sehen:

- **Datum, Uhrzeit, Einsatzort**
- **Eingeteilte Personen** (mit dir markiert)
- **Notizen** der Disposition (z. B. „Sondertermin", „Anfahrtszeit beachten")
- **Aktionen** — je nach Termin und Status: Termin absagen, Termin tauschen, Ich kann einspringen

Bei vergangenen Terminen sind die Aktionen ausgeblendet — du kannst dir aber die Details als
Nachweis ansehen.

## Aktionen am Termin {#aktionen-am-termin}

Im Detail-Panel rechts findest du je nach Kontext einen oder mehrere Aktions-Buttons:

| Button | Wann sichtbar | Was passiert |
|---|---|---|
| **Termin absagen** | Eigener, künftiger Termin | Öffnet das Absage-Formular |
| **Termin tauschen** | Eigener, künftiger Termin | Öffnet die Tauschbörse mit Vorbelegung |
| **Ich kann einspringen** | Fremder, unterbesetzter Termin | Sendet ein Einsprung-Angebot — optional mit Nachricht |

Für jede Aktion gibt es ein eigenes Hilfe-Thema (siehe „Auch interessant" am Ende dieser Seite).

## Häufige Fragen {#haeufige-fragen}

**Warum sehe ich keine Termine, obwohl ich eingeplant sein sollte?**

Mögliche Ursachen: (1) du hast den Zeitraum nicht eingestellt — der Kalender springt initial auf die
nächste oder aktuelle Planungsperiode; (2) deine Disposition hat den Plan noch nicht veröffentlicht;
(3) dein Konto ist (noch) keiner Person verknüpft — wende dich in diesem Fall an deine Disposition.

**Warum erscheinen Termine, an denen ich gar nicht arbeiten kann?**

Im **„Alle anzeigen"-Modus** zeigt der Kalender auch Termine deines Teams, an denen andere eingeteilt
sind. Schalte den Toggle aus, um nur deine eigenen zu sehen.

**Kann ich den Kalender exportieren (z. B. iCal für Google/Apple Kalender)?**

Aktuell nicht. Eine Export-Funktion ist denkbar — falls du das brauchst, sprich mit der Disposition,
damit sie das Feature priorisieren kann.

**Was ist der Unterschied zur Verfügbarkeitsmaske?**

Die **Verfügbarkeitsmaske** ist deine Eingabe — wann du arbeiten **könntest**. Der **Kalender** zeigt,
wann du tatsächlich arbeiten **wirst** — also die Termine, für die deine Disposition dich konkret
eingeteilt hat.

**Sehen Kolleg:innen, dass ich ihren Kalender betrachte?**

Nein, das System protokolliert keine Lese-Zugriffe. Wer ein Detail-Panel öffnet, ist für andere nicht
sichtbar.
