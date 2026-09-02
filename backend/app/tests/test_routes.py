from pathlib import Path
from uuid import uuid4
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.database import SessionLocal, engine
from app.main import app
from app.models.question import Question
from app.models.topic import Topic
from app.models.user import User


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        settings.JWT_SECRET_KEY = settings.JWT_SECRET_KEY or "test-secret"
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        engine.dispose()

    def setUp(self) -> None:
        self.user_ids: list[int] = []
        self.upload_paths: list[Path] = []

    def tearDown(self) -> None:
        with SessionLocal() as db:
            for user_id in self.user_ids:
                user = db.get(User, user_id)
                if user is not None:
                    db.delete(user)
            db.commit()

        for path in self.upload_paths:
            path.unlink(missing_ok=True)

    def test_auth_register_and_login(self) -> None:
        email = f"route-auth-{uuid4().hex}@example.com"
        register = self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "correct-horse"},
        )
        self.assertEqual(register.status_code, 201)
        self.user_ids.append(register.json()["id"])

        login = self.client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "correct-horse"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("access_token", login.json())

    def test_topics_create_and_list(self) -> None:
        user = self._create_user()
        headers = self._auth_headers(user.id)

        created = self.client.post(
            "/api/v1/topics/",
            headers=headers,
            json={"name": "Biology"},
        )
        self.assertEqual(created.status_code, 201)

        listed = self.client.get("/api/v1/topics/", headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["name"], "Biology")

    def test_documents_upload_enqueues_processing(self) -> None:
        user = self._create_user()
        headers = self._auth_headers(user.id)

        with patch("app.api.v1.documents.process_document.delay") as delay:
            response = self.client.post(
                "/api/v1/documents/",
                headers=headers,
                data={"title": "Notes", "source_type": "txt"},
                files={"file": ("notes.txt", b"plants use sunlight", "text/plain")},
            )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["status"], "pending")
        delay.assert_called_once_with(body["id"])
        self.upload_paths.append(Path("uploads") / Path(body["file_path"]).name)

    def test_practice_attempt_updates_progress_and_hides_foreign_answers(self) -> None:
        owner = self._create_user()
        intruder = self._create_user()
        topic, question = self._create_topic_question(owner.id)

        blocked = self.client.post(
            f"/api/v1/practice/{question.id}/attempt",
            headers=self._auth_headers(intruder.id),
            json={"is_correct": True},
        )
        self.assertEqual(blocked.status_code, 404)

        attempt = self.client.post(
            f"/api/v1/practice/{question.id}/attempt",
            headers=self._auth_headers(owner.id),
            json={"is_correct": True, "response_time_ms": 1000},
        )
        self.assertEqual(attempt.status_code, 201)
        self.assertEqual(attempt.json()["answer_text"], "By evaporation.")

        progress = self.client.get(
            f"/api/v1/progress/{topic.id}",
            headers=self._auth_headers(owner.id),
        )
        self.assertEqual(progress.status_code, 200)
        self.assertEqual(progress.json()["streak"], 1)

        due = self.client.get("/api/v1/progress/due", headers=self._auth_headers(owner.id))
        self.assertEqual(due.status_code, 200)
        self.assertEqual(due.json(), [])

    def _create_user(self) -> User:
        with SessionLocal() as db:
            user = User(
                email=f"route-{uuid4().hex}@example.com",
                hashed_password=hash_password("correct-horse"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            user_id = user.id
            email = user.email

        self.user_ids.append(user_id)
        return User(id=user_id, email=email, hashed_password="")

    def _create_topic_question(self, user_id: int) -> tuple[Topic, Question]:
        with SessionLocal() as db:
            topic = Topic(user_id=user_id, name="Water cycle")
            db.add(topic)
            db.commit()
            db.refresh(topic)

            question = Question(
                topic_id=topic.id,
                chunk_id=None,
                question_text="How does water leave oceans?",
                answer_text="By evaporation.",
                difficulty="easy",
            )
            db.add(question)
            db.commit()
            db.refresh(question)
            topic_id = topic.id
            question_id = question.id

        return (
            Topic(id=topic_id, user_id=user_id, name="Water cycle"),
            Question(
                id=question_id,
                topic_id=topic_id,
                chunk_id=None,
                question_text="How does water leave oceans?",
                answer_text="By evaporation.",
                difficulty="easy",
            ),
        )

    def _auth_headers(self, user_id: int) -> dict[str, str]:
        token = create_access_token({"sub": str(user_id)})
        return {"Authorization": f"Bearer {token}"}


if __name__ == "__main__":
    unittest.main()
