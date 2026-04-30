# E-Mail-Setup

Der Web-API-Server versendet Mails (Auth, Cancellations, Swap-Requests, Plan-
Notifications etc.) über einen SMTP-Server, dessen Zugangsdaten in der DB
gespeichert sind. Die SMTP-Passwörter werden mit einem Fernet-Master-Key
verschlüsselt; der Master-Key liegt als Env-Var `EMAIL_ENCRYPTION_KEY`.

## Erst-Setup (lokal)

1. Master-Key generieren:

   ```bash
   uv run --package hcc-plan-web-api python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. Den ausgegebenen 44-Zeichen-String in die `.env` eintragen:

   ```env
   EMAIL_ENCRYPTION_KEY=<hier-einfügen>
   ```

3. Web-API-Server starten. Beim ersten Aufruf eines Mail-versendenden
   Endpoints (z. B. `/auth/forgot-password`) wirft der Server einen
   `EmailNotConfiguredError`, weil noch keine SMTP-Daten in der DB stehen.

4. Als Admin einloggen, im Dashboard die Kachel **„E-Mail-Einstellungen"**
   öffnen (oder direkt `/admin/email-settings`).

5. SMTP-Server eintragen:
   - **Host / Port**: vom Provider (z. B. `smtp.gmail.com:587`,
     `smtp-relay.brevo.com:587`, `smtp.sendgrid.net:587`).
   - **Benutzername / Passwort**: provider-spezifisch (Gmail: App-Password
     erzeugen, **nicht** das Login-Passwort; Sendgrid: API-Key als Username).
   - **STARTTLS**: für Port 587 in der Regel ein. **SSL/TLS-only**: nur für
     Port 465.
   - **Absender-Adresse**: muss vom Provider als „verifiziert" akzeptiert sein
     (sonst wird die Mail abgelehnt oder landet im Spam).
   - **Absender-Name** (optional): erscheint im `From`-Header vor der Adresse,
     z. B. `"hcc plan" <noreply@example.com>`.

6. **Speichern** drücken — die Settings werden persistiert.

7. **Test-Mail an mich senden** drücken — die Mail geht synchron raus, und du
   siehst Erfolg oder den konkreten SMTP-Fehler als Banner.

## Production-Setup (Render)

1. Im Render-Dashboard für den Web-API-Service unter **Environment** eine neue
   Variable anlegen:

   ```
   EMAIL_ENCRYPTION_KEY=<wie oben generieren — NICHT den Dev-Wert wiederverwenden>
   ```

   Render speichert Env-Vars verschlüsselt; der Wert sollte **nirgends sonst**
   liegen (auch nicht im Repo, auch nicht in `.env.production`, das nur
   ein gitignored Cheat-Sheet ist).

2. Service redeployen (Render macht das automatisch beim Speichern der
   Env-Var).

3. Schritte 4–7 aus dem Lokal-Setup wiederholen, diesmal gegen die Produktion.

## Schlüssel-Rotation

**Heute nicht implementiert.** Wenn du den Master-Key wechseln willst:

1. Aktuell gilt: alle SMTP-Passwörter in der DB werden unentschlüsselbar.
2. Workaround: nach Key-Rotation die Admin-UI öffnen und die SMTP-Settings
   einmal neu speichern (Passwort eintragen). Damit wird das Passwort mit
   dem neuen Key verschlüsselt.
3. Saubere Lösung wäre `MultiFernet` (alte und neue Keys parallel + Hintergrund-
   Re-Encryption), das ist ein eigener Branch falls je nötig.

## Provider-Empfehlungen

Konkreter Provider ist Kunden-Entscheidung. Alles was SMTP+STARTTLS auf 587
spricht, funktioniert. Häufige Optionen:

| Provider | Free-Tier | DSGVO/EU | Notizen |
|----------|-----------|----------|---------|
| Brevo (ehem. Sendinblue) | 300/Tag | ja, EU-Hosting | einfache Anmeldung, gute Wahl für EU-Kunden |
| Sendgrid | 100/Tag | nein, US | mehr Features, US-Hosting |
| Mailgun | 100/Tag (Karte nötig) | wählbar | gut für höheres Volumen |
| Postmark | kein Free | wählbar | beste Deliverability für Transaktional |
| Gmail (App-Password) | ~500/Tag | n/a | nur für Smoke-Tests |
| Firmeneigener Mail-Server | n/a | n/a | volle Kontrolle, hängt vom Setup ab |

Domain-Authentication (SPF + DKIM) richtet der Admin beim Provider und im
DNS der Absender-Domain ein — ohne SPF/DKIM landen Mails häufig im Spam.

## Versand-Fehler debuggen

Wenn `/admin/email-settings/test` einen SMTP-Fehler zeigt:

- **`SMTPAuthenticationError`**: Username/Passwort falsch. Bei Gmail: prüfen, ob
  ein **App-Password** statt des Login-Passworts genutzt wird. Bei Sendgrid:
  Username muss `apikey` sein, Passwort der API-Key.
- **`SMTPSenderRefused: 5.7.1`**: Absender-Adresse nicht beim Provider
  verifiziert. In der Provider-Konsole die `email_from`-Adresse als „verified
  sender" eintragen.
- **`gaierror: Name or service not known`**: Hostname falsch geschrieben.
- **Timeout / Connection refused**: Port falsch oder vom Render-Plan
  blockiert. Render erlaubt 587/465 outbound, **nicht** 25.

Beim Versand im normalen Betrieb (nicht über die Test-Mail) landet der
Fehler im Server-Log — Suchbegriff `E-Mail-Versand fehlgeschlagen`.