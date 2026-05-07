---
title: Verfügbarkeit eintragen
roles: [employee]
category: Mitarbeiter
order: 30
updated: 2026-05-07
anchors:
  - ueberblick
  - verfuegbarkeit-eintragen
  - verfuegbarkeit-loeschen
  - eigene-tageszeiten
  - anmerkungen-wuensche
  - gesperrte-perioden
  - haeufige-fragen
related:
  - employee/calendar
  - employee/swap-request
---

In der **Verfügbarkeitsmaske** trägst du ein, an welchen Tagen und zu welchen Tageszeiten du
arbeiten kannst. Auf Basis deiner Eingaben plant dein Disponent dich später für konkrete Termine ein.

## Überblick {#ueberblick}

Du erreichst die Maske über die Dashboard-Kachel **„Verfügbarkeit"** oder direkt unter
`/availability/`. Sie ist in drei Bereiche aufgeteilt:

- **Sidebar (links)** — wechselt zwischen Teams und Planungsperioden, zeigt Statistik (Anzahl
  Verfügbarkeiten, Wunscheinsätze, eigene Anmerkungen).
- **Wochengrid (Mitte)** — eine Wochenansicht mit allen 7 Tagen nebeneinander. Jede deiner
  eingetragenen Verfügbarkeiten erscheint als farbiger Block.
- **Tages-Panel (rechts)** — öffnet sich beim Klick auf einen Tag und enthält die eigentlichen
  Schaltflächen zum Eintragen und Löschen.

> **Hinweis:** Wenn du in mehreren Teams arbeitest, wähle zuerst das richtige Team über die
> Sidebar. Jedes Team hat eigene Planungsperioden — Verfügbarkeiten gelten immer pro Team.

## Verfügbarkeit eintragen {#verfuegbarkeit-eintragen}

1. Öffne im Wochengrid den gewünschten Tag durch Klick auf die Spalte oder den Tagestitel.
2. Im Tages-Panel rechts erscheinen die Tageszeit-Kategorien deines Projekts
   (z. B. **Vormittag**, **Nachmittag**, **Abend**).
3. Klicke auf den Button der Kategorie, an der du verfügbar bist. Die Schaltfläche wird sofort
   farbig markiert und ist nun in deiner Verfügbarkeit hinterlegt.

Die Sidebar-Statistik aktualisiert sich automatisch — du musst nichts speichern. Mehrere
Tageszeiten am gleichen Tag sind erlaubt; du kannst z. B. **Vormittag** und **Abend** zugleich
markieren, ohne den Nachmittag.

### Mehrere Zeiträume pro Kategorie (Intervall-Modus)

Im **Intervall-Modus** kannst du innerhalb einer Tageszeit-Kategorie mehrere konkrete Zeitfenster
parallel hinterlegen. Beispiel: Du hast unter **Vormittag** zwei eigene Tageszeiten definiert —
„Vormittag früh (06:00–10:00)" und „Vormittag spät (10:00–13:00)". Im Tages-Panel kannst du beide
einzeln aktivieren oder nur eine davon, je nach tatsächlicher Verfügbarkeit.

Im **Simple-Modus** wählt das System automatisch eine vom Projekt vorgegebene Standard-Zeit pro
Kategorie. Du klickst nur die Kategorie an — eigene Tageszeiten können hier nicht angelegt werden.

> Welcher Modus für dich aktiv ist, hängt am Projekt und wird vom Administrator festgelegt.
> Du erkennst den Simple-Modus daran, dass der Menüpunkt **„Meine Tageszeiten"** nicht erscheint.

## Verfügbarkeit löschen {#verfuegbarkeit-loeschen}

Im Tages-Panel rechts klickst du erneut auf einen bereits markierten Button — die Verfügbarkeit
wird entfernt. Auch hier ist nichts zu speichern.

**Achtung — bereits eingeplante Tage:** Wenn dein Disponent dich für einen Termin an diesem Tag
und zu dieser Tageszeit bereits eingeplant hat, lässt sich die Verfügbarkeit **nicht mehr löschen**.
Du erhältst dann eine Fehlermeldung („Verfügbarkeitstag ist bereits eingeplant"). In diesem Fall
nutze den **Absage-Workflow** für den konkreten Termin — siehe das Hilfe-Thema „Absagen".

## Eigene Tageszeiten verwalten (nur Intervall-Modus) {#eigene-tageszeiten}

Im Intervall-Modus erreichst du unter **„Meine Tageszeiten"** (Link in der Sidebar oder unter
`/availability/time-of-days`) eine Übersicht aller deiner persönlichen Zeitfenster, gruppiert nach
Tageszeit-Kategorie.

| Aktion | Wie? |
|---|---|
| Neue Tageszeit anlegen | Auf **„+ Neu"** in der gewünschten Kategorie klicken, Start- und Endzeit eingeben |
| Bestehende Tageszeit ändern | In der Zeile auf das Stift-Symbol klicken und Zeiten anpassen |
| Tageszeit löschen | Mülltonnen-Symbol — funktioniert nur, wenn die Tageszeit nicht mehr in Verfügbarkeitstagen verwendet wird |

> **Tipp:** Lege Tageszeiten so an, wie sie in deinem Alltag wirklich vorkommen — z. B. „Vormittag
> regulär (08:00–13:00)" und „Vormittag mit Anfahrt (07:00–13:00)". Bei der Termineinteilung
> erkennt der Disponent dann sofort, welche Variante an dem Tag passt.

## Anmerkungen und Wunscheinsätze {#anmerkungen-wuensche}

Über der Statistik in der Sidebar gibst du deinem Disponenten zwei zusätzliche Informationen:

- **Anmerkungen** — Freitext, z. B. „Nur notfalls in Einrichtung xyz besetzen" oder „Vom 03. bis 11.10 bitte nur 3 Einsätze". Die Anmerkungen sind nur für deine Disposition sichtbar.
- **Wunscheinsätze** — die Anzahl von Einsätzen, die du in dieser Periode anstrebst. Dein
  Disponent versucht, diese Zahl bei der Einteilung zu treffen.

Beide Felder werden automatisch gespeichert, sobald du das Eingabefeld verlässt (Tab oder Klick
außerhalb).

## Gesperrte Planungsperioden {#gesperrte-perioden}

Wenn dein Disponent eine Planungsperiode **geschlossen** hat, erscheint im Tages-Panel ein
**Schloss-Symbol** mit dem Hinweis „Gesperrt". Ab diesem Zeitpunkt sind keine Änderungen mehr
möglich — die Verfügbarkeiten, die du eingetragen hast, sind verbindlich.

Wenn sich nachträglich etwas ändert (du wirst krank, ein Termin fällt unerwartet weg etc.),
nutze den **Absage-Workflow** oder die **Tauschbörse**, statt die Verfügbarkeit zu ändern.

## Häufige Fragen {#haeufige-fragen}

**Warum sehe ich keine Planungsperiode?**

Entweder gibt es für dein Team aktuell keine offene Periode, oder du bist (noch) keinem Team
zugeordnet. Wende dich in beiden Fällen an deinen Disponenten.

**Warum kann ich keine eigenen Tageszeiten anlegen?**

Dann läuft das Projekt im Simple-Modus. Die Standard-Zeiten sind dort projektweit festgelegt —
sprich deinen Administrator an, wenn du andere Zeiten brauchst.

**Warum verschwindet eine Verfügbarkeit nicht beim Klick?**

Höchstwahrscheinlich bist du bereits für diesen Tag eingeplant. Schau in **„Mein Kalender"**, ob
dort ein Termin an diesem Tag und zu dieser Tageszeit liegt. Wenn ja: nutze den Absage- oder
Tausch-Workflow.

**Werden meine Eingaben sofort gespeichert?**

Ja. Jeder Klick auf eine Tageszeit-Schaltfläche und jede Eingabe in den Anmerkungen ist sofort
in der Datenbank — ein „Speichern"-Knopf existiert bewusst nicht.

**Kann ich Verfügbarkeiten kopieren (z. B. von einer Woche in die nächste)?**

Aktuell nicht direkt in der Web-Oberfläche. Wenn du regelmäßig wiederkehrende Muster hast, sprich
mit deinem Disponenten — er kann das beim Anlegen einer neuen Periode für dich vorbelegen.
