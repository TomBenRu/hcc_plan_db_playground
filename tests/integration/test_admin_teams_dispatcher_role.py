"""Integration-Tests fuer /admin/teams Dispatcher-Plan-Konfig (Phase 1.2).

Pruefen:
- Dispatcher kann nr_actors / fixed_cast / notes aendern (200, DB-Update)
- Admin darf Plan-Konfig ebenfalls aendern (Doppel-Rolle)
- Standard-Konto ohne Dispatcher-Rolle wird abgewiesen (403)
- notification_circle_restricted-Feld wird vom Endpoint ignoriert
- fixed_cast_only_if_available als Checkbox (Wert "on" oder fehlend)
"""

from __future__ import annotations

from sqlmodel import Session

from database.models import LocationOfWork, Project


def test_dispatcher_can_change_nr_actors(
    as_dispatcher, session: Session, project: Project, link_location_to_dispatcher
) -> None:
    loc = LocationOfWork(name="Loc-PC1", project=project, nr_actors=2)
    session.add(loc)
    session.commit()
    session.refresh(loc)
    link_location_to_dispatcher(loc)

    resp = as_dispatcher.patch(
        f"/admin/teams/locations/{loc.id}/plan-konfig",
        data={"nr_actors": 5, "fixed_cast": "", "notes": ""},
    )
    assert resp.status_code == 200, resp.text
    session.expire_all()
    fresh = session.get(LocationOfWork, loc.id)
    assert fresh.nr_actors == 5


def test_dispatcher_can_set_fixed_cast_and_flag(
    as_dispatcher, session: Session, project: Project, link_location_to_dispatcher
) -> None:
    loc = LocationOfWork(name="Loc-PC2", project=project)
    session.add(loc)
    session.commit()
    session.refresh(loc)
    link_location_to_dispatcher(loc)

    resp = as_dispatcher.patch(
        f"/admin/teams/locations/{loc.id}/plan-konfig",
        data={
            "nr_actors": 3,
            "fixed_cast": "A;B",
            "fixed_cast_only_if_available": "on",
            "notes": "Test-Notes",
        },
    )
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(LocationOfWork, loc.id)
    assert fresh.fixed_cast == "A;B"
    assert fresh.fixed_cast_only_if_available is True
    assert fresh.notes == "Test-Notes"


def test_fixed_cast_only_if_available_unset_when_checkbox_absent(
    as_dispatcher, session: Session, project: Project, link_location_to_dispatcher
) -> None:
    """Checkbox-Konvention: Feld fehlt im Submit → False."""
    loc = LocationOfWork(
        name="Loc-PC3",
        project=project,
        fixed_cast_only_if_available=True,
    )
    session.add(loc)
    session.commit()
    session.refresh(loc)
    link_location_to_dispatcher(loc)

    resp = as_dispatcher.patch(
        f"/admin/teams/locations/{loc.id}/plan-konfig",
        data={"nr_actors": 2, "fixed_cast": "", "notes": ""},
    )
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(LocationOfWork, loc.id)
    assert fresh.fixed_cast_only_if_available is False


def test_admin_can_also_change_plan_config(
    as_admin, session: Session, project: Project
) -> None:
    """Admin hat Doppel-Recht — Stammdaten + Plan-Konfig."""
    loc = LocationOfWork(name="Loc-PC4", project=project)
    session.add(loc)
    session.commit()
    session.refresh(loc)

    resp = as_admin.patch(
        f"/admin/teams/locations/{loc.id}/plan-konfig",
        data={"nr_actors": 7, "fixed_cast": "", "notes": ""},
    )
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(LocationOfWork, loc.id)
    assert fresh.nr_actors == 7


def test_notification_circle_restricted_is_ignored(
    as_dispatcher, session: Session, project: Project, link_location_to_dispatcher
) -> None:
    """Defensiver Filter: notification_circle_restricted darf vom Endpoint
    NICHT gesetzt werden — Form-Body-Wert wird stillschweigend ignoriert."""
    loc = LocationOfWork(
        name="Loc-PC5",
        project=project,
        notification_circle_restricted=False,
    )
    session.add(loc)
    session.commit()
    session.refresh(loc)
    link_location_to_dispatcher(loc)

    resp = as_dispatcher.patch(
        f"/admin/teams/locations/{loc.id}/plan-konfig",
        data={
            "nr_actors": 2,
            "fixed_cast": "",
            "notes": "",
            "notification_circle_restricted": "on",
        },
    )
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(LocationOfWork, loc.id)
    assert fresh.notification_circle_restricted is False, (
        "notification_circle_restricted darf nicht aus diesem Endpoint geaendert werden"
    )


def test_nr_actors_validation_rejects_out_of_range(
    as_dispatcher, session: Session, project: Project
) -> None:
    loc = LocationOfWork(name="Loc-PC6", project=project)
    session.add(loc)
    session.commit()
    session.refresh(loc)

    resp = as_dispatcher.patch(
        f"/admin/teams/locations/{loc.id}/plan-konfig",
        data={"nr_actors": 500, "fixed_cast": "", "notes": ""},
    )
    # FastAPI ``Form(..., ge=0, le=255)`` liefert 422 bei Out-of-Range
    assert resp.status_code == 422
