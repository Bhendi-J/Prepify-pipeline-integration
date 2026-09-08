from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.database import SessionLocal, engine
from app.main import app
from app.models.question import Question
from app.models.attempt import Attempt
from app.models.mastery import Mastery
from app.models.document import Document
from app.models.study_session import StudySession
from app.models.chunk import Chunk
from app.workers.tasks import summarize_document
from app.models.topic import Topic
from app.models.user import User
from app.services.question_gen import GeneratedQuestion
from app.workers.tasks import process_document


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

        questions = self.client.get(
            f"/api/v1/practice/{topic.id}/questions",
            headers=self._auth_headers(owner.id),
        )
        self.assertEqual(questions.status_code, 200)
        self.assertEqual(questions.json()[0]["id"], question.id)
        self.assertNotIn("answer_text", questions.json()[0])

        due = self.client.get("/api/v1/progress/due", headers=self._auth_headers(owner.id))
        self.assertEqual(due.status_code, 200)
        self.assertEqual(due.json(), [])

    def test_upload_to_practice_flow(self) -> None:
        owner = self._create_user()
        headers = self._auth_headers(owner.id)
        topic = self.client.post(
            "/api/v1/topics/", headers=headers, json={"name": "Water cycle"}
        ).json()
        with patch("app.api.v1.documents.process_document.delay"):
            uploaded = self.client.post(
                "/api/v1/documents/", headers=headers,
                data={"title": "Water notes", "source_type": ".txt", "topic_id": topic["id"]},
                files={"file": ("water.txt", b"Water leaves oceans by evaporation.", "text/plain")},
            )
        self.assertEqual(uploaded.status_code, 201)
        document = uploaded.json()
        self.upload_paths.append(Path(document["file_path"]))
        question_path = f"/api/v1/practice/{topic['id']}/question"
        with patch("app.services.retrieval.embed_query") as embed:
            pending = self.client.post(question_path, headers=headers, json={})
            self.assertEqual(pending.status_code, 404)
            embed.assert_not_called()
        # Exercise real ingestion and vector retrieval with deterministic provider outputs.
        with patch("app.workers.tasks.get_embeddings", return_value=[[1.0, 0.0, 0.0]]):
            process_document.run(document["id"])
        ready = self.client.get(f"/api/v1/documents/{document['id']}", headers=headers)
        self.assertEqual(ready.json()["status"], "ready")
        with patch("app.services.retrieval.embed_query", return_value=[1.0, 0.0, 0.0]):
            search = self.client.post(
                f"/api/v1/topics/{topic['id']}/search", headers=headers,
                json={"query": "How does water leave oceans?"},
            )
            self.assertEqual(search.status_code, 200)
            self.assertEqual(search.json()[0]["document_id"], document["id"])
            with patch("app.api.v1.practice.generate_question", return_value=GeneratedQuestion(
                question_text="How does water leave oceans?",
                answer_text="By evaporation.", difficulty="medium",
            )) as generate:
                first = self.client.post(question_path, headers=headers, json={})
                reused = self.client.post(question_path, headers=headers, json={})
                self.assertEqual(first.status_code, 201)
                self.assertEqual(reused.json()["id"], first.json()["id"])
                generate.assert_called_once()
        question = first.json()
        self.assertNotIn("answer_text", question)
        self.assertEqual(question["source_chunk_ids"], [search.json()[0]["chunk_id"]])
        revealed = self.client.get(
            f"/api/v1/practice/{question['id']}/answer", headers=headers
        )
        self.assertEqual(revealed.json()["answer_text"], "By evaporation.")
        rated = self.client.post(
            f"/api/v1/practice/{question['id']}/attempt", headers=headers,
            json={"is_correct": True, "submission_id": str(uuid4())},
        )
        self.assertEqual(rated.status_code, 201)
        progress = self.client.get(f"/api/v1/progress/{topic['id']}", headers=headers)
        self.assertEqual(progress.json()["streak"], 1)
        self.assertEqual(self.client.get("/api/v1/progress/due", headers=headers).json(), [])

    def test_reveal_is_private_and_does_not_record_a_rating(self) -> None:
        owner = self._create_user()
        intruder = self._create_user()
        topic, question = self._create_topic_question(owner.id)
        path = f"/api/v1/practice/{question.id}/answer"
        self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(
            self.client.get(path, headers=self._auth_headers(intruder.id)).status_code, 404
        )
        result = self.client.get(path, headers=self._auth_headers(owner.id))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {
            "question_id": question.id, "answer_text": "By evaporation."
        })
        with SessionLocal() as db:
            self.assertEqual(db.query(Attempt).filter_by(user_id=owner.id).count(), 0)
            self.assertEqual(db.query(Mastery).filter_by(user_id=owner.id).count(), 0)
        public = self.client.get(
            f"/api/v1/practice/{topic.id}/questions", headers=self._auth_headers(owner.id)
        )
        self.assertNotIn("answer_text", public.json()[0])

    def test_attempt_retry_does_not_advance_mastery_twice(self) -> None:
        owner = self._create_user()
        topic, question = self._create_topic_question(owner.id)
        headers = self._auth_headers(owner.id)
        path = f"/api/v1/practice/{question.id}/attempt"
        payload = {
            "is_correct": True, "response_time_ms": 1200, "submission_id": str(uuid4())
        }
        first = self.client.post(path, headers=headers, json=payload)
        retry = self.client.post(path, headers=headers, json=payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 201)
        self.assertEqual(first.json(), retry.json())
        conflict = self.client.post(path, headers=headers, json={**payload, "is_correct": False})
        self.assertEqual(conflict.status_code, 409)
        progress = self.client.get(
            f"/api/v1/progress/{topic.id}", headers=headers
        )
        self.assertEqual(progress.json()["streak"], 1)
        with SessionLocal() as db:
            self.assertEqual(db.query(Attempt).filter_by(user_id=owner.id).count(), 1)
        # A later deliberate review is still allowed, using a new submission ID.
        subsequent = self.client.post(
            path, headers=headers, json={**payload, "submission_id": str(uuid4())}
        )
        self.assertEqual(subsequent.status_code, 201)
        self.assertNotEqual(subsequent.json()["id"], first.json()["id"])

    def test_concurrent_attempt_retries_record_one_attempt(self) -> None:
        owner = self._create_user()
        topic, question = self._create_topic_question(owner.id)
        headers = self._auth_headers(owner.id)
        payload = {"is_correct": True, "submission_id": str(uuid4())}

        def submit():
            return self.client.post(
                f"/api/v1/practice/{question.id}/attempt", headers=headers, json=payload
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual([result.status_code for result in results], [201, 201])
        self.assertEqual(results[0].json()["id"], results[1].json()["id"])
        progress = self.client.get(
            f"/api/v1/progress/{topic.id}", headers=headers
        )
        self.assertEqual(progress.json()["streak"], 1)

    def _ready_notes(self, user_id: int, topic_id: int, title: str = "Notes", content: str = "Water evaporates from the ocean.") -> Document:
        path = Path("uploads") / f"test-{uuid4().hex}.txt"
        path.write_text(content)
        self.upload_paths.append(path)
        with SessionLocal() as db:
            document = Document(user_id=user_id, topic_id=topic_id, title=title,
                source_type=".txt", file_path=str(path), status="ready")
            db.add(document)
            db.flush()
            db.add(Chunk(document_id=document.id, topic_id=topic_id, content=content,
                embedding=[1.0, 0.0, 0.0], token_count=len(content.split())))
            db.commit()
            db.refresh(document)
            db.expunge(document)
            return document

    def test_session_batch_filter_paging_and_retry(self) -> None:
        owner = self._create_user()
        topic, old = self._create_topic_question(owner.id)
        selected = self._ready_notes(owner.id, topic.id, "Selected notes", "Only the selected source")
        self._ready_notes(owner.id, topic.id, "Other notes", "Must never enter this prompt")
        headers = self._auth_headers(owner.id)
        payload = {"topic_id": topic.id, "document_id": selected.id, "count": 3, "request_id": str(uuid4())}
        batch = [GeneratedQuestion(f"Distinct question {i}?", f"Answer {i}", "medium") for i in range(3)]
        source_ids = []
        def generated_batch(chunks, *args):
            source_ids.extend(chunk.document_id for chunk in chunks)
            return batch
        with patch("app.services.retrieval.embed_query", return_value=[1.0, 0.0, 0.0]), patch(
            "app.api.v1.study_sessions.generate_questions", side_effect=generated_batch
        ) as generate:
            first = self.client.post("/api/v1/study-sessions/", headers=headers, json=payload)
            self.assertEqual(first.status_code, 201, first.text)
            retry = self.client.post("/api/v1/study-sessions/", headers=headers, json=payload)
            self.assertEqual(retry.status_code, 201)
            self.assertEqual(first.json()["session"]["id"], retry.json()["session"]["id"])
            generate.assert_called_once()
            self.assertEqual(source_ids, [selected.id])
        result = first.json()
        self.assertEqual(result["total"], 3)
        self.assertEqual(len(result["items"]), 1)
        self.assertNotEqual(result["items"][0]["id"], old.id)
        self.assertNotIn("answer_text", result["items"][0])
        session_id = result["session"]["id"]
        last = self.client.get(f"/api/v1/study-sessions/{session_id}?page=3", headers=headers)
        self.assertEqual(last.json()["items"][0]["question_text"], "Distinct question 2?")
        self.assertEqual(self.client.get(f"/api/v1/study-sessions/{session_id}?page=4", headers=headers).status_code, 404)
        intruder = self._create_user()
        self.assertEqual(self.client.get(f"/api/v1/study-sessions/{session_id}", headers=self._auth_headers(intruder.id)).status_code, 404)
        changed = self.client.post("/api/v1/study-sessions/", headers=headers, json={**payload, "count": 2})
        self.assertEqual(changed.status_code, 409)
        rating = self.client.post(f"/api/v1/practice/{result['items'][0]['id']}/attempt", headers=headers,
            json={"is_correct": True, "submission_id": str(uuid4())})
        self.assertEqual(rating.status_code, 201)
        reopened = self.client.get(f"/api/v1/study-sessions/{session_id}", headers=headers)
        self.assertEqual(reopened.json()["attempts"][0]["answer_text"], "Answer 0")

    def test_session_failure_is_atomic_and_checks_document_ownership(self) -> None:
        from app.services.question_gen import QuestionGenerationError
        owner = self._create_user()
        topic, _ = self._create_topic_question(owner.id)
        document = self._ready_notes(owner.id, topic.id)
        headers = self._auth_headers(owner.id)
        payload = {"topic_id": topic.id, "document_id": document.id, "count": 3, "request_id": str(uuid4())}
        with patch("app.services.retrieval.embed_query", return_value=[1.0, 0.0, 0.0]), patch(
            "app.api.v1.study_sessions.generate_questions", side_effect=QuestionGenerationError("Repeated question")
        ):
            result = self.client.post("/api/v1/study-sessions/", headers=headers, json=payload)
        self.assertEqual(result.status_code, 502)
        with SessionLocal() as db:
            self.assertEqual(db.query(StudySession).filter_by(user_id=owner.id).count(), 0)
            self.assertEqual(db.query(Question).filter_by(topic_id=topic.id).count(), 1)
        other_topic, _ = self._create_topic_question(owner.id)
        wrong = self.client.post("/api/v1/study-sessions/", headers=headers, json={**payload, "topic_id": other_topic.id})
        self.assertEqual(wrong.status_code, 404)
        with patch.object(settings, "MAX_QUESTION_GENERATIONS_PER_DAY", 3):
            capped = self.client.post("/api/v1/study-sessions/", headers=headers, json=payload)
        self.assertEqual(capped.status_code, 429)

    def test_session_history_is_paginated(self) -> None:
        owner = self._create_user()
        topic, _ = self._create_topic_question(owner.id)
        with SessionLocal() as db:
            db.add_all(StudySession(user_id=owner.id, topic_id=topic.id, title=f"Session {i}",
                difficulty="medium", question_type="short_answer") for i in range(8))
            db.commit()
        headers = self._auth_headers(owner.id)
        first = self.client.get(f"/api/v1/study-sessions/?topic_id={topic.id}", headers=headers)
        second = self.client.get(f"/api/v1/study-sessions/?topic_id={topic.id}&page=2", headers=headers)
        self.assertEqual(first.json()["total"], 8)
        self.assertEqual(len(first.json()["items"]), 6)
        self.assertEqual(len(second.json()["items"]), 2)
        self.assertTrue(set(item["id"] for item in first.json()["items"]).isdisjoint(item["id"] for item in second.json()["items"]))

    def test_original_notes_pagination_and_summary_cache(self) -> None:
        owner = self._create_user()
        topic, _ = self._create_topic_question(owner.id)
        source = "A first paragraph.\n\n" + "Long notes. " * 500
        document = self._ready_notes(owner.id, topic.id, content=source)
        headers = self._auth_headers(owner.id)
        base = f"/api/v1/documents/{document.id}"
        first = self.client.get(base + "/content", headers=headers)
        second = self.client.get(base + "/content?page=2", headers=headers)
        self.assertEqual(first.json()["total_pages"], 2)
        self.assertEqual(first.json()["content"] + second.json()["content"], source)
        intruder = self._create_user()
        for path in ["/content", "/summary"]:
            self.assertEqual(self.client.get(base + path, headers=self._auth_headers(intruder.id)).status_code, 404)
        with patch("app.api.v1.documents.summarize_document.delay") as queue:
            queued = self.client.post(base + "/summary", headers=headers)
            again = self.client.post(base + "/summary", headers=headers)
            self.assertEqual(queued.status_code, 202)
            self.assertEqual(again.json()["status"], "pending")
            queue.assert_called_once_with(document.id)
        with patch("app.services.summarization.summarize_notes", return_value="A helpful summary.") as summarize:
            summarize_document.run(document.id)
            summarize.assert_called_once_with(source)
        with patch("app.api.v1.documents.summarize_document.delay") as queue:
            cached = self.client.post(base + "/summary", headers=headers)
            self.assertEqual(cached.json()["summary"], "A helpful summary.")
            self.assertEqual(cached.json()["status"], "ready")
            queue.assert_not_called()

    def test_summary_queue_failure_can_retry(self) -> None:
        owner = self._create_user()
        topic, _ = self._create_topic_question(owner.id)
        document = self._ready_notes(owner.id, topic.id)
        headers = self._auth_headers(owner.id)
        path = f"/api/v1/documents/{document.id}/summary"
        with patch("app.api.v1.documents.summarize_document.delay", side_effect=RuntimeError("queue down")):
            self.assertEqual(self.client.post(path, headers=headers).status_code, 503)
        self.assertEqual(self.client.get(path, headers=headers).json()["status"], "failed")
        with patch("app.api.v1.documents.summarize_document.delay"):
            self.assertEqual(self.client.post(path, headers=headers).json()["status"], "pending")

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
