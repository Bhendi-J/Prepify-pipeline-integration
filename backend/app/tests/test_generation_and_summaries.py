import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.core.config import settings
from app.models.chunk import Chunk
from app.services.question_gen import generate_questions, QuestionGenerationError
from app.services.summarization import summarize_notes, SummaryError


def response(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class GenerationTests(unittest.TestCase):
    def test_batch_uses_one_model_call(self):
        items = [
            {"question_text": "What powers photosynthesis?", "answer_text": "Sunlight"},
            {"question_text": "Where does water evaporate?", "answer_text": "From oceans"},
            {"question_text": "Explain the role of chlorophyll.", "answer_text": "Absorbs light"},
        ]
        with patch.object(settings, "HF_TOKEN", "test-token"), patch("huggingface_hub.InferenceClient") as client:
            client.return_value.chat_completion.return_value = response(json.dumps({"questions": items}))
            result = generate_questions([Chunk(content="Study notes")], 3, "medium", "short_answer")
            self.assertEqual(len(result), 3)
            client.return_value.chat_completion.assert_called_once()

    def test_duplicate_and_incomplete_batches_are_rejected(self):
        old = "What powers photosynthesis?"
        for items, count, history in [
            ([{"question_text": "WHAT powers photosynthesis!", "answer_text": "Sunlight"}], 1, [old]),
            ([{"question_text": old, "answer_text": "Sunlight"}] * 2, 2, []),
            ([{"question_text": old, "answer_text": None}], 1, []),
        ]:
            with self.subTest(items=items), patch.object(settings, "HF_TOKEN", "test"), patch("huggingface_hub.InferenceClient") as client:
                client.return_value.chat_completion.return_value = response(json.dumps({"questions": items}))
                with self.assertRaises(QuestionGenerationError):
                    generate_questions([Chunk(content="Notes")], count, "medium", "short_answer", history)

    def test_multiple_choice_answers_are_normalized(self):
        items = [{
            "question_text": "What does Redis do? A) Store style sheets B) Hold queue messages C) Compile TypeScript D) Host Postgres",
            "answer_text": "B) Hold queue messages",
        }]
        with patch.object(settings, "HF_TOKEN", "test"), patch("huggingface_hub.InferenceClient") as client:
            client.return_value.chat_completion.return_value = response(json.dumps({"questions": items}))
            result = generate_questions([Chunk(content="Notes")], 3, "medium", "multiple_choice")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].answer_text, "B")
            self.assertIn("\nA)", result[0].question_text)

    def test_multiple_choice_falls_back_when_provider_fails(self):
        note = "Redis stores queue messages for Celery workers so background jobs can run after uploads."
        with patch.object(settings, "HF_TOKEN", "test"), patch("huggingface_hub.InferenceClient") as client:
            client.return_value.chat_completion.side_effect = RuntimeError("provider down")
            result = generate_questions([Chunk(content=note)], 2, "medium", "multiple_choice")
            self.assertEqual(result[0].answer_text, "A")
            self.assertIn("A)", result[0].question_text)

    def test_multiple_choice_falls_back_when_provider_format_is_bad(self):
        items = [{"question_text": "What does Redis do?", "answer_text": "Queue messages"}]
        note = "Redis stores queue messages for Celery workers so background jobs can run after uploads."
        with patch.object(settings, "HF_TOKEN", "test"), patch("huggingface_hub.InferenceClient") as client:
            client.return_value.chat_completion.return_value = response(json.dumps({"questions": items}))
            result = generate_questions([Chunk(content=note)], 1, "medium", "multiple_choice")
            self.assertEqual(result[0].answer_text, "A")
            self.assertIn("Redis stores queue messages", result[0].question_text)

    def test_long_summary_includes_the_end_of_the_notes(self):
        text = "first section " * 1500 + "IMPORTANT FINAL SECTION"
        with patch.object(settings, "HF_TOKEN", "test"), patch("huggingface_hub.InferenceClient") as client:
            client.return_value.chat_completion.return_value = response("A concise summary")
            self.assertEqual(summarize_notes(text), "A concise summary")
            prompts = [call.kwargs["messages"][1]["content"] for call in client.return_value.chat_completion.call_args_list]
            self.assertTrue(any("IMPORTANT FINAL SECTION" in prompt for prompt in prompts))
            self.assertGreater(len(prompts), 1)
            self.assertTrue(all(len(prompt) < 12200 for prompt in prompts))

    def test_empty_notes_cannot_be_summarized(self):
        with self.assertRaises(SummaryError):
            summarize_notes("  \n ")
