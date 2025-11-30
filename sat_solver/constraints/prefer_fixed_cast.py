"""
PreferFixedCastConstraint - Soft Constraint für bevorzugte Events.

Dieses Constraint implementiert die prefer_fixed_cast_events Logik:
- Events mit fixed_cast UND prefer_fixed_cast_events=True werden bevorzugt
- Penalty-Variablen werden erstellt wenn bevorzugte Events nicht gewählt werden

Strategie:
- Bei reinem AND (z.B. "uuid1 AND uuid2"): Pro Mitarbeiter 1 Penalty
  → 2 Mitarbeiter nicht besetzt = 2 Penalties
- Bei OR-Operatoren: 1 Penalty pro Event (Event-basierte Logik)
"""

from uuid import UUID

from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase
from sat_solver.constraints.fixed_cast_helpers import (
    parse_and_filter_fixed_cast,
    check_pers_id_in_shift_vars,
    extract_person_uuids,
    has_only_and_operators,
)


class PreferFixedCastConstraint(ConstraintBase):
    """
    Soft Constraint für bevorzugte Events (prefer_fixed_cast_events).
    
    Erstellt Penalty-Variablen für Events die:
    1. Eine feste Besetzung haben (fixed_cast)
    2. Als bevorzugt markiert sind (prefer_fixed_cast_events=True)
    3. Eine echte Auswahl haben (Parent wählt nur Subset der Children)
    
    Bei AND-Operatoren wird pro Person eine Penalty erstellt.
    Bei OR-Operatoren wird pro Event eine Penalty erstellt.
    """
    
    name = "prefer_fixed_cast"
    weight_attribute = "prefer_fixed_cast_events"
    
    def apply(self) -> None:
        """
        Erstellt Preference-Penalty-Variablen für bevorzugte Events.
        """
        print("\n" + "="*80)
        print("DEBUG: prefer_fixed_cast_events - Penalty-Variablen werden erstellt")
        print("="*80)
        
        for cast_group in self.entities.cast_groups_with_event.values():
            # 1. Grundvoraussetzungen prüfen
            if not (cast_group.fixed_cast and cast_group.prefer_fixed_cast_events):
                continue
            
            print(f"\nEvent gefunden: {cast_group.event.date:%d.%m.%y} "
                  f"({cast_group.event.time_of_day.name}), "
                  f"{cast_group.event.location_plan_period.location_of_work.name_an_city}")
            
            # 2. Relevanz-Prüfung: Ist Preference überhaupt relevant?
            if not self._is_preference_relevant(cast_group):
                continue
            
            # 3. Verfügbarkeits-Prüfung (bei fixed_cast_only_if_available)
            fixed_cast_as_list = parse_and_filter_fixed_cast(cast_group, self.entities)
            if fixed_cast_as_list is None:
                print("     ✗ Übersprungen: Event nicht besetzbar (keine verfügbaren Personen)")
                continue
            
            # 4. Erstelle Preference-Variable basierend auf Operator-Typ
            self._create_preference_vars(cast_group, fixed_cast_as_list)
        
        print("\n" + "="*80)
        print(f"DEBUG: Zusammenfassung prefer_fixed_cast_events")
        print(f"  Gesamtanzahl Penalty-Variablen erstellt: {len(self.penalty_vars)}")
        print("="*80 + "\n")
    
    def _is_preference_relevant(self, cast_group) -> bool:
        """
        Prüft ob die Preference für dieses Event überhaupt relevant ist.
        
        Relevant ist sie nur wenn:
        - Es eine Parent-Group gibt (sonst keine Auswahl)
        - Die Parent-Group nur ein Subset der Children auswählt
        
        Returns:
            True wenn Preference relevant ist
        """
        parent_cast_group = cast_group.parent
        if not parent_cast_group:
            print("     ✗ Übersprungen: Keine Parent-Group (keine Auswahl)")
            return False
        
        # Hole die zugehörige EventGroup
        event_group_id = cast_group.event.event_group.id
        event_group = self.entities.event_groups_with_event.get(event_group_id)
        if not event_group or not event_group.parent:
            print("     ✗ Übersprungen: Keine Parent EventGroup")
            return False
        
        parent_event_group = event_group.parent
        
        # Prüfe ob Parent überhaupt eine Auswahl trifft
        nr_of_active_children = parent_event_group.nr_of_active_children
        if nr_of_active_children is None:
            print("     ✗ Übersprungen: Alle Children werden ausgewählt (nr_of_active_children=None)")
            return False
        
        # Zähle die Children der Parent-Group die Events haben
        children_with_event = [c for c in parent_event_group.children if c.event]
        if nr_of_active_children >= len(children_with_event):
            print(f"     ✗ Übersprungen: Alle Events werden ausgewählt "
                  f"(nr_of_active_children={nr_of_active_children} >= "
                  f"children_with_event={len(children_with_event)})")
            return False
        
        print(f"     ✓ Relevanz-Check bestanden! nr_of_active_children={nr_of_active_children}, "
              f"children_with_event={len(children_with_event)}")
        return True
    
    def _create_preference_vars(self, cast_group, fixed_cast_as_list: tuple | str) -> None:
        """
        Erstellt Preference-Variablen basierend auf Operator-Typ.
        
        Args:
            cast_group: Die CastGroup
            fixed_cast_as_list: Geparsete fixed_cast Struktur
        """
        if has_only_and_operators(fixed_cast_as_list):
            self._create_per_person_penalties(cast_group, fixed_cast_as_list)
        else:
            self._create_event_based_penalty(cast_group)
    
    def _create_per_person_penalties(self, cast_group, fixed_cast_as_list: tuple | str) -> None:
        """
        Strategie A: Pro-Person Penalties (bei reinem AND).
        
        Für jeden Mitarbeiter in der fixed_cast Liste wird eine Penalty-Variable
        erstellt, die 1 ist wenn der Mitarbeiter NICHT zugewiesen ist.
        """
        print(f"     📊 Strategie A: Pro-Person Penalties (nur AND-Operatoren)")
        
        # Extrahiere alle Person-UUIDs aus der verschachtelten Struktur
        person_uuids = extract_person_uuids(fixed_cast_as_list)
        print(f"        Anzahl Personen in fixed_cast: {len(person_uuids)}")
        
        for idx, person_uuid in enumerate(person_uuids, 1):
            # Prüfe ob diese Person dem Event zugewiesen ist
            is_assigned_var = check_pers_id_in_shift_vars(
                self.model, self.entities, person_uuid, cast_group
            )
            
            # Finde Person-Namen für bessere Variablen-Benennung
            person = next(
                (app.person for app in self.entities.actor_plan_periods.values() 
                 if app.person.id == person_uuid),
                None
            )
            person_name = person.f_name if person else str(person_uuid)[:8]
            
            penalty_var = self.model.NewIntVar(0, 1, 
                f'Prefer: {cast_group.event.date:%d.%m.%y} '
                f'({cast_group.event.time_of_day.name}), '
                f'{cast_group.event.location_plan_period.location_of_work.name_an_city}, '
                f'{person_name}'
            )
            
            # penalty_var = 1 wenn Mitarbeiter NICHT zugewiesen
            # penalty_var = 0 wenn Mitarbeiter zugewiesen
            self.model.Add(penalty_var == 1 - is_assigned_var)
            
            self.penalty_vars.append(penalty_var)
            print(f"        [{idx}/{len(person_uuids)}] Penalty-Variable erstellt für: {person_name}")
    
    def _create_event_based_penalty(self, cast_group) -> None:
        """
        Strategie B: Event-basierte Penalty (bei OR-Operatoren).
        
        Eine einzige Penalty-Variable die 1 ist wenn das Event NICHT ausgewählt wurde.
        """
        print(f"     📊 Strategie B: Event-basierte Penalty (enthält OR-Operatoren)")
        
        event_group_id = cast_group.event.event_group.id
        
        penalty_var = self.model.NewIntVar(0, 1, 
            f'Prefer: {cast_group.event.date:%d.%m.%y} '
            f'({cast_group.event.time_of_day.name}), '
            f'{cast_group.event.location_plan_period.location_of_work.name_an_city}'
        )
        
        # penalty_var = 1 wenn Event NICHT ausgewählt (entities.event_group_vars[...] == 0)
        # penalty_var = 0 wenn Event ausgewählt (entities.event_group_vars[...] == 1)
        self.model.Add(penalty_var == 1 - self.entities.event_group_vars[event_group_id])
        
        self.penalty_vars.append(penalty_var)
        print(f"        [1/1] Event-basierte Penalty-Variable erstellt")
