"""
Paket für E-Mail-Templates.

Dieses Paket enthält die Basis-Template-Klasse und spezifische Template-Implementierungen.
"""

from .base import EmailTemplate
from .plan_notify import PlanNotificationTemplate
from .request import AvailabilityRequestTemplate
