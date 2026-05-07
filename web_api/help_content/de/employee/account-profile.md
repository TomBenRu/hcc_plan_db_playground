---
title: Mein Profil (Stammdaten)
roles: [employee]
category: Konto
order: 90
updated: 2026-05-07
anchors:
  - was-kann-ich-aendern
  - daten-bearbeiten
  - validierung
  - haeufige-fragen
related:
  - employee/account-credentials
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
| **Straße / PLZ / Ort** | Ja | Optional, für Abrechnung relevant |
| Login-E-Mail | Nein, hier | Wechsel über **Anmelde­daten** (eigenes Hilfe-Thema) |

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
