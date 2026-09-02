import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.config import settings
from app.models.chunk import Chunk


class QuestionGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeneratedQuestion:
    question_text: str
    answer_text: str
    difficulty: str


def build_prompt(chunks: Sequence[Chunk], difficulty: str) -> str:
    context = "\n\n".join(
        f"Chunk {index + 1}:\n{chunk.content}"
        for index, chunk in enumerate(chunks)
    )
    return f"""
You are creating one study practice question from the user's uploaded notes.
Use only the study notes. Do not invent facts.

Return only JSON with exactly these keys:
question_text, answer_text, difficulty

The question should be {difficulty} difficulty.
The answer should be concise but complete.

Study notes:
{context}
""".strip()


def generate_question(
    chunks: Sequence[Chunk],
    difficulty: str = "medium",
) -> GeneratedQuestion:
    if not chunks:
        raise QuestionGenerationError("Cannot generate a question without chunks")
    if not settings.HF_TOKEN:
        raise QuestionGenerationError("HF_TOKEN is required for question generation")

    try:
        from huggingface_hub import InferenceClient
    except ImportError as exc:
        raise QuestionGenerationError(
            "Install huggingface_hub to use question generation"
        ) from exc

    client = InferenceClient(
        provider=settings.HUGGINGFACE_CHAT_PROVIDER,
        api_key=settings.HF_TOKEN,
    )
    try:
        response = client.chat_completion(
            model=settings.HUGGINGFACE_QUESTION_MODEL,
            messages=[{"role": "user", "content": build_prompt(chunks, difficulty)}],
            max_tokens=settings.QUESTION_MAX_TOKENS,
            temperature=settings.QUESTION_TEMPERATURE,
        )
        content = response.choices[0].message.content
    except Exception as exc:
        raise QuestionGenerationError("Question generation provider failed") from exc

    if not content:
        raise QuestionGenerationError("Question generation returned empty content")

    payload = _parse_question_payload(content)
    return GeneratedQuestion(
        question_text=payload["question_text"],
        answer_text=payload["answer_text"],
        difficulty=payload.get("difficulty") or difficulty,
    )


def _parse_question_payload(content: str) -> dict[str, str]:
    json_text = _extract_json(content)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise QuestionGenerationError("Question generation returned invalid JSON") from exc

    question_text = str(payload.get("question_text") or "").strip()
    answer_text = str(payload.get("answer_text") or "").strip()
    difficulty = str(payload.get("difficulty") or "").strip()
    if not question_text or not answer_text:
        raise QuestionGenerationError(
            "Question generation response is missing question_text or answer_text"
        )

    return {
        "question_text": question_text,
        "answer_text": answer_text,
        "difficulty": difficulty,
    }


def _extract_json(content: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fenced:
        return fenced.group(1)

    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise QuestionGenerationError("Question generation response did not include JSON")
    return content[start : end + 1]
