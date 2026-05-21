---
title: Notfall-Benachrichtigungs-Kreise
roles: [dispatcher]
category: Disposition
order: 10
updated: 2026-05-21
anchors:
  - auto-mode
  - whitelist-konfigurieren
  - bulk-uebernehmen
  - bulk-loeschen
  - abgrenzung-regulaer
  - haeufige-fragen
related:
  - employee/cancellation
---

Wenn eine Mitarbeiterin oder ein Mitarbeiter **nach Ablauf der Absagefrist** krankheitsbedingt
absagen muss, läuft das über den **Notfall-Absage-Workflow**. Du steuerst pro Arbeitsort, wer
in diesem Fall benachrichtigt wird — schlanker oder mit anderem Personenkreis als bei der
regulären Absage.

Den Verwaltungs-Bereich erreichst du über das Dashboard-Tile **„Notfall-Kreise"** oder direkt
unter `/dispatcher/emergency-notification-circles`.

## Auto-Mode (Whitelist leer) {#auto-mode}

**Standardzustand**: solange die Whitelist eines Arbeitsortes **leer** ist, schaltet das System
automatisch auf **Auto-Mode**. Bei einer Notfall-Absage werden dann alle berechtigten Personen
des Arbeitsortes benachrichtigt, die an dem Tag keinen anderen Einsatz haben — also derselbe
Kreis wie beim regulären Absage-Workflow.

> **Wichtig — Implicit-Aktivierung:** Es gibt **keinen** separaten An/Aus-Schalter. Die
> Whitelist ist entweder leer (= Auto-Mode) oder gefüllt (= Konfiguriert). Sobald du die erste
> Person einträgst, ist der Arbeitsort konfiguriert; sobald du die letzte Person entfernst,
> kehrt er zurück zu Auto-Mode.

In der Sidebar-Filterleiste findest du das passende Filter-Set („Auto-Mode" vs. „Konfiguriert"),
um auf einen Blick zu sehen, welche Arbeitsorte aktuell wie eingestellt sind.

## Whitelist konfigurieren {#whitelist-konfigurieren}

Auf der Detail-Seite eines Arbeitsortes findest du drei Aktions-Buttons rechts oben am
Whitelist-Block:

| Button | Wann sichtbar | Was er tut |
|---|---|---|
| **+ Person hinzufügen** | immer | Modal mit Personensuche; Auswahl direkt eingetragen |
| **Aus regulärem Kreis übernehmen** | wenn regulärer Kreis ≥ 1 Person enthält | Übernimmt alle aus dem regulären Kreis |
| **Alle entfernen** | wenn Whitelist ≥ 1 Person enthält | Setzt zurück auf Auto-Mode |

Die Pool-Grundlage ist immer **„aktive Team-Zuordnung am Arbeitsort"** — Karteileichen aus
früheren Teams können nicht eingetragen werden. Die Anzahl verfügbarer Personen siehst du am
Fuß der Karte („Pool: N Personen verfügbar").

## „Aus regulärem Kreis übernehmen" {#bulk-uebernehmen}

Praktisch, wenn du die Whitelist erstmalig befüllst und sie sich stark mit dem regulären
Benachrichtigungs-Kreis überschneidet. Beim Klick:

1. Alle Personen aus dem regulären Kreis dieses Arbeitsortes werden in die Notfall-Whitelist
   kopiert.
2. **Karteileichen-Filter**: Personen, die im regulären Kreis stehen, aber inzwischen keine
   aktive Team-Zuordnung am Arbeitsort mehr haben, werden **übersprungen**. So entsteht keine
   ungültige Whitelist.
3. **Idempotenz**: Bereits eingetragene Personen werden nicht doppelt hinzugefügt — du kannst
   den Button gefahrlos ein zweites Mal klicken, um eine zwischenzeitlich gewachsene
   reguläre Liste nachzuziehen.

Bei der Bestätigung zeigt der Confirm-Dialog die Anzahl der zu kopierenden Personen — so weißt
du vorher, was passiert.

> **Hinweis:** Die Aktion **kopiert**, sie **verknüpft nicht**. Spätere Änderungen am regulären
> Kreis schlagen sich **nicht** automatisch auf die Notfall-Whitelist nieder. Wenn dort jemand
> hinzukommt, musst du die Notfall-Whitelist separat pflegen oder den Button erneut nutzen.

## „Alle entfernen" {#bulk-loeschen}

Setzt die Whitelist komplett zurück. Danach greift wieder [Auto-Mode](#auto-mode). Nützlich,
wenn du:

- Die Whitelist neu strukturieren willst und mit leerem Stand beginnen möchtest.
- Festgestellt hast, dass der konfigurierte Kreis zu eng ist und Auto-Mode (alle berechtigten
  Personen) besser passt.

Der Confirm-Dialog nennt die Anzahl der Personen, die entfernt werden, plus den Hinweis
„Danach greift wieder Auto-Mode."

## Abgrenzung zum regulären Benachrichtigungs-Kreis {#abgrenzung-regulaer}

Es gibt **zwei separate Kreise** pro Arbeitsort:

| Kreis | Zweck | Verwaltung |
|---|---|---|
| **Regulär** (Benachrichtigungs-Kreis) | Empfänger bei klassischen Absagen vor Ablauf der Frist | `/dispatcher/notification-circles` |
| **Notfall** (Notfall-Whitelist) | Empfänger nach Ablauf der Frist (= Notfall-Absage) | `/dispatcher/emergency-notification-circles` |

Beide Kreise sind unabhängig voneinander. Der Notfall-Kreis ist explizit als **kleiner und
verlässlicher** gedacht: bei kurzfristigen Absagen kommt es auf schnelle Reaktion an, und nicht
jede:r möchte oder kann das übernehmen.

Den Workflow aus Sicht der Mitarbeiter:innen siehst du im
[Mitarbeiter-Topic „Termin absagen"](/help/employee/cancellation) im Abschnitt **Notfall-
Absage**.

## Häufige Fragen {#haeufige-fragen}

**Was passiert, wenn ich keine Whitelist konfiguriere?**

Genau das ist der Auto-Mode: das System nutzt für Notfälle den **gleichen Personenkreis wie
beim regulären Workflow**. Wenn du keine Sonderregelung brauchst, lass die Whitelist leer.

**Wie sehe ich, wer aktuell in beiden Kreisen steht?**

Auf der Detail-Seite des Arbeitsortes siehst du nur die **Notfall-Whitelist** und die
**Anzahl** im regulären Kreis (am „Aus regulärem Kreis übernehmen"-Button). Die volle Personen-
Liste des regulären Kreises pflegst du separat unter `/dispatcher/notification-circles`.

**Was ist mit Personen, die in der Whitelist stehen, aber das Team verlassen haben?**

Sie verschwinden automatisch aus dem effektiven Empfängerkreis — der **Pool-Filter** greift bei
jeder Benachrichtigungs-Berechnung. Bestand der Whitelist-Einträge bleibt aber sichtbar (für
Audit-Zwecke). Spätestens beim Aufräumen über „Alle entfernen" oder beim erneuten „Aus
regulärem Kreis übernehmen" wirst du diese Karteileichen los.

**Erhalten Personen mit deaktiviertem Notfall-Telefon-Toggle trotzdem die Benachrichtigung?**

Ja. Der Toggle in deren Profil steuert nur, ob die **Telefonnummer** in der Kontakt-Mail an die
absagende Person erscheint — Inbox- und E-Mail-Benachrichtigung an die Whitelist-Mitglieder
selbst sind davon unberührt.

**Kann ein:e Mitarbeiter:in selbst in den Notfall-Kreis wechseln?**

Nein. Die Zuordnung erfolgt ausschließlich über die Disposition — bewusst, weil die
Notfall-Mitarbeit ein Verlässlichkeits-Versprechen ist und nicht jede:r kurzfristig einspringen
kann oder will.