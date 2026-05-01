"""Service-Funktionen für Team.

Ein Team gehört zu einem Projekt, hat einen optionalen Dispatcher (Person) und
verwaltet seine eigenen Standortkombinationen und Excel-Exporteinstellungen.
Soft-Delete via `prep_delete`. Abfragen liefern Teams eines Projekts entweder
vollständig oder als kompakte (Name, ID)-Liste für Dropdown-Menüs.

Read-Funktionen filtern soft-deleted Records standardmäßig aus
(`include_deleted=False`). Über die zugehörigen `with_loader_criteria`-Optionen
werden auch durchnavigierte Relationship-Pfade (`Team.plan_periods` etc.)
automatisch von soft-deleted Einträgen befreit. Restore- und Audit-Pfade
können `include_deleted=True` setzen, um wirklich alle Zeilen zu sehen.
"""
import logging
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import team_show_options
from ._soft_delete import active_team_pp_criteria
from .combination_locations_possible import is_comb_loc_orphaned

logger = logging.getLogger(__name__)


def get(team_id: UUID, *, include_deleted: bool = False) -> schemas.TeamShow:
    with get_session() as session:
        stmt = (select(models.Team)
                .where(models.Team.id == team_id)
                .options(*team_show_options()))
        if not include_deleted:
            stmt = stmt.options(*active_team_pp_criteria())
        team = session.exec(stmt).unique().one()
        return schemas.TeamShow.model_validate(team)


def exists_any_from__project(project_id: UUID, *, include_deleted: bool = False) -> bool:
    """Gibt True zurück, wenn das Projekt mindestens ein Team hat (kein model_validate)."""
    with get_session() as session:
        stmt = select(models.Team).where(models.Team.project_id == project_id).limit(1)
        if not include_deleted:
            stmt = stmt.where(models.Team.prep_delete.is_(None))
        return session.exec(stmt).first() is not None


def get_all_from__project(project_id: UUID, minimal: bool = False, *,
                          include_deleted: bool = False) -> list[schemas.TeamShow | tuple[str, UUID]]:
    with get_session() as session:
        if minimal:
            stmt = select(models.Team).where(models.Team.project_id == project_id)
            if not include_deleted:
                stmt = stmt.where(models.Team.prep_delete.is_(None))
            teams = session.exec(stmt).all()
            return [(t.name, t.id) for t in teams]
        stmt = (select(models.Team)
                .where(models.Team.project_id == project_id)
                .options(*team_show_options()))
        if not include_deleted:
            stmt = stmt.options(*active_team_pp_criteria())
        teams = session.exec(stmt).unique().all()
        return [schemas.TeamShow.model_validate(t) for t in teams]


def create(team_name: str, project_id: UUID, dispatcher_id: UUID = None):
    log_function_info()
    with get_session() as session:
        project_db = session.get(models.Project, project_id)
        dispatcher_db = session.get(models.Person, dispatcher_id) if dispatcher_id else None
        team_db = models.Team(name=team_name, project=project_db, dispatcher=dispatcher_db)
        session.add(team_db)
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def update(team: schemas.Team) -> schemas.TeamShow:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team.id)
        team_db.name = team.name
        team_db.dispatcher = session.get(models.Person, team.dispatcher.id) if team.dispatcher else None
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def update_notes(team_id: UUID, notes: str) -> schemas.TeamShow:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        team_db.notes = notes
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def put_in_comb_loc_possible(team_id: UUID, comb_loc_possible_id: UUID) -> schemas.TeamShow:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        team_db.combination_locations_possibles.append(
            session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def put_in_excel_settings(team_id: UUID, excel_settings_id: UUID) -> schemas.TeamShow:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        team_db.excel_export_settings = session.get(models.ExcelExportSettings, excel_settings_id)
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def remove_comb_loc_possible(team_id: UUID, comb_loc_possible_id: UUID) -> schemas.TeamShow:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        team_db.combination_locations_possibles.remove(
            session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def replace_comb_loc_possibles(
        team_id: UUID,
        original_ids: set[UUID],
        pending_creates: list[tuple[UUID, schemas.CombinationLocationsPossibleCreate]],
        current_combs: list[schemas.CombinationLocationsPossible],
) -> dict[str, list[UUID]]:
    """Ersetzt alle CombLocPossibles eines Teams in einer einzigen Session.

    Neue CLPs werden aus pending_creates angelegt. Verwaiste CLPs werden soft-deleted.
    Returns: {'old_comb_ids': [...], 'new_comb_ids': [...]}
    """
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        old_ids = {c.id for c in team_db.combination_locations_possibles}

        # Neue CLPs anlegen und Temp-IDs auflösen
        temp_to_real: dict[UUID, UUID] = {}
        for temp_id, create_schema in pending_creates:
            new_clp = models.CombinationLocationsPossible(
                project=session.get(models.Project, create_schema.project.id),
                time_span_between=create_schema.time_span_between)
            session.add(new_clp)
            session.flush()
            for loc in create_schema.locations_of_work:
                new_clp.locations_of_work.append(session.get(models.LocationOfWork, loc.id))
            session.flush()
            temp_to_real[temp_id] = new_clp.id

        # Finale echte IDs bestimmen und Assoziationen ersetzen
        final_ids = {temp_to_real.get(c.id, c.id) for c in current_combs}
        team_db.combination_locations_possibles = [
            session.get(models.CombinationLocationsPossible, clp_id) for clp_id in final_ids]
        session.flush()

        # Verwaiste CLPs soft-deleten (CLPs mit team_id werden durch is_comb_loc_orphaned nie gelöscht)
        now = _utcnow()
        for removed_id in old_ids - final_ids:
            clp = session.get(models.CombinationLocationsPossible, removed_id)
            if clp and not clp.prep_delete and is_comb_loc_orphaned(session, removed_id):
                clp.prep_delete = now
        session.flush()

        return {'old_comb_ids': list(old_ids), 'new_comb_ids': list(final_ids)}


def restore_comb_loc_possibles(
        team_id: UUID,
        comb_ids_to_restore: list[UUID],
) -> None:
    """Undo/Redo-Gegenstück zu replace_comb_loc_possibles für Team."""
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        current_ids = {c.id for c in team_db.combination_locations_possibles}
        ids_to_restore = set(comb_ids_to_restore)

        for clp_id in ids_to_restore:
            clp = session.get(models.CombinationLocationsPossible, clp_id)
            if clp and clp.prep_delete:
                clp.prep_delete = None

        team_db.combination_locations_possibles = [
            session.get(models.CombinationLocationsPossible, clp_id)
            for clp_id in ids_to_restore]
        session.flush()

        now = _utcnow()
        for removed_id in current_ids - ids_to_restore:
            clp = session.get(models.CombinationLocationsPossible, removed_id)
            if clp and not clp.prep_delete and is_comb_loc_orphaned(session, removed_id):
                clp.prep_delete = now
        session.flush()


def delete(team_id: UUID) -> schemas.TeamDeletionResult:
    """Soft-Delete des Teams mit Kaskade auf alle aktiven PlanPeriods.

    Cascade-Verhalten:
      - Alle PlanPeriods mit `prep_delete IS NULL` werden mit dem gleichen
        Timestamp soft-deleted.
      - Geschlossene PlanPeriods (`closed=True`) werden bewusst mit-soft-deleted —
        die übliche `PlanPeriodClosedError`-Invariante wird umgangen, weil ein
        gelöschtes Team die "aktiv archiviert"-Semantik der geschlossenen PP
        ohnehin obsolet macht. Pro überschriebene Closed-PP wird eine
        `logger.info`-Zeile geschrieben.

    Rückgabe enthält die IDs der mit-cascade-deleteten PlanPeriods, damit der
    Undo-Pfad sie gezielt restoren kann (kein Timestamp-Heuristik-Match).
    """
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        now = _utcnow()
        team_db.prep_delete = now

        cascaded_pp_ids: list[UUID] = []
        for pp in team_db.plan_periods:
            if pp.prep_delete is not None:
                continue
            if pp.closed:
                logger.info(
                    "team.delete cascade: bypass closed-invariant for "
                    "PlanPeriod %s (team %s) — soft-delete erzwungen, da Team gelöscht.",
                    pp.id, team_db.id,
                )
            pp.prep_delete = now
            cascaded_pp_ids.append(pp.id)

        session.flush()
        return schemas.TeamDeletionResult(
            team=schemas.Team.model_validate(team_db),
            cascaded_plan_period_ids=cascaded_pp_ids,
        )


def undelete(team_id: UUID, cascaded_plan_period_ids: list[UUID] | None = None) -> schemas.Team:
    """Hebt das Soft-Delete einer Team-Zeile auf (Undo-Pfad).

    Mit `cascaded_plan_period_ids` werden die im selben Soft-Delete-Schritt
    mit-cascade-deleteten PlanPeriods explizit zurückgesetzt — typischerweise
    übergeben aus dem Ergebnis eines vorigen `delete()`-Aufrufs. PPs, die
    schon vor dem Team-Soft-Delete gelöscht waren, bleiben unverändert.
    """
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        team_db.prep_delete = None

        if cascaded_plan_period_ids:
            for pp_id in cascaded_plan_period_ids:
                pp = session.get(models.PlanPeriod, pp_id)
                if pp is not None and pp.prep_delete is not None:
                    pp.prep_delete = None

        session.flush()
        return schemas.Team.model_validate(team_db)