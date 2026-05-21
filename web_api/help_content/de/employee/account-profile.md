---
title: Mein Profil (Stammdaten)
roles: [employee]
category: Konto
order: 90
updated: 2026-05-21
anchors:
  - was-kann-ich-aendern
  - daten-bearbeiten
  - validierung
  - notfall-telefon
  - haeufige-fragen
related:
  - employee/account-credentials
  - employee/cancellation
---

Im **Profil-Tab** unter **Mein Konto** pflegst du deine Stammdaten — E-Mail-Adresse, Telefonnummer und
Anschrift. Diese Daten nutzt deine Disposition für die Kommunikation und ggf. Abrechnung.

Du erreichst die Seite über das **Avatar-Symbol** oben rechts in der Navigation oder direkt unter
`/account/profile`.

## Was kann ich hier ändern? {#was-kann-ich-aendern}

| Feld | Bearbeitbar | Hinweis |
|---|---|---|
| Vor- und Nachname | Nein | Nur deine Disposition kann das ändern |
| **E-Mail (Kontakt)** | Ja | Wird für Benachrichtigungen genutzt |
| **Telefonnummer** | Ja | Optional |
| **Geschlecht** | Ja | Optional (weiblich / männlich / divers oder leer) |
| **Straße / PLZ / Ort** | Ja | Optional, für Abrechnung relevant |
| Login-E-Mail | Nein, hier | Wechsel über [Anmeldedaten](/help/employee/account-credentials) |

> **Wichtig:** Die **E-Mail** auf dieser Seite ist deine **Kontakt-Adresse** für Benachrichtigungen.
> Sie kann von deiner **Login-E-Mail** abweichen — die Login-Adresse änderst du im Tab
> **Anmeldedaten**, nicht hier.

## Daten bearbeiten {#daten-bearbeiten}

1. Felder direkt im Formular anpassen.
2. **„Speichern"** — eine Bestätigungsmeldung erscheint oben.
3. Bei Fehleingaben (siehe nächster Abschnitt) zeigt das Formular rote Hinweise; nichts wird gespeichert,
   bis alle Fehler behoben sind.

## Validierung — was wird geprüft? {#validierung}

Beim Speichern prüft das System:

- **E-Mail** — gültiges Format, maximal 50 Zeichen, Domain muss existieren (DNS/MX-Check). Tippfehler
  wie `gmial.com` werden erkannt und abgelehnt.
- **Telefonnummer** — maximal 50 Zeichen. Format wird **nicht** geprüft (international vs. national).
- **Straße / PLZ / Ort** — keine inhaltliche Validierung; PLZ-Format ist frei (für nicht-deutsche Adressen).

> **Tipp:** Wenn die Domain-Prüfung scheitert, obwohl die Adresse korrekt ist (z. B. neuere Domain,
> die DNS-Resolver noch nicht kennen), warte 5–10 Minuten und versuche erneut.

## Telefonnummer in Notfällen teilen {#notfall-telefon}

Unterhalb des Telefon-Feldes findest du die Option **„Telefonnummer in Notfällen teilen"**.
Sie steuert, ob deine Nummer in der **Kontakt-Liste** auftaucht, die bei einer
[Notfall-Absage](/help/employee/cancellation) an die absagende Person verschickt wird.

**Hintergrund:** Wenn eine Kollegin oder ein Kollege kurz vor einem Termin krank wird und eine
Notfall-Absage stellt, bekommt sie/er eine E-Mail mit den Telefonnummern erreichbarer Kontakte
am gleichen Einsatzort. So kann sie/er sich direkt persönlich um Ersatz kümmern, statt nur auf
die automatische Benachrichtigung über das System zu hoffen.

| Toggle | Bedeutung |
|---|---|
| **Aktiv** (Standard) | Deine Telefonnummer erscheint in Notfall-Mails an Kolleg:innen |
| **Inaktiv** | Deine Nummer wird **nicht** geteilt — nur Name und ggf. E-Mail sichtbar |

> **Hinweis:** Auch wenn du den Toggle deaktivierst, bleibst du weiterhin im
> **Benachrichtigungs-Kreis** für Notfälle (wenn deine Disposition dich dafür vorgesehen hat).
> Du bekommst weiterhin Inbox- und E-Mail-Nachrichten — nur dein Telefonanschluss ist dann
> für andere Mitarbeiter:innen nicht sichtbar.

## Häufige Fragen {#haeufige-fragen}

**Warum kann ich meinen Namen nicht ändern?**

Vor- und Nachname sind in deinem **Personen-Datensatz** hinterlegt, der zentral von der Disposition
verwaltet wird. Bitte sprich deine Disposition an, wenn ein Name geändert werden soll
(z. B. nach Heirat, Schreibfehler).

**Wofür wird meine Adresse verwendet?**

Primär für die **Abrechnung** — falls dein Team z. B. Reisekosten oder Honorare abrechnet, brauchen
sie eine zustellbare Anschrift. Für die operative Planung selbst ist die Adresse nicht nötig.

**Was passiert, wenn ich meine Kontakt-E-Mail ändere — bekommt sofort die neue Adresse Mails?**

Ja, ab dem nächsten gesendeten E-Mail-Trigger geht alles an die neue Adresse.

**Wo finde ich meine bisher gespeicherten Daten?**

Sie werden beim Öffnen der Seite automatisch geladen — vorausgefüllt, falls schon eingegeben, oder leer.

**Wer sieht meine Telefonnummer noch, wenn der Notfall-Toggle inaktiv ist?**

Deine **Disposition** sieht sie immer (Stammdaten-Sicht). Andere Mitarbeiter:innen sehen sie
**nur**, wenn der Toggle aktiv ist und konkret eine Notfall-Absage einen Kontakt-Anruf an dich
sinnvoll macht. Im normalen Plan- und Kalender-Betrieb ist deine Nummer für Kolleg:innen nie
sichtbar.
