---
title: Anmeldedaten (Passwort & Login-E-Mail)
roles: [employee]
category: Konto
order: 100
updated: 2026-05-07
anchors:
  - login-vs-kontakt
  - passwort-aendern
  - email-wechsel
  - email-wechsel-abbrechen
  - sicherheit
  - haeufige-fragen
related:
  - employee/account-profile
---

Im Tab **Anmeldedaten** unter **Mein Konto** verwaltest du dein **Passwort** und deine **Login-E-Mail-Adresse** —
also die Daten, mit denen du dich bei hcc plan anmeldest. Du erreichst die Seite über das Avatar-Symbol
oben rechts oder direkt unter `/account/credentials`.

## Login-E-Mail vs. Kontakt-E-Mail {#login-vs-kontakt}

Wichtige Unterscheidung:

- **Login-E-Mail** (dieser Tab) — die Adresse, mit der du dich anmeldest.
- **Kontakt-E-Mail** (Tab „Profil") — die Adresse, an die hcc plan Benachrichtigungen schickt. Sie
  kann mit der Login-Adresse identisch sein oder davon abweichen (z. B. private vs. dienstliche Mail).

> **Tipp:** Viele Mitarbeiter:innen nutzen ihre dienstliche Adresse zum Login, aber die private
> Adresse für Benachrichtigungen — so siehst du auch am Wochenende, wenn jemand mit dir tauschen will.

## Passwort ändern {#passwort-aendern}

1. Im Bereich **„Passwort ändern"** drei Felder ausfüllen:
   - **Aktuelles Passwort** (Verifikation)
   - **Neues Passwort**
   - **Neues Passwort wiederholen** (Tippfehler-Schutz)
2. **„Passwort speichern"** — bei Erfolg erscheint eine Bestätigung; deine aktuelle Sitzung bleibt
   eingeloggt.

> **Wichtig:** Beim Passwort-Wechsel werden **alle anderen Sitzungen** (anderes Gerät, anderer
> Browser) automatisch ausgeloggt. Das ist Absicht — wenn jemand Unbefugtes Zugriff hatte, ist er
> oder sie nach dem Wechsel draußen.

### Häufige Fehler beim Passwort-Wechsel

| Meldung | Ursache                                                         |
|---|-----------------------------------------------------------------|
| „Aktuelles Passwort ist falsch" | Tippfehler im ersten Feld; Caps-Lock prüfen                     |
| „Die beiden neuen Passwörter stimmen nicht überein" | Wiederhol-Feld weicht ab                                        |
| „Passwort zu kurz" | Mindestlänge wird vom System vorgegeben (typisch 12-16 Zeichen) |

## Login-E-Mail wechseln {#email-wechsel}

Der Wechsel der Login-Adresse ist ein **zweistufiger Prozess** — wir verschicken einen
Bestätigungs-Link an die neue Adresse, damit ein Tippfehler dich nicht aussperrt.

1. Im Bereich **„Login-Adresse ändern"** die **neue E-Mail-Adresse** eintragen und **„Ändern"** klicken.
2. Sofort danach gehen **zwei E-Mails** raus:
   - **An die neue Adresse**: Bestätigungs-Mail mit Link.
   - **An die alte Adresse**: Hinweis-Mail („deine Anmeldeadresse wird bald gewechselt"). Falls du
     das nicht warst — nichts tun, der Wechsel verfällt automatisch.
3. **Klicke auf den Link in der Bestätigungs-Mail.** Die neue Adresse wird aktiviert.
4. Ab dem nächsten Login meldest du dich mit der neuen Adresse an.

> **Wichtig:** Solange der Link nicht angeklickt ist, bleibt die alte Adresse aktiv. Du kannst dich
> während des laufenden Wechsels weiterhin mit der alten Adresse anmelden.

### Wenn der Link auf einem anderen Gerät geöffnet wird

Wenn du den Bestätigungs-Link z. B. auf dem Handy öffnest, während dein Laptop noch mit der alten
Adresse eingeloggt ist: kein Problem. Auf dem Laptop bleibt die Sitzung gültig, bis du dich neu
einloggst — dann mit der neuen Adresse.

## Adressänderung abbrechen {#email-wechsel-abbrechen}

Solange der Bestätigungs-Link **noch nicht angeklickt** wurde, kannst du den Wechsel zurückziehen:

1. Im Bereich **„Login-Adresse ändern"** erscheint ein Hinweis mit der ausstehenden neuen Adresse
   und einem **„Anfrage zurückziehen"-Button**.
2. Klick darauf — der Bestätigungs-Link in der Mail funktioniert anschließend nicht mehr.

> Das ist nützlich, wenn du z. B. einen Tippfehler in der neuen Adresse gemacht hast oder es dir
> anders überlegt hast.

## Sicherheit {#sicherheit}

- **5-Minuten-Throttle**: zwischen zwei Adresswechsel-Anfragen müssen 5 Minuten liegen — verhindert
  Mail-Spam und Brute-Force-Versuche auf den Token.
- **Rate-Limit**: maximal 3 Adresswechsel und 10 Passwort-Wechsel pro Stunde.
- **User-Enumeration-Schutz**: das System gibt **immer** dieselbe Bestätigungs-Meldung („wenn die
  Adresse verfügbar ist…") zurück, auch wenn die Adresse bereits anderweitig vergeben oder mit deiner
  aktuellen identisch ist. So kann niemand durch Eingabe einer fremden Adresse herausfinden, wer hier
  Konten hat.

## Häufige Fragen {#haeufige-fragen}

**Ich habe meine Login-E-Mail vergessen — was nun?**
Sprich mit deiner Disposition oder dem hcc-plan-Administrator. Es gibt keinen
Self-Service-Wiederherstellungsweg, weil das System sonst über die Antwort verraten würde, ob die
Adresse existiert.

**Werde ich nach einem Passwort-Wechsel auf allen Geräten ausgeloggt?**
Ja, mit Ausnahme der **aktuellen Sitzung** im Browser, in dem du das Passwort gewechselt hast.
Diese Sitzung bekommt frische Tokens.

**Wenn ich beide Mails (alte + neue Adresse) nicht mehr empfangen kann, komm ich noch ans Konto?**
Nein, in dem Fall musst du deine Disposition oder den Administrator bitten, die Login-Adresse manuell
zurückzusetzen.

**Was ist mit Multi-Faktor-Authentifizierung?**
Aktuell bietet hcc plan keine MFA an. Sicheres Passwort-Hygiene und ein zugriffsgeschützter
Mail-Account sind die wichtigsten Schutzmaßnahmen.
