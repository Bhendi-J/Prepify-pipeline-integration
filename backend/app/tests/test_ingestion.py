from pathlib import Path
import tempfile
import unittest

from app.services.ingestion import UnsupportedDocumentTypeError, chunk_text, extract_text


class IngestionTests(unittest.TestCase):
    def test_extract_text_reads_txt_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notes.txt"
            path.write_text("hello from notes", encoding="utf-8")

            self.assertEqual(extract_text(str(path)), "hello from notes")

    def test_extract_text_rejects_unsupported_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notes.pdf"
            path.write_text("not actually a pdf", encoding="utf-8")

            with self.assertRaises(UnsupportedDocumentTypeError):
                extract_text(str(path))

    def test_chunk_text_applies_overlap(self) -> None:
        chunks = chunk_text(
            "one two three four five six seven",
            max_tokens=4,
            overlap_tokens=2,
        )

        self.assertEqual([chunk.content for chunk in chunks], [
            "one two three four",
            "three four five six",
            "five six seven",
        ])
        self.assertEqual([chunk.token_count for chunk in chunks], [4, 4, 3])


if __name__ == "__main__":
    unittest.main()
