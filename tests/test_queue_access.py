"""What the queue sends each viewer: staff see everything; a student sees their
own tickets and groups in full, and only what the queue lists about anyone
else's; signed-out visitors see only that."""

import pytest

from oh_queue.models import Assignment, Group, Location, db
from tests.conftest import log_in

PRIVATE_TICKET_FIELDS = {
    "description", "call_url", "doc_url", "llm_tips", "use_llm", "student_help_type",
    "student_help_other", "staff_help_type", "staff_help_other", "llm_tips_influence",
    "rerequest_threshold",
}


def state(client):
    response = client.post("/api/connect", json={"url": "http://localhost/"})
    return {key: value for _, s in response.get_json()["updates"] for key, value in s.items()}


def api(client, name, payload):
    return client.post(f"/api/{name}", json=payload).get_json()["action"]


@pytest.fixture()
def queue(app):
    """A queue with one ticket from each of two students, the first being
    helped by a TA and holding a chat message, and a group from the second."""
    staff, alice, bob, visitor = (app.test_client() for _ in range(4))
    staff.get("/")
    log_in(staff, "ta@example.edu", "TA Person", is_staff=True)
    log_in(alice, "alice@example.edu", "Alice Student", is_staff=False)
    log_in(bob, "bob@example.edu", "Bob Student", is_staff=False)
    with app.app_context():
        assignment = Assignment(name="Hog", visible=True, course="cs61a")
        location = Location(name="Cory", visible=True, online=False, link="", course="cs61a")
        db.session.add_all([assignment, location])
        db.session.commit()
        ids = {"assignment_id": assignment.id, "location_id": location.id}

    redirect = api(alice, "create", {**ids, "question": "1", "description": "my secret bug",
                                     "call-link": "meet.google.com/alice"})["redirect"]
    alice_ticket = int(redirect.strip("/").split("/")[-1])
    api(alice, "send_chat_message", {"mode": "ticket", "id": alice_ticket, "content": "hello"})
    api(staff, "update_staff_online_setup", {"staff-call-link": "meet.google.com/ta", "staff-doc-link": ""})
    api(staff, "assign", [alice_ticket])
    redirect = api(bob, "create", {**ids, "question": "2", "description": "bob's bug"})["redirect"]
    bob_ticket = int(redirect.strip("/").split("/")[-1])

    api(staff, "update_config", {"key": "party_enabled", "value": "true"})
    api(bob, "create_group", {**ids, "question": "3", "call-link": "meet.google.com/bobgroup"})
    with app.app_context():
        group_id = Group.query.one().id
    api(bob, "update_group", {"id": group_id, "description": "study group"})
    api(bob, "send_chat_message", {"mode": "group", "id": group_id, "content": "group chat"})

    return {"staff": staff, "alice": alice, "bob": bob, "visitor": visitor,
            "alice_ticket": alice_ticket, "bob_ticket": bob_ticket, "group": group_id}


def tickets(client):
    return {t["id"]: t for t in state(client)["tickets"]}


def assert_public(ticket):
    assert ticket["user"] is None
    assert ticket["messages"] == []
    assert not PRIVATE_TICKET_FIELDS & set(ticket)
    if ticket["helper"]:
        assert set(ticket["helper"]) == {"id", "name", "shortName", "isStaff"}


def test_staff_see_every_ticket_in_full(queue):
    seen = tickets(queue["staff"])
    assert seen[queue["alice_ticket"]]["user"]["email"] == "alice@example.edu"
    assert seen[queue["alice_ticket"]]["description"] == "my secret bug"
    assert seen[queue["alice_ticket"]]["messages"][0]["body"] == "hello"
    assert seen[queue["bob_ticket"]]["description"] == "bob's bug"


def test_students_see_their_own_ticket_in_full(queue):
    mine = tickets(queue["alice"])[queue["alice_ticket"]]
    assert mine["user"]["email"] == "alice@example.edu"
    assert mine["description"] == "my secret bug"
    assert mine["messages"][0]["body"] == "hello"
    # The helper's call link, to join the call.
    assert mine["helper"]["call_url"].endswith("meet.google.com/ta")


def test_students_see_only_what_the_queue_lists_about_other_tickets(queue):
    theirs = tickets(queue["bob"])[queue["alice_ticket"]]
    assert_public(theirs)
    assert (theirs["status"], theirs["question"], theirs["helper"]["name"]) == ("assigned", "1", "TA Person")


def test_signed_out_visitors_see_only_what_the_queue_lists(queue):
    seen = tickets(queue["visitor"])
    assert set(seen) == {queue["alice_ticket"], queue["bob_ticket"]}
    for ticket in seen.values():
        assert_public(ticket)


def test_only_staff_see_who_is_online(queue):
    assert state(queue["staff"])["presence"]["staff_list"] == [["ta@example.edu", "TA Person"]]
    for viewer in ("alice", "visitor"):
        presence = state(queue[viewer])["presence"]
        assert "staff_list" not in presence
        assert presence["staff"] == 1


def test_group_members_see_their_group_in_full(queue):
    group = state(queue["bob"])["groups"][0]
    assert group["call_url"].endswith("meet.google.com/bobgroup")
    assert group["messages"][0]["body"] == "group chat"
    assert group["attendees"][0]["user"]["email"] == "bob@example.edu"


@pytest.mark.parametrize("viewer", ["alice", "visitor"])
def test_others_see_only_what_a_group_card_and_page_show(queue, viewer):
    group = state(queue[viewer])["groups"][0]
    assert (group["description"], group["question"]) == ("study group", "3")
    assert group["messages"] == []
    assert "call_url" not in group and "doc_url" not in group
    # The group's page lists who's in it, without their emails or links.
    member = group["attendees"][0]["user"]
    assert {k: member[k] for k in ("name", "shortName", "isStaff")} == {
        "name": "Bob Student", "shortName": "Bob", "isStaff": False}
    assert set(member) == {"id", "name", "shortName", "isStaff"}


def test_signed_out_visitors_cant_change_a_group(queue, app):
    response = api(queue["visitor"], "update_group", {"id": queue["group"], "description": "changed"})
    assert "permission" in response["messages"][0]["text"]
    response = api(queue["visitor"], "create_group_ticket", {"id": queue["group"]})
    assert "permission" in response["messages"][0]["text"]
    with app.app_context():
        group = db.session.get(Group, queue["group"])
        assert group.description == "study group"
        assert group.ticket_id is None


def test_signed_out_visitors_cant_open_a_group_by_its_address(queue):
    response = queue["visitor"].post("/api/connect", json={"url": f"http://localhost/groups/{queue['group']}/"})
    groups = [g for _, s in response.get_json()["updates"] for g in s.get("groups", [])]
    assert all("call_url" not in g for g in groups)


def test_students_keep_seeing_their_group_ticket_after_leaving(queue):
    api(queue["bob"], "delete", [queue["bob_ticket"]])
    api(queue["bob"], "create_group_ticket", {"id": queue["group"]})
    group_ticket = [t for t in state(queue["bob"])["tickets"] if t["group_id"] == queue["group"]][0]["id"]
    api(queue["bob"], "leave_group", queue["group"])
    bob_id = state(queue["bob"])["current_user"]["id"]
    history = {t["id"]: t for t in api(queue["bob"], "get_user", bob_id)["tickets"]}
    assert history[group_ticket]["user"]["email"] == "bob@example.edu"
    assert history[group_ticket]["description"] == "This ticket is associated with a group."


def test_a_missing_ticket_is_refused_not_an_error(queue):
    response = api(queue["alice"], "update_ticket", {"id": 999, "description": "x"})
    assert "permission" in response["messages"][0]["text"]
