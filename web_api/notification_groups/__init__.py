"""Disponenten-UI fuer die Verwaltung von Notification-Groups (Reminder).

Stellt unter `/dispatcher/notification-groups` die Verwaltung der
Reminder-Buendelung bereit: Liste der Groups pro Team, Anlegen, Rename,
Deadline-Aenderung, Aufloesen, manueller Catchup-Versand und Drag+Drop-
Zuordnung von PlanPerioden zu Groups.

Seit Phase A der NG-Verwaltung kann eine PlanPeriod ohne Group
existieren ("Ohne Reminder"). Diese View ist der einzige Ort, an dem
PPs Groups zugewiesen werden — die PP-Forms enthalten keine
Reminder-Logik mehr.
"""
