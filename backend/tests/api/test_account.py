import io

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from tests.api.test_auth import token_from
from tests.conftest import TEST_PASSWORD, FakeEmailSender, make_user


def picture(width: int = 800, height: int = 600, kind: str = "PNG") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), (200, 120, 60)).save(out, kind)
    return out.getvalue()


def me(client: TestClient) -> dict[str, object]:
    body: dict[str, object] = client.get("/api/auth/me").json()
    return body


class TestName:
    def test_can_be_changed_once(self, user_client: TestClient) -> None:
        first = user_client.patch("/api/auth/me/name", json={"display_name": "  Neeraj  "})

        assert first.status_code == 200
        assert first.json()["display_name"] == "Neeraj"
        assert first.json()["name_changed_at"] is not None
        again = user_client.patch("/api/auth/me/name", json={"display_name": "Someone else"})
        assert again.status_code == 409
        assert again.json()["detail"] == "You've already used your one name change"
        assert me(user_client)["display_name"] == "Neeraj"

    def test_a_blank_name_is_refused(self, user_client: TestClient) -> None:
        response = user_client.patch("/api/auth/me/name", json={"display_name": "   "})

        assert response.status_code == 422
        assert me(user_client)["name_changed_at"] is None  # the one change isn't used up


def test_gender_picks_the_icon(user_client: TestClient) -> None:
    assert me(user_client)["gender"] == "unspecified"

    assert user_client.put("/api/auth/me/gender", json={"gender": "female"}).status_code == 200

    assert me(user_client)["gender"] == "female"
    assert user_client.put("/api/auth/me/gender", json={"gender": "robot"}).status_code == 422


class TestPicture:
    def test_a_photo_becomes_a_small_square(self, user_client: TestClient) -> None:
        saved = user_client.put(
            "/api/auth/me/avatar", files={"file": ("me.png", picture(), "image/png")}
        )

        assert saved.status_code == 200
        assert saved.json()["has_avatar"] is True
        served = user_client.get("/api/auth/me/avatar")
        assert served.headers["content-type"] == "image/jpeg"
        assert Image.open(io.BytesIO(served.content)).size == (256, 256)

    def test_it_can_be_removed(self, user_client: TestClient) -> None:
        user_client.put("/api/auth/me/avatar", files={"file": ("me.jpg", picture(kind="JPEG"))})

        assert user_client.delete("/api/auth/me/avatar").status_code == 204

        assert me(user_client)["has_avatar"] is False
        assert user_client.get("/api/auth/me/avatar").status_code == 404

    def test_other_files_are_refused(self, user_client: TestClient) -> None:
        response = user_client.put(
            "/api/auth/me/avatar", files={"file": ("notes.txt", b"hello", "text/plain")}
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "That file isn't a picture we can read"


class TestEmail:
    def test_changes_once_the_new_address_is_confirmed(
        self, user_client: TestClient, mailer: FakeEmailSender
    ) -> None:
        asked = user_client.post(
            "/api/auth/me/email", json={"email": "New@Example.com", "password": TEST_PASSWORD}
        )

        assert asked.status_code == 202
        assert mailer.outbox[-1].to == "new@example.com"
        assert "/confirm-email?token=" in mailer.outbox[-1].body
        assert (me(user_client)["email"], me(user_client)["pending_email"]) == (
            "reader@example.com",
            "new@example.com",
        )  # the old address stays until the link is opened

        token = token_from(mailer)
        assert user_client.post("/api/auth/confirm-email", json={"token": token}).status_code == 204

        assert (me(user_client)["email"], me(user_client)["pending_email"]) == (
            "new@example.com",
            None,
        )
        assert user_client.post("/api/auth/confirm-email", json={"token": token}).status_code == 400

    def test_needs_the_password(self, user_client: TestClient) -> None:
        response = user_client.post(
            "/api/auth/me/email", json={"email": "new@example.com", "password": "wrong password"}
        )

        assert response.status_code == 403
        assert me(user_client)["pending_email"] is None

    def test_an_address_in_use_is_refused(self, user_client: TestClient, session: Session) -> None:
        make_user(session, "taken@example.com")

        response = user_client.post(
            "/api/auth/me/email", json={"email": "taken@example.com", "password": TEST_PASSWORD}
        )

        assert response.status_code == 409


class TestPassword:
    def test_changes_with_the_current_one(self, user_client: TestClient) -> None:
        body = {"current_password": TEST_PASSWORD, "new_password": "a much better secret"}

        assert user_client.post("/api/auth/me/password", json=body).status_code == 204

        assert user_client.post("/api/auth/logout").status_code == 204
        login = {"email": "reader@example.com", "password": "a much better secret"}
        assert user_client.post("/api/auth/login", json=login).status_code == 200

    def test_a_wrong_current_password_is_refused(self, user_client: TestClient) -> None:
        body = {"current_password": "not it at all", "new_password": "a much better secret"}

        assert user_client.post("/api/auth/me/password", json=body).status_code == 403
