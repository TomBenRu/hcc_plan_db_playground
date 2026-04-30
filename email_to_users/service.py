"""Desktop-API-Email-Service: Plan-Notifications, Verfügbarkeitsanfragen, Bulk-Mails.

Versand läuft über die zentrale SMTP-Pipeline aus web_api/email/service.py.
Templates liegen unter web_api/templates/emails/ (Jinja2-HTML/Plaintext-Pärchen).

Diese Klasse wird mit einer SmtpConfig instantiiert, die der Aufrufer aus der
DB lädt. Damit gibt es nur noch eine SMTP-Konfigurationsquelle im System.
"""

import logging
from typing import Any, Dict, List, Optional

from database import schemas
from database.database import get_session
from database.models import Person, Plan, PlanPeriod
from web_api.email.config_loader import SmtpConfig
from web_api.email.service import EmailPayload, _send_one_smtp
from web_api.templating import templates as jinja_templates

logger = logging.getLogger(__name__)


class EmailService:
    """High-Level-Versand für Plan/Availability-Mails."""

    def __init__(self, smtp_config: SmtpConfig):
        self.smtp_config = smtp_config

    def _send_one(self, payload: EmailPayload) -> bool:
        """Sendet eine einzelne Mail. True bei Erfolg, False bei Fehler."""
        try:
            _send_one_smtp(payload, self.smtp_config)
            return True
        except Exception:
            logger.exception("E-Mail-Versand fehlgeschlagen (to=%s)", payload.to)
            return False

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
                if self._send_one(payload):
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
                    "deadline": plan_period.deadline.strftime("%d.%m.%Y"),
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
                if self._send_one(payload):
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
        """Custom-Mail an eine Personen-Liste, eine Mail pro Empfänger."""
        if not recipients:
            return {"success": 0, "failed": 0}

        body = html_content or _text_to_html(text_content)
        stats = {"success": 0, "failed": 0}
        for person in recipients:
            if not person.email:
                stats["failed"] += 1
                continue
            payload = EmailPayload(
                to=[str(person.email)],
                subject=subject,
                html_body=body,
            )
            if self._send_one(payload):
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
        if self._send_one(payload):
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


def _text_to_html(text: str) -> str:
    """Plaintext minimal HTML-tauglich machen (für Custom/Bulk-Mails ohne HTML-Vorlage)."""
    from html import escape
    return f"<pre style=\"font-family:Arial,sans-serif;white-space:pre-wrap;\">{escape(text)}</pre>"