"""Soft-Delete-Filter für Team- und PlanPeriod-Read-Pfade.

Stellt zentrale `with_loader_criteria`-Optionen bereit, die in den Read-Service-Funktionen
als Top-Level-Query-Option mitgegeben werden. Mit `include_aliases=True` propagieren sie
über alle Joins und Relationship-Loadings (joinedload/selectinload) hinweg — dadurch
werden auch durchnavigierte Pfade wie `Project.teams[].plan_periods[]` automatisch gefiltert.

Das ersetzt die bisher überall in der GUI verstreuten List-Comprehensions
`[t for t in ... if not t.prep_delete]` und schließt die Lücke in den Web-API-Pfaden,
die heute nur PlanPeriod, aber nicht Team filtern.

Verwendung::

    from ._soft_delete import active_team_pp_criteria

    options = [*team_show_options(), *active_team_pp_criteria()] if not include_deleted \
              else team_show_options()
    stmt = select(models.Team).where(...).options(*options)
"""
from sqlalchemy.orm import with_loader_criteria

from .. import models


def active_team_pp_criteria() -> list:
    """Zwei Loader-Criteria, die soft-deleted Team- und PlanPeriod-Records verbergen.

    `include_aliases=True` ist Pflicht, damit auch Joins mit Aliases (typisch in
    eager-loading-Plänen) gefiltert werden. `propagate_to_loaders=True` (Default)
    wirkt auch auf Relationship-Loads — also `Team.plan_periods`, `Project.teams`,
    `Person.teams_of_dispatcher` etc.
    """
    return [
        with_loader_criteria(
            models.Team,
            lambda cls: cls.prep_delete.is_(None),
            include_aliases=True,
        ),
        with_loader_criteria(
            models.PlanPeriod,
            lambda cls: cls.prep_delete.is_(None),
            include_aliases=True,
        ),
    ]


def active_team_criteria() -> list:
    """Nur den Team-Filter — für Read-Funktionen, die kein PlanPeriod im Tree haben."""
    return [
        with_loader_criteria(
            models.Team,
            lambda cls: cls.prep_delete.is_(None),
            include_aliases=True,
        ),
    ]


def active_pp_criteria() -> list:
    """Nur den PlanPeriod-Filter."""
    return [
        with_loader_criteria(
            models.PlanPeriod,
            lambda cls: cls.prep_delete.is_(None),
            include_aliases=True,
        ),
    ]