"""Desktop-API-Email-Service: Plan-Notifications, Verfügbarkeitsanfragen, Bulk-Mails.

Versand läuft über die zentrale SMTP-Pipeline aus web_api/email/service.py.
Templates liegen unter web_api/templates/emails/ (Jinja2-HTML/Plaintext-Pärchen).

Diese Klasse wird mit einer SmtpConfig instantiiert, die der Aufrufer aus der
DB lädt. Damit gibt es nur noch eine SMTP-Konfigurationsquelle im System.
"""

import logging
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy import select as sa_select

from database import schemas
from database.database import get_session
from database.models import (
    NotificationGroup,
    NotificationLog,
    Person,
    Plan,
    PlanPeriod,
)
from web_api.email.config_loader import SmtpConfig
from web_api.email.service import EmailPayload, _send_one_smtp
from web_api.templating import templates as jinja_templates

logger = logging.getLogger(__name__)


# ── Reminder-Konstanten ───────────────────────────────────────────────────────
# kind ∈ {"t7", "t3", "t1", "catchup", "manual"} — Konsistent mit den
# Scheduler-Job-IDs (`reminder:{group.id}:{kind}`) und dem notification_log.
_REMINDER_TEMPLATE = {
    "t7": "availability_reminder_t7.html",
    "t3": "availability_reminder_t3.html",
    "t1": "availability_reminder_t1.html",
    "catchup": "availability_reminder_catchup.html",
}
_REMINDER_SUBJECT = {
    "t7": "Erinnerung: Verfügbarkeitseingabe — Deadline in 7 Tagen",
    "t3": "Erinnerung: Verfügbarkeitseingabe — Deadline in 3 Tagen",
    "t1": "Letzte Erinnerung: Deadline morgen",
    "catchup": "Verfügbarkeitsanfrage aktualisiert",
}
_REMINDER_DAYS_LEFT = {"t7": 7, "t3": 3, "t1": 1, "catchup": 0}

# SandboxedEnvironment blockiert Attribut-Zugriffe wie {{ x.__class__ }}
# — Defense-in-Depth gegen versehentliche Code-Injection in User-Templates.
# undefined=Undefined (Default): unbekannte Variablen werden zu leeren Strings
# beim Stringify, statt Exception zu werfen.
_personalization_env = SandboxedEnvironment(autoescape=False)


def _personalize(template_str: str, person: Person) -> str:
    """Rendert einen Custom-Email-Template-String mit Person-Werten.

    Verfügbare Platzhalter (deutsch, konsistent mit den UI-Buttons):
        {{ vorname }}    — Person.f_name
        {{ nachname }}   — Person.l_name
        {{ name }}       — Person.full_name
        {{ email }}      — Person.email
    """
    ctx = {
        "vorname": person.f_name or "",
        "nachname": person.l_name or "",
        "name": person.full_name or "",
        "email": str(person.email) if person.email else "",
    }
    return _personalization_env.from_string(template_str).render(**ctx)


class EmailService:
    """High-Level-Versand für Plan/Availability-Mails."""

    def __init__(self, smtp_config: SmtpConfig):
        self.smtp_config = smtp_config

    def _send_one(self, payload: EmailPayload) -> tuple[bool, str | None]:
        """Sendet eine einzelne Mail.

        Returns: `(True, None)` bei Erfolg, `(False, "<ExcType>: <message>")`
        bei Fehler. Der Fehlertext ist gedacht fuer das Audit-Feld
        `notification_log.error_detail`; das Application-Log bekommt parallel
        einen vollen Stacktrace via `logger.exception`.
        """
        try:
            _send_one_smtp(payload, self.smtp_config)
            return True, None
        except Exception as exc:
            logger.exception("E-Mail-Versand fehlgeschlagen (to=%s)", payload.to)
            return False, f"{type(exc).__name__}: {exc}"

    def _render(self, template_name: str, ctx: Dict[str, Any]) -> str:
        """Rendert ein Jinja2-Template aus web_api/templates/emails/."""
        return jinja_templates.get_template(f"emails/{template_name}").render(**ctx)

    def send_plan_notification(
        self,
        plan_id: str,
        recipient_ids: Optional[List[str]] = None,
        include_attachments: bool = False,
    ) -> Dict[str, Any]:
        """Versendet eine Plan-Benachrichtigung pro Empfänger mit individueller Einsatzliste.

        Anhänge werden in dieser Pipeline nicht unterstützt — wenn der Aufrufer
        include_attachments=True setzt, loggen wir eine Warnung und ignorieren.
        """
        if include_attachments:
            logger.warning(
                "include_attachments=True wird nicht unterstützt — Anhang-Generierung "
                "läuft in dieser Web-API-Pipeline nicht (xlsxwriter ist Desktop-only)."
            )

        with get_session() as session:
            plan = session.get(Plan, plan_id)
            if plan is None:
                return {"success": 0, "failed": 0, "error": "Plan nicht gefunden"}
            plan_period = plan.plan_period
            team = plan_period.team

            recipients = self._resolve_plan_recipients(session, plan, recipient_ids)
            if not recipients:
                return {"success": 0, "failed": 0}

            period_str = (
                f"{plan_period.start.strftime('%d.%m.%Y')} - "
                f"{plan_period.end.strftime('%d.%m.%Y')}"
            )
            stats = {"success": 0, "failed": 0}

            for person in recipients:
                assignments = self._extract_assignments_for_person(plan, person.id)
                if not assignments:
                    continue
                ctx = {
                    "recipient_name": person.full_name,
                    "plan_name": plan.name,
                    "plan_period": period_str,
                    "team_name": team.name,
                    "assignments": assignments,
                    "notes": plan.notes,
                }
                payload = EmailPayload(
                    to=[str(person.email)],
                    subject=f"Neuer Einsatzplan verfügbar: {plan.name}",
                    html_body=self._render("plan_notification.html", ctx),
                )
                if self._send_one(payload)[0]:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1

            return stats

    def send_availability_request(
        self,
        plan_period_id: str,
        recipient_ids: Optional[List[str]] = None,
        url_base: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Versendet Verfügbarkeitsanfragen an die Mitarbeiter eines Planungszeitraums."""
        with get_session() as session:
            plan_period = session.get(PlanPeriod, plan_period_id)
            if plan_period is None:
                return {"success": 0, "failed": 0, "error": "PlanPeriod nicht gefunden"}
            team = plan_period.team

            recipients = self._resolve_period_recipients(session, plan_period, recipient_ids)
            if not recipients:
                return {"success": 0, "failed": 0}

            # Verfuegbarkeits-Anfrage braucht eine Deadline; PPs ohne
            # Notification-Group (Phase A der NG-Verwaltung) haben keine.
            # Caller muss erst per NG-View eine Group zuordnen.
            if plan_period.effective_deadline is None:
                return {
                    "success": 0,
                    "failed": 0,
                    "error": "PlanPeriod hat keine Reminder-Group — Deadline fehlt.",
                }

            month_names = [
                "Januar", "Februar", "März", "April", "Mai", "Juni",
                "Juli", "August", "September", "Oktober", "November", "Dezember",
            ]
            period_name = (
                f"{month_names[plan_period.start.month - 1]} {plan_period.start.year}"
            )
            stats = {"success": 0, "failed": 0}

            for person in recipients:
                url = (
                    f"{url_base.rstrip('/')}/{plan_period.id}/{person.id}"
                    if url_base
                    else None
                )
                ctx = {
                    "recipient_name": person.full_name,
                    "plan_period": period_name,
                    "team_name": team.name,
                    "deadline": plan_period.effective_deadline.strftime("%d.%m.%Y"),
                    "period_start": plan_period.start.strftime("%d.%m.%Y"),
                    "period_end": plan_period.end.strftime("%d.%m.%Y"),
                    "url": url,
                    "notes": notes or plan_period.notes_for_employees,
                }
                payload = EmailPayload(
                    to=[str(person.email)],
                    subject=f"Verfügbarkeitsabfrage: {period_name}",
                    html_body=self._render("availability_request.html", ctx),
                )
                if self._send_one(payload)[0]:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1

            return stats

    def send_availability_reminder(
        self,
        group_id: uuid.UUID,
        kind: str,
        url_base: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Versendet einen Reminder fuer alle Empfaenger einer NotificationGroup.

        kind ∈ {"t7", "t3", "t1", "catchup"}:
          * t7      — alle Team-Members der Gruppen-PPs (Awareness)
          * t3, t1  — nur Empfaenger, die in mindestens einer Gruppen-PP keine
                      AvailDays haben (saumig)
          * catchup — alle Team-Members (informiert ueber neuen Zeitraum)

        Idempotenz: pro `(group_id, person_id, kind)` wird hoechstens einmal
        erfolgreich versendet — schreibt `notification_log`-Zeile pro Versuch
        (success/failure), liest vor jedem Versand den Log und skipped
        Empfaenger mit erfolgreichem vorherigem Eintrag.
        """
        if kind not in _REMINDER_TEMPLATE:
            return {"success": 0, "failed": 0, "skipped": 0,
                    "error": f"Unbekannter kind: {kind!r}"}

        with get_session() as session:
            group = session.get(NotificationGroup, group_id)
            if group is None:
                return {"success": 0, "failed": 0, "skipped": 0,
                        "error": "NotificationGroup nicht gefunden"}
            team = group.team
            if team is None or team.prep_delete is not None:
                return {"success": 0, "failed": 0, "skipped": 0,
                        "error": "Team nicht aktiv"}

            if kind in ("t3", "t1"):
                recipients = self._resolve_group_recipients_saumig(session, group)
            else:
                recipients = self._resolve_group_recipients_t7(session, group)

            stats = {"success": 0, "failed": 0, "skipped": 0}
            template_name = _REMINDER_TEMPLATE[kind]
            subject = _REMINDER_SUBJECT[kind]
            days_left = _REMINDER_DAYS_LEFT[kind]
            deadline_str = group.deadline.strftime("%d.%m.%Y")

            for person in recipients:
                if not person.email:
                    stats["failed"] += 1
                    continue

                if self._reminder_already_sent(session, group.id, person.id, kind):
                    stats["skipped"] += 1
                    continue

                periods_ctx = self._build_group_periods_ctx(group, person, url_base)
                if not periods_ctx:
                    # Kein einziger relevanter Zeitraum fuer diese Person —
                    # vermutlich wurde sie nach Group-Anlage aus dem Team genommen.
                    stats["skipped"] += 1
                    continue

                ctx = {
                    "recipient_name": person.full_name,
                    "team_name": team.name,
                    "deadline": deadline_str,
                    "days_left": days_left,
                    "periods": periods_ctx,
                }
                payload = EmailPayload(
                    to=[str(person.email)],
                    subject=subject,
                    html_body=self._render(template_name, ctx),
                )
                success, error_detail = self._send_one(payload)
                self._log_reminder(
                    session, group.id, person.id, kind, success,
                    error_detail=error_detail,
                )
                # Pro Mail commit, damit der Idempotenz-Schutz auch bei
                # Crash/Restart mitten im Loop greift.
                session.commit()
                if success:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1

            return stats

    def send_custom_email(
        self,
        subject: str,
        text_content: str,
        html_content: Optional[str] = None,
        recipients: Optional[List[schemas.Person]] = None,
    ) -> Dict[str, Any]:
        """Custom-Mail an eine Personen-Liste, eine Mail pro Empfänger.

        Subject und Body werden pro Empfänger via Jinja2 personalisiert.
        Verfügbare Platzhalter: {{ vorname }}, {{ nachname }}, {{ name }},
        {{ email }}. Unbekannte Platzhalter werden zu leeren Strings.
        """
        if not recipients:
            return {"success": 0, "failed": 0}

        body_template = html_content or _text_to_html(text_content)
        stats = {"success": 0, "failed": 0}
        for person in recipients:
            if not person.email:
                stats["failed"] += 1
                continue
            try:
                personalized_subject = _personalize(subject, person)
                personalized_body = _personalize(body_template, person)
            except Exception:
                logger.exception(
                    "Personalisierung fehlgeschlagen für %s — Mail wird übersprungen",
                    person.email,
                )
                stats["failed"] += 1
                continue
            payload = EmailPayload(
                to=[str(person.email)],
                subject=personalized_subject,
                html_body=personalized_body,
            )
            if self._send_one(payload)[0]:
                stats["success"] += 1
            else:
                stats["failed"] += 1
        return stats

    def send_bulk_email(
        self,
        subject: str,
        text_content: str,
        html_content: Optional[str] = None,
        recipients: Optional[List[schemas.Person]] = None,
        cc: Optional[List[schemas.Person]] = None,
        bcc: Optional[List[schemas.Person]] = None,
    ) -> Dict[str, Any]:
        """Bulk-Mail: eine Nachricht an mehrere Empfänger mit To/Cc/Bcc."""
        to_emails = [str(p.email) for p in (recipients or []) if p.email]
        cc_emails = [str(p.email) for p in (cc or []) if p.email]
        bcc_emails = [str(p.email) for p in (bcc or []) if p.email]

        if not (to_emails or cc_emails or bcc_emails):
            return {"success": 0, "failed": 0}

        body = html_content or _text_to_html(text_content)
        payload = EmailPayload(
            to=to_emails or [self.smtp_config.email_from],  # SMTP verlangt mindestens eine To
            cc=cc_emails,
            bcc=bcc_emails,
            subject=subject,
            html_body=body,
        )
        recipient_count = len(to_emails) + len(cc_emails) + len(bcc_emails)
        if self._send_one(payload)[0]:
            return {"success": recipient_count, "failed": 0}
        return {"success": 0, "failed": recipient_count}

    # ── Hilfsfunktionen ────────────────────────────────────────────────────────

    def _resolve_plan_recipients(self, session, plan: Plan, recipient_ids):
        if recipient_ids:
            return [
                p for p in (session.get(Person, pid) for pid in recipient_ids)
                if p is not None
            ]
        recipients = []
        for appointment in plan.appointments:
            for avail_day in appointment.avail_days:
                person = avail_day.actor_plan_period.person
                if person not in recipients:
                    recipients.append(person)
        return recipients

    def _resolve_period_recipients(self, session, plan_period: PlanPeriod, recipient_ids):
        if recipient_ids:
            return [
                p for p in (session.get(Person, pid) for pid in recipient_ids)
                if p is not None
            ]
        recipients = []
        for taa in plan_period.team.team_actor_assigns:
            end_ok = not taa.end or taa.end >= plan_period.start
            start_ok = taa.start <= plan_period.end
            if end_ok and start_ok and taa.person not in recipients:
                recipients.append(taa.person)
        return recipients

    def _extract_assignments_for_person(self, plan: Plan, person_id) -> List[Dict[str, str]]:
        assignments = []
        for appointment in plan.appointments:
            for avail_day in appointment.avail_days:
                if avail_day.actor_plan_period.person.id != person_id:
                    continue
                event = appointment.event
                location = event.location_plan_period.location_of_work
                assignments.append({
                    "date": event.date.strftime("%d.%m.%Y"),
                    "time": event.time_of_day.name,
                    "location": location.name,
                })
        return assignments

    # ── Reminder-Helfer ────────────────────────────────────────────────────────

    def _resolve_group_recipients_t7(
        self, session, group: NotificationGroup
    ) -> List[Person]:
        """Union der Team-Members aller Gruppen-PPs (mit TeamActorAssign-Overlap)."""
        seen: dict[uuid.UUID, Person] = {}
        for pp in group.plan_periods:
            for person in self._resolve_period_recipients(session, pp, None):
                if person.prep_delete is not None:
                    continue
                if person.id not in seen:
                    seen[person.id] = person
        return list(seen.values())

    def _resolve_group_recipients_saumig(
        self, session, group: NotificationGroup
    ) -> List[Person]:
        """Personen mit mind. einer Gruppen-PP ohne AvailDay.

        Pro Person wird gefragt: gibt es eine ActorPlanPeriod in einer der
        Gruppen-PPs, in der die Person noch keinen aktiven AvailDay hat? Wenn
        ja → saumig, Reminder geht raus. Wer ueberall (alle relevanten APPs)
        bereits ≥1 AvailDay hat, ist fuer diese Stufe fertig.
        """
        candidates = self._resolve_group_recipients_t7(session, group)
        saumig: list[Person] = []
        for person in candidates:
            if self._person_has_open_period(group, person):
                saumig.append(person)
        return saumig

    @staticmethod
    def _person_has_open_period(group: NotificationGroup, person: Person) -> bool:
        for pp in group.plan_periods:
            person_app = next(
                (app for app in pp.actor_plan_periods if app.person_id == person.id),
                None,
            )
            if person_app is None:
                continue
            active_avail_days = [ad for ad in person_app.avail_days if ad.prep_delete is None]
            if not active_avail_days:
                return True
        return False

    @staticmethod
    def _build_group_periods_ctx(
        group: NotificationGroup,
        person: Person,
        url_base: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Liste der fuer `person` relevanten Gruppen-PPs mit Status + Link.

        Eine PP ist relevant, wenn die Person dort eine ActorPlanPeriod hat
        (was beim PP-Insert nur passiert, wenn ihr TeamActorAssign mit der PP
        ueberlappt). Status `submitted` ↔ ≥1 aktiver AvailDay; sonst `open`.

        URL-Format: `<url_base>/availability?plan_period_id=<pp_id>` — die
        Web-Verfuegbarkeitsmaske ist Login-gated und identifiziert die Person
        ueber das Auth-Token, nicht ueber URL-Parameter.
        """
        items: list[dict] = []
        for pp in group.plan_periods:
            person_app = next(
                (app for app in pp.actor_plan_periods if app.person_id == person.id),
                None,
            )
            if person_app is None:
                continue
            active_avail_days = [ad for ad in person_app.avail_days if ad.prep_delete is None]
            status = "submitted" if active_avail_days else "open"
            url = (
                f"{url_base.rstrip('/')}/availability?plan_period_id={pp.id}"
                if url_base
                else None
            )
            items.append({
                "label": (
                    f"{pp.start.strftime('%d.%m.%Y')} – "
                    f"{pp.end.strftime('%d.%m.%Y')}"
                ),
                "url": url,
                "status": status,
                "notes_for_employees": pp.notes_for_employees,
            })
        return items

    @staticmethod
    def _reminder_already_sent(
        session,
        group_id: uuid.UUID,
        person_id: uuid.UUID,
        kind: str,
    ) -> bool:
        """True, wenn fuer (group, person, kind) bereits ein erfolgreicher Log existiert."""
        stmt = sa_select(NotificationLog.id).where(
            NotificationLog.notification_group_id == group_id,
            NotificationLog.person_id == person_id,
            NotificationLog.kind == kind,
            NotificationLog.success.is_(True),
        )
        return session.execute(stmt).first() is not None

    @staticmethod
    def _log_reminder(
        session,
        group_id: uuid.UUID,
        person_id: uuid.UUID,
        kind: str,
        success: bool,
        error_detail: Optional[str] = None,
    ) -> None:
        log = NotificationLog(
            notification_group_id=group_id,
            person_id=person_id,
            kind=kind,
            success=success,
            error_detail=error_detail,
        )
        session.add(log)
        session.flush()


def _text_to_html(text: str) -> str:
    """Plaintext minimal HTML-tauglich machen (für Custom/Bulk-Mails ohne HTML-Vorlage)."""
    from html import escape
    return f"<pre style=\"font-family:Arial,sans-serif;white-space:pre-wrap;\">{escape(text)}</pre>"