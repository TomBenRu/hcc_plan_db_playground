# sat_solver/constraints/event_groups_activity.py
"""
Hard Constraint für Event-Gruppen-Aktivität.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sat_solver.constraints.base import ConstraintBase, Validatable

if TYPE_CHECKING:
    from database import schemas


class EventGroupsActivityConstraint(ConstraintBase):
    """
    Hard Constraint für die Aktivität von Event-Gruppen.
    
    Dieses Constraint stellt sicher, dass nur so viele Child-Event-Groups
    aktiv sind, wie in der Parent-Event-Group mit dem Parameter
    `nr_of_active_children` angegeben ist.
    
    Logik:
    - Für jede Event-Group mit Kindern wird geprüft
    - `nr_of_active_children` wird entweder explizit gesetzt oder berechnet
      als Anzahl der Kinder die selbst Kinder oder Events haben
    - Für Root-Event-Groups: sum(child_vars) == nr_of_active_children
    - Für Child-Event-Groups: sum(child_vars) == nr_of_active_children * parent_var
      (damit keine Kinder aktiv sind wenn der Parent nicht aktiv ist)
    
    Dies ist ein **Hard Constraint** ohne Penalty-Variablen.
    
    Attributes:
        name: "event_groups_activity"
        weight_attribute: "" (leer, da Hard Constraint ohne Weight)
    """
    
    name = "event_groups_activity"
    weight_attribute = ""  # Hard Constraint, kein Weight benötigt
    
    def apply(self) -> None:
        """
        Wendet das Event-Groups-Activity Constraint an.
        
        Für jede Event-Group mit Kindern wird ein Constraint hinzugefügt,
        das die Anzahl aktiver Kinder begrenzt.
        """
        for event_group_id, event_group in self.entities.event_groups.items():
            # Überspringe Event-Groups ohne Kinder
            if not event_group.children:
                continue
            
            # Berechne die Anzahl aktiver Kinder
            # Entweder explizit gesetzt oder Anzahl der relevanten Kinder
            relevant_children = [c for c in event_group.children if c.children or c.event]
            nr_of_active_children = (
                event_group.nr_of_active_children
                or len(relevant_children)
            )
            
            # Hole die Variablen für alle relevanten Kinder
            child_vars = [
                self.entities.event_group_vars[c.event_group_id]
                for c in relevant_children
            ]
            
            # Root-Event-Groups sind garantiert aktiv
            if event_group.is_root:
                self.model.Add(sum(child_vars) == nr_of_active_children)
            else:
                # Child-Event-Groups können inaktiv sein
                # In diesem Fall sollen keine Kinder aktiv sein
                self.model.Add(
                    sum(child_vars) == nr_of_active_children * self.entities.event_group_vars[event_group_id]
                )


    def validate_plan(self, plan: 'schemas.PlanShow') -> list['ValidationError']:
        """
        Prüft ob für jede EventGroup die korrekte Anzahl an Kindern aktiv ist.
        
        Eine EventGroup ist aktiv wenn:
        - Sie ein Event hat und dieses Event im Plan ist, ODER
        - Sie Kinder hat von denen mindestens eines aktiv ist
        
        Für jede EventGroup mit Kindern muss gelten:
        - Anzahl aktiver relevanter Kinder == nr_of_active_children
        """
        from database import schemas
        from sat_solver.constraints.base import ValidationError
        
        errors = []
        
        # Sammle alle Event-IDs aus dem Plan
        event_ids_in_plan: set[UUID] = {
            appointment.event.id for appointment in plan.appointments
        }
        
        # Cache für berechnete Aktivität (event_group_id -> bool)
        activity_cache: dict[UUID, bool] = {}
        
        def is_event_group_active(event_group) -> bool:
            """Bestimmt rekursiv, ob eine EventGroup aktiv ist."""
            eg_id = event_group.event_group_id
            
            if eg_id in activity_cache:
                return activity_cache[eg_id]
            
            # EventGroup mit Event: aktiv wenn Event im Plan
            if event_group.event:
                result = event_group.event.id in event_ids_in_plan
                activity_cache[eg_id] = result
                return result
            
            # EventGroup mit Kindern: aktiv wenn mindestens ein Kind aktiv
            if event_group.children:
                result = any(is_event_group_active(child) for child in event_group.children)
                activity_cache[eg_id] = result
                return result
            
            # Keine Events, keine Kinder -> inaktiv
            activity_cache[eg_id] = False
            return False
        
        def collect_events_from_group(event_group) -> list:
            """Sammelt rekursiv alle Events aus einer EventGroup."""
            events = []
            if event_group.event:
                events.append(event_group.event)
            for child in event_group.children:
                events.extend(collect_events_from_group(child))
            return events
        
        def format_events_summary(events: list) -> str:
            """Formatiert eine Liste von Events als kompakte Zusammenfassung."""
            if not events:
                return "(keine Events)"
            # Sortiere nach Datum und Zeit
            sorted_events = sorted(events, key=lambda e: (e.date, e.time_of_day.time_of_day_enum.time_index))
            # Formatiere als "Datum (Tageszeit) - Ort"
            parts = [
                f'{e.date:%d.%m.%y} ({e.time_of_day.name}) - {e.location_plan_period.location_of_work.name}'
                for e in sorted_events
            ]
            return ', '.join(parts)
        
        # Prüfe jede EventGroup mit Kindern
        for event_group_id, event_group in self.entities.event_groups.items():
            if not event_group.children:
                continue
            
            # Relevante Kinder = haben selbst Kinder oder ein Event
            relevant_children = [c for c in event_group.children if c.children or c.event]
            if not relevant_children:
                continue
            
            # Erwartete Anzahl aktiver Kinder
            expected_active = (
                event_group.nr_of_active_children
                or len(relevant_children)
            )
            
            # Prüfe nur wenn die EventGroup selbst aktiv ist (oder Root ist)
            is_root = event_group.is_root if hasattr(event_group, 'is_root') else (event_group.parent is None)
            if not is_root and not is_event_group_active(event_group):
                continue
            
            # Zähle aktive relevante Kinder
            active_children = [c for c in relevant_children if is_event_group_active(c)]
            actual_active = len(active_children)
            
            if actual_active != expected_active:
                # Erstelle Korrekturvorschlag mit allen relevanten Kindern und ihren Events
                children_descriptions = []
                for child in relevant_children:
                    child_events = collect_events_from_group(child)
                    events_text = format_events_summary(child_events)
                    children_descriptions.append(f'• {events_text}')
                
                children_list = '<br>'.join(children_descriptions)
                
                errors.append(ValidationError(
                    category="Event-Gruppen-Aktivität",
                    message=(
                        f'Erwartet: {expected_active} aktive Varianten<br>'
                        f'Tatsächlich: {actual_active} aktive Varianten<br>'
                        f'<b>Vorschlag zur Korrektur:</b><br>'
                        f'Events von nur {expected_active} der folgenden Eventgruppen dürfen stattfinden:<br>'
                        f'{children_list}'
                    )
                ))
        
        return errors
