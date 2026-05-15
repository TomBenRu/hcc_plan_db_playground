"""Integration-Tests fuer /admin/teams Soft-/Hard-Delete (Phase 1.5).

Pruefen:
- Team ohne aktive PP soft-deleten + restore
- Soft-Delete blockiert bei aktiver PlanPeriod (409)
- Hard-Delete erfordert Name-Confirm
- Hard-Delete blockiert sobald JEDE PP existiert (auch historische)
- TAA/TLA-Cleanup: offene Eintraege werden end=today, Future-Eintraege geloescht
- Standort-Pendants analog
- Dispatcher darf NICHT loeschen (403)
"""

from __future__ import annotations

import datetime
from datetime import date, timedelta

from sqlmodel import Session, select

from database.models import (
    LocationOfWork,
    LocationPlanPeriod,
    Person,
    PlanPeriod,
    Project,
    Team,
    TeamActorAssign,
    TeamLocationAssign,
)


def test_soft_delete_team_without_plan_periods(
    as_admin, session: Session, project: Project
) -> None:
    team = Team(name="SoftDel-1", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)

    resp = as_admin.post(f"/admin/teams/teams/{team.id}/soft-delete")
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(Team, team.id)
    assert fresh.prep_delete is not None


def test_soft_delete_team_blocked_by_active_plan_period(
    as_admin, session: Session, project: Project
) -> None:
    team = Team(name="SoftDel-2", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)
    pp = PlanPeriod(
        team=team,
        start=date.today(),
        end=date.today() + timedelta(days=14),
    )
    session.add(pp)
    session.commit()

    resp = as_admin.post(f"/admin/teams/teams/{team.id}/soft-delete")
    assert resp.status_code == 200  # Drawer mit Error gerendert
    assert "kann nicht entfernt werden" in resp.text
    session.expire_all()
    fresh = session.get(Team, team.id)
    assert fresh.prep_delete is None, "Team darf NICHT soft-deleted sein"


def test_restore_team(as_admin, session: Session, project: Project) -> None:
    team = Team(
        name="Restoreable",
        project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(team)
    session.commit()
    session.refresh(team)

    resp = as_admin.post(f"/admin/teams/teams/{team.id}/restore")
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(Team, team.id)
    assert fresh.prep_delete is None


def test_hard_delete_team_requires_correct_name(
    as_admin, session: Session, project: Project
) -> None:
    team = Team(
        name="HardDel-1",
        project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(team)
    session.commit()
    session.refresh(team)
    team_id = team.id

    resp = as_admin.request(
        "DELETE",
        f"/admin/teams/teams/{team_id}",
        data={"name_confirmation": "FalscherName"},
    )
    assert resp.status_code == 422
    session.expire_all()
    assert session.get(Team, team_id) is not None, "Team darf NICHT geloescht sein"

    resp = as_admin.request(
        "DELETE",
        f"/admin/teams/teams/{team_id}",
        data={"name_confirmation": "HardDel-1"},
    )
    assert resp.status_code == 200
    session.expire_all()
    assert session.get(Team, team_id) is None


def test_hard_delete_team_blocked_by_any_plan_period(
    as_admin, session: Session, project: Project
) -> None:
    """Selbst eine historische, soft-deletete PlanPeriod blockiert Hard-Delete —
    Schutz vor Cascade-Verlust."""
    team = Team(
        name="ProtectedTeam",
        project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(team)
    session.commit()
    pp = PlanPeriod(
        team=team,
        start=date.today() - timedelta(days=180),
        end=date.today() - timedelta(days=150),
        prep_delete=datetime.datetime.now(datetime.timezone.utc),  # historisch
    )
    session.add(pp)
    session.commit()
    session.refresh(team)
    team_id = team.id

    resp = as_admin.request(
        "DELETE",
        f"/admin/teams/teams/{team_id}",
        data={"name_confirmation": "ProtectedTeam"},
    )
    assert resp.status_code == 422
    assert "Endgültiges Löschen nicht möglich" in resp.text
    session.expire_all()
    assert session.get(Team, team_id) is not None, "Team mit PP-Historie darf NICHT weg"


def test_soft_delete_cleans_open_assigns(
    as_admin, session: Session, project: Project
) -> None:
    """Beim Team-Soft-Delete:
    - Offene TAA mit start<=heute → end=heute
    - Future-Start-TAA → DELETE
    """
    team = Team(name="CleanupTest", project=project)
    session.add(team)
    session.commit()
    person_a = Person(
        f_name="Active", l_name="Mit", email="a@test.local", username="a", password="x",
        project=project,
    )
    person_b = Person(
        f_name="Future", l_name="Mit", email="b@test.local", username="b", password="x",
        project=project,
    )
    session.add_all([person_a, person_b])
    session.commit()

    today = date.today()
    open_taa = TeamActorAssign(person=person_a, team=team, start=today - timedelta(days=10))
    future_taa = TeamActorAssign(person=person_b, team=team, start=today + timedelta(days=30))
    session.add_all([open_taa, future_taa])
    session.commit()
    session.refresh(open_taa)
    session.refresh(future_taa)
    open_id = open_taa.id
    future_id = future_taa.id

    resp = as_admin.post(f"/admin/teams/teams/{team.id}/soft-delete")
    assert resp.status_code == 200

    session.expire_all()
    open_after = session.get(TeamActorAssign, open_id)
    assert open_after is not None
    assert open_after.end == today, "Offene Mitgliedschaft sollte end=today bekommen"

    future_after = session.get(TeamActorAssign, future_id)
    assert future_after is None, "Future-Mitgliedschaft sollte geloescht sein"


def test_soft_delete_location_blocked_by_lpp(
    as_admin, session: Session, project: Project
) -> None:
    team = Team(name="TeamForLPP", project=project)
    loc = LocationOfWork(name="ProtectedLoc", project=project)
    session.add_all([team, loc])
    session.commit()
    pp = PlanPeriod(team=team, start=date.today(), end=date.today() + timedelta(days=7))
    session.add(pp)
    session.commit()
    lpp = LocationPlanPeriod(plan_period=pp, location_of_work=loc)
    session.add(lpp)
    session.commit()
    session.refresh(loc)

    resp = as_admin.post(f"/admin/teams/locations/{loc.id}/soft-delete")
    assert "kann nicht entfernt werden" in resp.text
    session.expire_all()
    fresh = session.get(LocationOfWork, loc.id)
    assert fresh.prep_delete is None


def test_soft_delete_location_without_lpp(
    as_admin, session: Session, project: Project
) -> None:
    loc = LocationOfWork(name="DelLoc-1", project=project)
    session.add(loc)
    session.commit()
    session.refresh(loc)

    resp = as_admin.post(f"/admin/teams/locations/{loc.id}/soft-delete")
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(LocationOfWork, loc.id)
    assert fresh.prep_delete is not None


def test_dispatcher_cannot_soft_delete(
    as_dispatcher, session: Session, project: Project
) -> None:
    team = Team(name="Lock", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)
    resp = as_dispatcher.post(f"/admin/teams/teams/{team.id}/soft-delete")
    assert resp.status_code == 403


def test_admin_drawer_shows_soft_delete_button_for_active_team(
    as_admin, session: Session, project: Project
) -> None:
    team = Team(name="UIActionsAktiv", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)

    resp = as_admin.get(f"/admin/teams/teams/{team.id}/drawer")
    assert resp.status_code == 200
    assert "In Inaktiv verschieben" in resp.text
    assert "Wiederherstellen" not in resp.text
    assert "Endgültig löschen" not in resp.text


def test_admin_drawer_shows_restore_and_delete_for_inactive_team(
    as_admin, session: Session, project: Project
) -> None:
    team = Team(
        name="UIActionsInaktiv",
        project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(team)
    session.commit()
    session.refresh(team)

    resp = as_admin.get(f"/admin/teams/teams/{team.id}/drawer")
    assert resp.status_code == 200
    assert "Wiederherstellen" in resp.text
    assert "Endgültig löschen" in resp.text
    assert "name_confirmation" in resp.text
    assert "In Inaktiv verschieben" not in resp.text


def test_dispatcher_drawer_blocked(
    as_dispatcher, session: Session, project: Project
) -> None:
    """/admin/teams ist seit 2026-05-15 strikt admin-only — Dispatcher bekommt
    403 auf jeden Drawer-Endpoint."""
    team = Team(name="NoAccessForDisp", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)
    resp = as_dispatcher.get(f"/admin/teams/teams/{team.id}/drawer")
    assert resp.status_code == 403


def test_admin_drawer_shows_location_actions(
    as_admin, session: Session, project: Project
) -> None:
    loc_active = LocationOfWork(name="LocAktiv", project=project)
    loc_inactive = LocationOfWork(
        name="LocInaktiv",
        project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add_all([loc_active, loc_inactive])
    session.commit()
    session.refresh(loc_active)
    session.refresh(loc_inactive)

    resp_active = as_admin.get(f"/admin/teams/locations/{loc_active.id}/drawer")
    assert "In Inaktiv verschieben" in resp_active.text
    assert "Endgültig löschen" not in resp_active.text

    resp_inactive = as_admin.get(f"/admin/teams/locations/{loc_inactive.id}/drawer")
    assert "Wiederherstellen" in resp_inactive.text
    assert "Endgültig löschen" in resp_inactive.text
    assert "name_confirmation" in resp_inactive.text


# ═══════════════════════════════════════════════════════════════════════════════
# Soft-/Hard-Delete für Personen (Phase 1.5b)
# ═══════════════════════════════════════════════════════════════════════════════


def _make_person_with_taa(
    session: Session, project: Project, team: Team, *, first: str = "Pat"
) -> tuple[Person, TeamActorAssign]:
    """Helper: aktive Person + offene Mitgliedschaft im Team."""
    from database.models import Gender
    import secrets

    person = Person(
        f_name=first,
        l_name="Member",
        gender=Gender.female,
        email=f"{first.lower()}-{secrets.token_hex(3)}@example.com",
        username=f"{first.lower()}-{secrets.token_hex(3)}",
        password="dummy",
        project=project,
    )
    session.add(person)
    session.commit()
    session.refresh(person)
    taa = TeamActorAssign(person=person, team=team, start=date.today())
    session.add(taa)
    session.commit()
    return person, taa


def test_soft_delete_person_happy(
    as_admin, session: Session, project: Project
) -> None:
    """Person ohne aktive APP wird soft-deletet; offene TAA wird auf end=today
    geschlossen."""
    team = Team(name="TeamForSoftDel", project=project)
    session.add(team)
    session.commit()
    person, taa = _make_person_with_taa(session, project, team)

    resp = as_admin.post(f"/admin/teams/persons/{person.id}/soft-delete")
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(Person, person.id)
    assert fresh.prep_delete is not None
    # Offene TAA geschlossen auf heute
    fresh_taa = session.get(TeamActorAssign, taa.id)
    assert fresh_taa.end == date.today()


def test_soft_delete_person_blocked_by_active_actor_plan_period(
    as_admin, session: Session, project: Project
) -> None:
    """Aktive APP blockiert Soft-Delete — Drawer wird mit Error gerendert."""
    from database.models import ActorPlanPeriod

    team = Team(name="TeamWithPP", project=project)
    session.add(team)
    session.commit()
    person, _ = _make_person_with_taa(session, project, team)

    pp = PlanPeriod(
        team=team,
        start=date.today(),
        end=date.today() + timedelta(days=14),
    )
    session.add(pp)
    session.commit()
    app = ActorPlanPeriod(plan_period=pp, person=person)
    session.add(app)
    session.commit()

    resp = as_admin.post(f"/admin/teams/persons/{person.id}/soft-delete")
    assert resp.status_code == 200
    assert "kann nicht entfernt werden" in resp.text
    session.expire_all()
    assert session.get(Person, person.id).prep_delete is None


def test_restore_person(as_admin, session: Session, project: Project) -> None:
    person = Person(
        f_name="ToRestore", l_name="Person",
        gender=__import__("database.models", fromlist=["Gender"]).Gender.female,
        email="restore@example.com", username="restore-x",
        password="dummy", project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(person)
    session.commit()

    resp = as_admin.post(f"/admin/teams/persons/{person.id}/restore")
    assert resp.status_code == 200
    session.expire_all()
    assert session.get(Person, person.id).prep_delete is None


def test_hard_delete_person_requires_full_name(
    as_admin, session: Session, project: Project
) -> None:
    from database.models import Gender

    person = Person(
        f_name="HardDel", l_name="Person",
        gender=Gender.female,
        email="hard@example.com", username="hard-x",
        password="dummy", project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(person)
    session.commit()
    person_id = person.id  # ID festhalten, weil Person nach Hard-Delete weg ist

    # Falscher Name → 200 mit Error im Drawer
    resp_wrong = as_admin.request(
        "DELETE",
        f"/admin/teams/persons/{person_id}",
        data={"name_confirmation": "HardDel"},
    )
    assert resp_wrong.status_code == 200
    assert "stimmt nicht überein" in resp_wrong.text
    session.expire_all()
    assert session.get(Person, person_id) is not None

    # Korrekter Name → 200 mit leerem Body + HX-Trigger
    resp_ok = as_admin.request(
        "DELETE",
        f"/admin/teams/persons/{person_id}",
        data={"name_confirmation": "HardDel Person"},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.headers.get("HX-Trigger") == "members-list-changed"
    session.expire_all()
    assert session.get(Person, person_id) is None


def test_hard_delete_person_blocked_by_any_actor_plan_period(
    as_admin, session: Session, project: Project
) -> None:
    """Auch eine historische APP blockt Hard-Delete (Cascade-Schutz)."""
    from database.models import ActorPlanPeriod, Gender

    team = Team(name="TeamHistAPP", project=project)
    session.add(team)
    session.commit()
    person = Person(
        f_name="Block", l_name="HardDel",
        gender=Gender.female,
        email="block@example.com", username="block-x",
        password="dummy", project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(person)
    session.commit()
    pp = PlanPeriod(team=team, start=date.today(), end=date.today() + timedelta(days=7))
    session.add(pp)
    session.commit()
    app = ActorPlanPeriod(plan_period=pp, person=person)
    session.add(app)
    session.commit()

    resp = as_admin.request(
        "DELETE",
        f"/admin/teams/persons/{person.id}",
        data={"name_confirmation": "Block HardDel"},
    )
    assert resp.status_code == 200
    assert "Endgültiges Löschen nicht möglich" in resp.text
    session.expire_all()
    assert session.get(Person, person.id) is not None


def test_dispatcher_cannot_soft_delete_person(
    as_dispatcher, session: Session, project: Project
) -> None:
    from database.models import Gender

    person = Person(
        f_name="Protected", l_name="Person",
        gender=Gender.female,
        email="prot@example.com", username="prot-x",
        password="dummy", project=project,
    )
    session.add(person)
    session.commit()

    resp = as_dispatcher.post(f"/admin/teams/persons/{person.id}/soft-delete")
    assert resp.status_code == 403


def test_hard_delete_accepts_name_confirmation_from_query_param(
    as_admin, session: Session, project: Project
) -> None:
    """HTMX schickt bei ``hx-delete`` Form-Werte als URL-Query-Parameter, nicht
    im Body. Der Endpoint muss beide Quellen akzeptieren — sonst kommt
    'stimmt nicht ueberein' im Browser, obwohl der Confirm-String stimmt.
    Stellvertretend nur fuer den Person-Pfad — Team/Location nutzen den
    gleichen Helper."""
    from database.models import Gender

    person = Person(
        f_name="Query", l_name="Confirm",
        gender=Gender.female,
        email="q@example.com", username="q-x",
        password="dummy", project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(person)
    session.commit()
    person_id = person.id

    # 1) Korrekter Name als URL-Query-Param (Browser/HTMX-Pfad)
    resp_ok = as_admin.request(
        "DELETE",
        f"/admin/teams/persons/{person_id}",
        params={"name_confirmation": "Query Confirm"},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.headers.get("HX-Trigger") == "members-list-changed"
    session.expire_all()
    assert session.get(Person, person_id) is None


def test_hard_delete_confirm_inputs_use_data_attribute_not_inline_tojson(
    as_admin, session: Session, project: Project
) -> None:
    """Regression: das oninput-Attribut darf keinen rohen ``tojson``-String mit
    ``"`` enthalten — der schloss das HTML-Attribut vorzeitig, und der
    Confirm-Button blieb permanent disabled. Stattdessen wird der Erwartungs-
    Wert ueber ``data-expected`` transportiert und im JS ueber
    ``this.dataset.expected`` gelesen. Gilt fuer alle drei Drawer."""
    from database.models import Gender

    team = Team(
        name="Confirm-Team", project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    loc = LocationOfWork(
        name="Confirm-Loc", project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    person = Person(
        f_name="Confirm", l_name="Person",
        gender=Gender.female,
        email="confirm@example.com", username="confirm-x",
        password="dummy", project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add_all([team, loc, person])
    session.commit()

    for url in (
        f"/admin/teams/teams/{team.id}/drawer",
        f"/admin/teams/locations/{loc.id}/drawer",
        f"/admin/teams/persons/{person.id}/drawer",
    ):
        resp = as_admin.get(url)
        assert resp.status_code == 200
        # Neues Pattern via data-Attribut
        assert "this.dataset.expected" in resp.text, f"{url} fehlt data.expected-Pattern"
        assert 'data-expected="' in resp.text, f"{url} fehlt data-expected-Attribut"
        # Altes Pattern darf nicht mehr drin sein
        assert "!== \"" not in resp.text, f"{url} hat noch rohes tojson-Pattern"


def test_member_drawer_shows_lifecycle_actions(
    as_admin, session: Session, project: Project
) -> None:
    """Drawer rendert die Aktionen-Section abhängig vom prep_delete-Status."""
    from database.models import Gender

    active = Person(
        f_name="DrawerAct", l_name="Person",
        gender=Gender.female,
        email="da@example.com", username="da-x",
        password="dummy", project=project,
    )
    inactive = Person(
        f_name="DrawerInact", l_name="Person",
        gender=Gender.female,
        email="di@example.com", username="di-x",
        password="dummy", project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add_all([active, inactive])
    session.commit()

    resp_active = as_admin.get(f"/admin/teams/persons/{active.id}/drawer")
    assert "In Inaktiv verschieben" in resp_active.text
    assert "Endgültig löschen" not in resp_active.text

    resp_inactive = as_admin.get(f"/admin/teams/persons/{inactive.id}/drawer")
    assert "Wiederherstellen" in resp_inactive.text
    assert "Endgültig löschen" in resp_inactive.text
    # Confirm-Input mit Vor- und Nachname als Placeholder
    assert "DrawerInact Person" in resp_inactive.text
