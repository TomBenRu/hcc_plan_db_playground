"""Notfall-Absage-Workflow (intern emergency_absence).

Wird ausgelöst, wenn ein Mitarbeiter nach Ablauf der regulären Absagefrist
seinen Einsatz nicht wahrnehmen kann (z. B. wegen Krankheit). Erstellt eine
`CancellationRequest` mit `kind=emergency`, entfernt den Reporter sofort
aus dem Cast und broadcastet an den Emergency-Notification-Circle.
"""
