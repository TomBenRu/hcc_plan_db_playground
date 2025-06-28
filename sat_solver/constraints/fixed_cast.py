"""
FixedCastConstraint - Constraint für feste Besetzungen

Dieser Constraint entspricht der Funktion add_constraints_fixed_cast()
und behandelt vordefinierte feste Besetzungen für Events.
"""

import datetime
from ast import literal_eval
from typing import List, Dict, Tuple
from uuid import UUID

from ortools.sat.python.cp_model import IntVar

from .base import AbstractConstraint
from tools.helper_functions import generate_fixed_cast_clear_text


class FixedCastConstraint(AbstractConstraint):
    """
    Constraint für feste Besetzungen (Fixed Cast).
    
    Dieser Constraint behandelt vordefinierte Besetzungen für Events,
    die als logische Ausdrücke mit Person-UUIDs definiert werden.
    
    Entspricht der ursprünglichen Funktion add_constraints_fixed_cast().
    """
    
    @property
    def constraint_name(self) -> str:
        """Name dieses Constraints."""
        return "fixed_cast"
    
    def create_variables(self) -> List[IntVar]:
        """
        Erstellt Fixed-Cast-Conflict-Variablen.
        
        Für jedes Cast-Group mit fixed_cast wird eine Variable erstellt,
        die anzeigt, ob die feste Besetzung verletzt wird.
        
        Returns:
            Liste der erstellten Fixed-Cast-Conflict-Variablen
        """
        fixed_cast_vars = []
        
        # Dummy-Variable für den Fall dass keine Fixed Casts existieren
        dummy_key = (datetime.date(1999, 1, 1), 'dummy', UUID('00000000-0000-0000-0000-000000000000'))
        dummy_var = self.model.NewBoolVar('dummy_fixed_cast')
        self.add_metadata('fixed_cast_dummy', {dummy_key: dummy_var})
        
        for cast_group in self.entities.cast_groups_with_event.values():
            if not cast_group.fixed_cast:
                continue
            
            try:
                # Parse Fixed Cast String zu Python-Objekt
                fixed_cast_as_list = self._parse_fixed_cast_string(cast_group.fixed_cast)
                
                # Generiere lesbaren Text für die Besetzung
                text_fixed_cast_persons = generate_fixed_cast_clear_text(cast_group.fixed_cast)
                
                # Erstelle Variable mit beschreibendem Namen
                var_name = (f'Datum: {cast_group.event.date: %d.%m.%y} '
                           f'({cast_group.event.time_of_day.name})\n'
                           f'Ort: {cast_group.event.location_plan_period.location_of_work.name_an_city}\n'
                           f'Besetzung: {text_fixed_cast_persons}')
                
                fixed_cast_var = self.model.NewBoolVar(var_name)
                fixed_cast_vars.append(fixed_cast_var)
                
                # Erstelle Constraint für Fixed Cast Validation
                validation_result = self._create_fixed_cast_validation(fixed_cast_as_list, cast_group)
                
                # Fixed Cast Conflict = NOT(validation_result)
                # Wenn das Event stattfindet, muss die Besetzung stimmen
                if cast_group.event.event_group.id in self.entities.event_group_vars:
                    event_group_var = self.entities.event_group_vars[cast_group.event.event_group.id]
                    
                    constraint = self.model.Add(
                        fixed_cast_var == validation_result.Not()
                    ).OnlyEnforceIf(event_group_var)
                else:
                    # Fallback falls Event Group Variable nicht existiert
                    self.model.Add(fixed_cast_var == validation_result.Not())
                
                # Speichere Metadaten für diesen Fixed Cast
                key = (cast_group.event.date, cast_group.event.time_of_day.name, cast_group.event.id)
                self.add_metadata(f'fixed_cast_{len(fixed_cast_vars)-1}', {
                    'key': key,
                    'event_id': str(cast_group.event.id),
                    'cast_group_id': str(cast_group.cast_group_id),
                    'fixed_cast_string': cast_group.fixed_cast,
                    'fixed_cast_persons': text_fixed_cast_persons,
                    'variable_name': var_name
                })
                
            except Exception as e:
                # Fehlerbehandlung für ungültige Fixed Cast Strings
                self.add_metadata(f'fixed_cast_error_{cast_group.cast_group_id}', {
                    'error': str(e),
                    'fixed_cast_string': cast_group.fixed_cast,
                    'event_id': str(cast_group.event.id)
                })
                continue
        
        self.add_metadata('total_fixed_cast_conflicts', len(fixed_cast_vars))
        return fixed_cast_vars
    
    def add_constraints(self) -> None:
        """
        Fügt zusätzliche Fixed-Cast-Constraints hinzu.
        
        Die Hauptlogik ist bereits in create_variables() implementiert.
        """
        constraints_added = 0
        
        # Zusätzliche Fixed-Cast-Constraints können hier hinzugefügt werden
        # Zum Beispiel: Konsistenz-Checks, Validierungen, etc.
        
        self.add_metadata('additional_fixed_cast_constraints', constraints_added)
    
    def _parse_fixed_cast_string(self, fixed_cast_string: str):
        """
        Parst Fixed Cast String zu Python-Objekt.
        
        Args:
            fixed_cast_string: Der Fixed Cast String aus der Datenbank
            
        Returns:
            Geparste Datenstruktur
            
        Raises:
            ValueError: Wenn der String nicht geparst werden kann
        """
        try:
            # String wird zu Python-Objekt umgewandelt (wie in der Original-Funktion)
            processed_string = (fixed_cast_string
                              .replace('and', ',"and",')
                              .replace('or', ',"or",')
                              .replace('in team', '')
                              .replace('UUID', ''))
            
            return literal_eval(processed_string)
            
        except Exception as e:
            raise ValueError(f"Failed to parse fixed cast string: {fixed_cast_string}") from e
    
    def _create_fixed_cast_validation(self, fixed_cast_list, cast_group) -> IntVar:
        """
        Erstellt Validation-Logic für Fixed Cast.
        
        Args:
            fixed_cast_list: Geparste Fixed Cast Datenstruktur
            cast_group: Cast Group Objekt
            
        Returns:
            BoolVar die anzeigt ob Fixed Cast erfüllt ist
        """
        return self._validate_fixed_cast_recursive(fixed_cast_list, cast_group)
    
    def _validate_fixed_cast_recursive(self, fixed_cast_list, cast_group) -> IntVar:
        """
        Rekursive Validation von Fixed Cast Listen.
        
        Args:
            fixed_cast_list: Liste oder String mit Fixed Cast Definition
            cast_group: Cast Group Objekt
            
        Returns:
            BoolVar die das Ergebnis der Validation repräsentiert
        """
        if isinstance(fixed_cast_list, str):
            # Base Case: Single Person UUID
            return self._check_person_in_shift_vars(UUID(fixed_cast_list), cast_group)
        
        # Recursive Case: Liste mit Operatoren
        person_ids = [v for i, v in enumerate(fixed_cast_list) if not i % 2]
        operators = [v for i, v in enumerate(fixed_cast_list) if i % 2]
        
        if not operators:
            # Keine Operatoren -> nur eine Person
            if len(person_ids) == 1:
                return self._validate_fixed_cast_recursive(person_ids[0], cast_group)
            else:
                raise ValueError("Multiple person IDs without operators")
        
        # Alle Operatoren müssen gleich sein
        if any(op != operators[0] for op in operators):
            raise ValueError("All operators must be the same!")
        
        operator = operators[0]
        
        # Erstelle Variablen für alle Personen
        person_vars = [
            self._validate_fixed_cast_recursive(person_id, cast_group) 
            for person_id in person_ids
        ]
        
        if operator == 'and':
            return self._create_and_variable(person_vars)
        elif operator == 'or':
            return self._create_or_variable(person_vars)
        else:
            raise ValueError(f"Unknown operator: {operator}")
    
    def _check_person_in_shift_vars(self, person_id: UUID, cast_group) -> IntVar:
        """
        Prüft ob eine Person in den Shift-Variablen für eine Cast Group vorkommt.
        
        Args:
            person_id: UUID der Person
            cast_group: Cast Group Objekt
            
        Returns:
            BoolVar die anzeigt ob die Person zugewiesen ist
        """
        person_var = self.model.NewBoolVar(f'person_{person_id}_in_cast')
        
        # Summe aller Shift-Variablen für diese Person in dieser Cast Group
        person_shifts = sum(
            shift_var for (adg_id, eg_id), shift_var in self.entities.shift_vars.items()
            if (eg_id == cast_group.event.event_group.id and
                self.entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.person.id == person_id)
        )
        
        self.model.Add(person_var == person_shifts)
        return person_var
    
    def _create_and_variable(self, variables: List[IntVar]) -> IntVar:
        """
        Erstellt AND-Variable für Liste von BoolVars.
        
        Args:
            variables: Liste von BoolVars
            
        Returns:
            BoolVar die das AND-Ergebnis repräsentiert
        """
        and_var = self.model.NewBoolVar('and_combination')
        self.model.AddMultiplicationEquality(and_var, variables)
        return and_var
    
    def _create_or_variable(self, variables: List[IntVar]) -> IntVar:
        """
        Erstellt OR-Variable für Liste von BoolVars.
        
        Args:
            variables: Liste von BoolVars
            
        Returns:
            BoolVar die das OR-Ergebnis repräsentiert
        """
        or_var = self.model.NewBoolVar('or_combination')
        self.model.Add(or_var == sum(variables))
        return or_var
    
    def validate_context(self) -> bool:
        """
        Validiert, ob der Kontext für diesen Constraint geeignet ist.
        
        Returns:
            True wenn alle notwendigen Datenstrukturen verfügbar sind
        """
        if not super().validate_context():
            return False
        
        # Prüfe notwendige Datenstrukturen
        required_attrs = [
            'cast_groups_with_event',
            'avail_day_groups_with_avail_day',
            'shift_vars',
            'event_group_vars'
        ]
        
        for attr in required_attrs:
            if not hasattr(self.entities, attr):
                self.add_metadata('validation_error', f"Missing entities.{attr}")
                return False
        
        # Prüfe ob Cast Groups existieren
        if not self.entities.cast_groups_with_event:
            self.add_metadata('validation_error', "No cast groups with events found")
            return False
        
        return True
    
    def get_fixed_cast_summary(self) -> dict:
        """
        Gibt eine Zusammenfassung der Fixed Cast Daten zurück.
        
        Returns:
            Dictionary mit Fixed Cast Statistiken
        """
        if not self.entities.cast_groups_with_event:
            return {}
        
        total_cast_groups = len(self.entities.cast_groups_with_event)
        cast_groups_with_fixed_cast = 0
        fixed_cast_errors = 0
        
        # Analysiere Cast Groups
        for cast_group in self.entities.cast_groups_with_event.values():
            if cast_group.fixed_cast:
                cast_groups_with_fixed_cast += 1
                
                # Prüfe auf Parsing-Fehler
                try:
                    self._parse_fixed_cast_string(cast_group.fixed_cast)
                except Exception:
                    fixed_cast_errors += 1
        
        # Zähle Metadata-Einträge für Fehler
        error_count_from_metadata = len([
            key for key in self.get_all_metadata().keys() 
            if key.startswith('fixed_cast_error_')
        ])
        
        return {
            'total_cast_groups': total_cast_groups,
            'cast_groups_with_fixed_cast': cast_groups_with_fixed_cast,
            'fixed_cast_parsing_errors': max(fixed_cast_errors, error_count_from_metadata),
            'fixed_cast_conflict_variables': self.get_metadata('total_fixed_cast_conflicts', 0),
            'fixed_cast_coverage': (
                cast_groups_with_fixed_cast / total_cast_groups 
                if total_cast_groups > 0 else 0.0
            )
        }
    
    def get_fixed_cast_details(self) -> List[dict]:
        """
        Gibt detaillierte Informationen über Fixed Casts zurück.
        
        Returns:
            Liste mit Details zu jedem Fixed Cast
        """
        details = []
        
        for cast_group in self.entities.cast_groups_with_event.values():
            if not cast_group.fixed_cast:
                continue
                
            try:
                parsed_cast = self._parse_fixed_cast_string(cast_group.fixed_cast)
                clear_text = generate_fixed_cast_clear_text(cast_group.fixed_cast)
                parsing_success = True
                error_message = None
            except Exception as e:
                parsed_cast = None
                clear_text = "Parsing Error"
                parsing_success = False
                error_message = str(e)
            
            details.append({
                'event_date': cast_group.event.date.strftime('%Y-%m-%d'),
                'event_time': cast_group.event.time_of_day.name,
                'location': cast_group.event.location_plan_period.location_of_work.name,
                'fixed_cast_string': cast_group.fixed_cast,
                'fixed_cast_clear_text': clear_text,
                'parsing_success': parsing_success,
                'error_message': error_message,
                'cast_group_id': str(cast_group.cast_group_id)
            })
        
        return details
    
    def get_summary(self) -> dict:
        """
        Erweiterte Zusammenfassung mit Fixed Cast Daten.
        
        Returns:
            Dictionary mit Constraint- und Fixed Cast Daten
        """
        base_summary = super().get_summary()
        base_summary.update(self.get_fixed_cast_summary())
        return base_summary
