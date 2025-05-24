"""
Utility functions for employment statistics
"""

import datetime
from typing import List, Dict, Any
from collections import defaultdict

from .service import EmploymentStatistics, EmployeeStatistics, LocationStatistics


def format_statistics_summary(stats: EmploymentStatistics) -> str:
    """
    Erstellt eine formatierte Zusammenfassung der Statistiken
    
    Args:
        stats: Die Employment Statistics
        
    Returns:
        str: Formatierte Zusammenfassung
    """
    context = f"Team: {stats.team_name}" if stats.team_name else f"Projekt: {stats.project_name}"
    
    summary = f"""
Einsatzstatistik - {context}
Zeitraum: {stats.start_date} bis {stats.end_date}

Übersicht:
• Gesamte Einsätze: {stats.total_assignments}
• Mitarbeiter: {stats.total_employees}
• Standorte: {stats.total_locations}
• Ø Einsätze pro Mitarbeiter: {stats.average_assignments_per_employee:.1f}
• Ø Einsätze pro Planperiode: {stats.average_assignments_per_period:.1f}
"""
    return summary.strip()


def get_top_employees(stats: EmploymentStatistics, limit: int = 10) -> List[EmployeeStatistics]:
    """
    Gibt die Top-Mitarbeiter nach Einsätzen zurück
    
    Args:
        stats: Die Employment Statistics
        limit: Maximale Anzahl zurückzugebender Mitarbeiter
        
    Returns:
        List[EmployeeStatistics]: Top Mitarbeiter
    """
    return stats.employee_statistics[:limit]


def get_top_locations(stats: EmploymentStatistics, limit: int = 10) -> List[LocationStatistics]:
    """
    Gibt die Top-Standorte nach Einsätzen zurück
    
    Args:
        stats: Die Employment Statistics
        limit: Maximale Anzahl zurückzugebender Standorte
        
    Returns:
        List[LocationStatistics]: Top Standorte
    """
    return stats.location_statistics[:limit]


def calculate_distribution_percentages(values: List[int]) -> List[float]:
    """
    Berechnet Prozent-Verteilung für eine Liste von Werten
    
    Args:
        values: Liste von Zahlenwerten
        
    Returns:
        List[float]: Prozent-Werte
    """
    total = sum(values)
    if total == 0:
        return [0.0] * len(values)
    
    return [round((value / total) * 100, 1) for value in values]


def group_employees_by_assignment_range(
    employee_stats: List[EmployeeStatistics]
) -> Dict[str, List[EmployeeStatistics]]:
    """
    Gruppiert Mitarbeiter nach Einsatz-Bereichen
    
    Args:
        employee_stats: Liste der Mitarbeiter-Statistiken
        
    Returns:
        Dict[str, List[EmployeeStatistics]]: Gruppierte Mitarbeiter
    """
    groups = defaultdict(list)
    
    for employee in employee_stats:
        assignments = employee.total_assignments
        
        if assignments == 0:
            group_key = "Keine Einsätze"
        elif assignments <= 5:
            group_key = "1-5 Einsätze"
        elif assignments <= 10:
            group_key = "6-10 Einsätze"
        elif assignments <= 20:
            group_key = "11-20 Einsätze"
        elif assignments <= 50:
            group_key = "21-50 Einsätze"
        else:
            group_key = "Mehr als 50 Einsätze"
            
        groups[group_key].append(employee)
    
    return dict(groups)


def calculate_workload_balance(employee_stats: List[EmployeeStatistics]) -> Dict[str, Any]:
    """
    Berechnet Workload-Balance Metriken
    
    Args:
        employee_stats: Liste der Mitarbeiter-Statistiken
        
    Returns:
        Dict[str, Any]: Balance-Metriken
    """
    if not employee_stats:
        return {
            'min_assignments': 0,
            'max_assignments': 0,
            'median_assignments': 0,
            'std_deviation': 0,
            'balance_score': 0  # 0-100, 100 = perfekt ausgewogen
        }
    
    assignments = [emp.total_assignments for emp in employee_stats]
    assignments.sort()
    
    min_val = min(assignments)
    max_val = max(assignments)
    median_val = assignments[len(assignments) // 2]
    
    # Einfache Standardabweichung
    mean_val = sum(assignments) / len(assignments)
    variance = sum((x - mean_val) ** 2 for x in assignments) / len(assignments)
    std_dev = variance ** 0.5
    
    # Balance Score: Je geringer die Standardabweichung im Verhältnis zum Mittelwert,
    # desto besser die Balance
    if mean_val > 0:
        coefficient_of_variation = std_dev / mean_val
        balance_score = max(0, 100 - (coefficient_of_variation * 100))
    else:
        balance_score = 100 if std_dev == 0 else 0
    
    return {
        'min_assignments': min_val,
        'max_assignments': max_val,
        'median_assignments': median_val,
        'std_deviation': round(std_dev, 2),
        'balance_score': round(balance_score, 1)
    }


def format_date_range(start_date: datetime.date, end_date: datetime.date) -> str:
    """
    Formatiert einen Datumsbereich für die Anzeige
    
    Args:
        start_date: Startdatum
        end_date: Enddatum
        
    Returns:
        str: Formatierter Datumsbereich
    """
    if start_date == end_date:
        return start_date.strftime("%d.%m.%Y")
    
    # Gleicher Monat
    if start_date.year == end_date.year and start_date.month == end_date.month:
        return f"{start_date.day}.-{end_date.strftime('%d.%m.%Y')}"
    
    # Gleiches Jahr
    if start_date.year == end_date.year:
        return f"{start_date.strftime('%d.%m.')}-{end_date.strftime('%d.%m.%Y')}"
    
    # Verschiedene Jahre
    return f"{start_date.strftime('%d.%m.%Y')}-{end_date.strftime('%d.%m.%Y')}"


def export_statistics_to_dict(stats: EmploymentStatistics) -> Dict[str, Any]:
    """
    Konvertiert Statistiken in ein Dictionary für Export/JSON
    
    Args:
        stats: Die Employment Statistics
        
    Returns:
        Dict[str, Any]: Dictionary-Repräsentation
    """
    return {
        'summary': {
            'team_name': stats.team_name,
            'project_name': stats.project_name,
            'start_date': stats.start_date.isoformat(),
            'end_date': stats.end_date.isoformat(),
            'total_assignments': stats.total_assignments,
            'total_employees': stats.total_employees,
            'total_locations': stats.total_locations,
            'average_assignments_per_employee': stats.average_assignments_per_employee,
            'average_assignments_per_period': stats.average_assignments_per_period
        },
        'employees': [
            {
                'name': emp.person_name,
                'total_assignments': emp.total_assignments,
                'assignments_by_location': emp.assignments_by_location,
                'assignments_by_period': emp.assignments_by_period
            }
            for emp in stats.employee_statistics
        ],
        'locations': [
            {
                'name': loc.location_name,
                'total_assignments': loc.total_assignments,
                'employees_count': loc.employees_count,
                'average_assignments_per_employee': loc.average_assignments_per_employee
            }
            for loc in stats.location_statistics
        ],
        'periods': [
            {
                'name': period.period_name,
                'start_date': period.period_start.isoformat(),
                'end_date': period.period_end.isoformat(),
                'total_assignments': period.total_assignments,
                'employees_count': period.employees_count,
                'locations_count': period.locations_count
            }
            for period in stats.period_statistics
        ]
    }
