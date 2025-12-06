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
import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase
from sat_solver.constraints.fixed_cast_helpers import (
    parse_and_filter_fixed_cast,
    check_pers_id_in_shift_vars,
    extract_person_uuids,
    has_only_and_operators,
)
from sat_solver.constraints.base import ValidationError, ValidationInfo

if TYPE_CHECKING:
    from database import schemas


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

    def validate_plan(self, plan: 'schemas.PlanShow') -> list[ValidationError | ValidationInfo]:
        """
        Prüft ob bevorzugte Events korrekt ausgewählt wurden.
        
        Validiert bei EventGroup-Hierarchien, wo nur ein Subset der Events stattfindet:
        - Wurden Events MIT prefer_fixed_cast_events bevorzugt ausgewählt?
        - Hätte ein bevorzugtes Event statt einem normalen Event gewählt werden können?
        
        Gibt auch einen Hinweis aus, wenn es mehr bevorzugte Events gibt als
        ausgewählt werden können (Konfliktfall ohne eindeutige Lösung).
        
        Returns:
            Liste mit ValidationError (Fehler) und ValidationInfo (Hinweise)
        """
        from sat_solver.constraints.base import ValidationError, ValidationInfo
        
        errors: list[ValidationError | ValidationInfo] = []
        
        # Sammle alle Event-IDs die im Plan sind
        events_in_plan = {app.event.id for app in plan.appointments}
        
        # Lookup: event_id -> cast_group
        cast_group_by_event_id = {
            cg.event.id: cg 
            for cg in self.entities.cast_groups_with_event.values()
            if cg.event is not None
        }
        
        # Bereits geprüfte Parent-EventGroups (um Duplikate zu vermeiden)
        checked_parent_groups = set()
        
        # Iteriere über alle EventGroups die eine Auswahl treffen
        for event_group in self.entities.event_groups.values():
            # Nur EventGroups die ein Subset ihrer Children auswählen
            if event_group.nr_of_active_children is None:
                continue
            
            # Bereits geprüft?
            if event_group.event_group_id in checked_parent_groups:
                continue
            checked_parent_groups.add(event_group.event_group_id)
            
            # Sammle Children mit Events
            children_with_event = [c for c in event_group.children if c.event]
            if not children_with_event:
                continue
            
            # Werden alle Children ausgewählt? Dann keine Prüfung nötig
            if event_group.nr_of_active_children >= len(children_with_event):
                continue
            
            # Kategorisiere Events: gewählt vs. nicht gewählt, bevorzugt vs. normal
            chosen_preferred = []
            chosen_normal = []
            not_chosen_preferred = []
            not_chosen_normal = []
            
            for child_eg in children_with_event:
                event = child_eg.event
                cast_group = cast_group_by_event_id.get(event.id)
                
                # Prüfe ob Event als "bevorzugt" gilt
                is_preferred = self._is_event_preferred(cast_group)
                
                event_info = {
                    'event': event,
                    'cast_group': cast_group,
                    'event_group': child_eg,
                }
                
                if event.id in events_in_plan:
                    if is_preferred:
                        chosen_preferred.append(event_info)
                    else:
                        chosen_normal.append(event_info)
                else:
                    if is_preferred:
                        not_chosen_preferred.append(event_info)
                    else:
                        not_chosen_normal.append(event_info)
            
            # Fehler: Normale Events gewählt, aber bevorzugte Events übergangen
            if chosen_normal and not_chosen_preferred:
                for normal_event_info in chosen_normal:
                    for preferred_event_info in not_chosen_preferred:
                        normal_event: schemas.Event = normal_event_info['event']
                        preferred_event = preferred_event_info['event']
                        preferred_cg = preferred_event_info['cast_group']
                        
                        # Finde Person(en) der festen Besetzung
                        fixed_cast_text = self._get_fixed_cast_persons_text(preferred_cg)
                        
                        errors.append(ValidationError(
                            category="Bevorzugtes Event nicht gewählt",
                            message=(
                                f'Statt {normal_event.date:%d.%m.%y} ({normal_event.time_of_day.name}), '
                                f'{normal_event.location_plan_period.location_of_work.name_an_city}<br>'
                                f'hätte bevorzugt werden sollen: '
                                f'{preferred_event.date:%d.%m.%y} ({preferred_event.time_of_day.name}), '
                                f'{preferred_event.location_plan_period.location_of_work.name_an_city}<br>'
                                f'Feste Besetzung: {fixed_cast_text}'
                            )
                        ))
                        # Nur einen Fehler pro normalem Event ausgeben
                        break
            
            # Hinweis: Mehr bevorzugte Events als Slots (Konfliktfall)
            total_preferred = len(chosen_preferred) + len(not_chosen_preferred)
            if total_preferred > event_group.nr_of_active_children and not_chosen_preferred:
                preferred_events_lines: list[tuple[tuple[datetime.date, int], str]] = []
                for e in (chosen_preferred + not_chosen_preferred):
                    event: schemas.Event = e["event"]
                    cast_group = e["cast_group"]
                    fixed_cast_text = self._get_fixed_cast_persons_text(cast_group)
                    preferred_events_lines.append(
                        ((event.date, event.time_of_day.time_of_day_enum.time_index),
                         f'&nbsp;&nbsp;&nbsp;{event.date:%d.%m.%y} ({event.time_of_day.name}) - '
                         f'{event.location_plan_period.location_of_work.name_an_city}<br>'
                         f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;zu besetzen: {fixed_cast_text}')
                    )
                preferred_events_text = '<br>'.join(line[1] for line in sorted(preferred_events_lines,
                                                                               key=lambda x: (x[0][0], x[0])[1]))
                errors.append(ValidationInfo(
                    category="Feste Besetzung: Keine eindeutige Lösung",
                    message=(
                        f'Es gibt {total_preferred} bevorzugte Events, aber nur '
                        f'{event_group.nr_of_active_children} können stattfinden.<br>'
                        f'Bevorzugte Events:<br>{preferred_events_text}'
                    )
                ))
        
        return errors
    
    def _is_event_preferred(self, cast_group) -> bool:
        """
        Prüft ob ein Event als "bevorzugt" gilt.
        
        Ein Event gilt als bevorzugt wenn:
        - prefer_fixed_cast_events=True
        - fixed_cast vorhanden
        - Bei only_if_available=True: Mindestens eine Person verfügbar
        """
        if not cast_group:
            return False
        if not cast_group.prefer_fixed_cast_events:
            return False
        if not cast_group.fixed_cast:
            return False
        
        # Prüfe Verfügbarkeit wenn only_if_available
        if cast_group.fixed_cast_only_if_available:
            from sat_solver.constraints.fixed_cast_helpers import (
                parse_fixed_cast_string,
                filter_unavailable_persons,
                is_empty_list,
            )
            fixed_cast_as_list = parse_fixed_cast_string(cast_group.fixed_cast)
            fixed_cast_as_list = filter_unavailable_persons(
                fixed_cast_as_list, cast_group, self.entities
            )
            if not fixed_cast_as_list or is_empty_list(fixed_cast_as_list):
                return False  # Keine Person verfügbar -> nicht bevorzugt
        
        return True
    
    def _get_fixed_cast_persons_text(self, cast_group) -> str:
        """Gibt lesbaren Text der festen Besetzung zurück."""
        if not cast_group or not cast_group.fixed_cast:
            return "unbekannt"
        
        from tools.helper_functions import generate_fixed_cast_clear_text
        return generate_fixed_cast_clear_text(
            cast_group.fixed_cast,
            cast_group.fixed_cast_only_if_available,
            cast_group.prefer_fixed_cast_events
        )
    
