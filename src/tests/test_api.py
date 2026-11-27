import pytest

from src import app as app_module


def test_root_redirects_to_static_index(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/static/index.html"


def test_get_activities_returns_activity_details(client):
    response = client.get("/activities")

    assert response.status_code == 200
    chess = response.json()["Chess Club"]
    assert set(chess) == {"description", "schedule", "max_participants", "participants"}
    assert "michael@mergington.edu" in chess["participants"]


def test_signup_and_unregister_update_activities(client):
    email = "Student@MERGINGTON.EDU"
    url = "/activities/Chess Club/signup"

    response = client.post(url, params={"email": email})
    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for Chess Club"}
    assert email in client.get("/activities").json()["Chess Club"]["participants"]

    response = client.delete(url, params={"email": email})
    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from Chess Club"}
    assert email not in client.get("/activities").json()["Chess Club"]["participants"]


@pytest.mark.parametrize("method", ["post", "delete"])
def test_unknown_activity_returns_not_found(client, method):
    response = getattr(client, method)(
        "/activities/Unknown/signup", params={"email": "student@mergington.edu"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}


@pytest.mark.parametrize("method", ["post", "delete"])
def test_missing_email_returns_validation_error(client, method):
    response = getattr(client, method)("/activities/Chess Club/signup")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "email"]


def test_duplicate_signup_does_not_change_participants(client):
    participants = client.get("/activities").json()["Chess Club"]["participants"]
    response = client.post(
        "/activities/Chess Club/signup", params={"email": participants[0]}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Student already signed up for this activity"}
    assert client.get("/activities").json()["Chess Club"]["participants"] == participants


def test_unregister_nonparticipant_does_not_change_participants(client):
    participants = client.get("/activities").json()["Chess Club"]["participants"]
    response = client.delete(
        "/activities/Chess Club/signup", params={"email": "student@mergington.edu"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Student is not signed up for this activity"}
    assert client.get("/activities").json()["Chess Club"]["participants"] == participants


@pytest.mark.parametrize("email", ["not-an-email", "student@", "@mergington.edu"])
def test_signup_rejects_malformed_email_without_mutation(client, email):
    participants = client.get("/activities").json()["Chess Club"]["participants"]
    response = client.post("/activities/Chess Club/signup", params={"email": email})

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid email address"}
    assert client.get("/activities").json()["Chess Club"]["participants"] == participants


def test_unregister_does_not_validate_email_format(client):
    app_module.activities["Chess Club"]["participants"].append("legacy-address")
    response = client.delete(
        "/activities/Chess Club/signup", params={"email": "legacy-address"}
    )

    assert response.status_code == 200
    assert "legacy-address" not in client.get("/activities").json()["Chess Club"]["participants"]


def test_signup_fills_last_available_place(client):
    activity = app_module.activities["Chess Club"]
    activity["max_participants"] = len(activity["participants"]) + 1
    email = "student@mergington.edu"

    response = client.post("/activities/Chess Club/signup", params={"email": email})

    assert response.status_code == 200
    assert email in client.get("/activities").json()["Chess Club"]["participants"]


@pytest.mark.parametrize("extra_participants", [0, 1])
@pytest.mark.parametrize("duplicate", [False, True])
def test_full_activity_rejects_signup_before_duplicate_check(
    client, extra_participants, duplicate
):
    activity = app_module.activities["Chess Club"]
    activity["max_participants"] = len(activity["participants"]) - extra_participants
    participants = activity["participants"].copy()
    email = participants[0] if duplicate else "student@mergington.edu"

    response = client.post("/activities/Chess Club/signup", params={"email": email})

    assert response.status_code == 400
    assert response.json() == {"detail": "Activity is full"}
    assert client.get("/activities").json()["Chess Club"]["participants"] == participants
