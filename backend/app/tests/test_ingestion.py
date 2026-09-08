from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from app.services.ingestion import EmptyDocumentTextError, UnsupportedDocumentTypeError, chunk_text, extract_text


class IngestionTests(unittest.TestCase):
    def test_extract_text_reads_txt_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notes.txt"
            path.write_text("hello from notes", encoding="utf-8")

            self.assertEqual(extract_text(str(path)), "hello from notes")

    def test_extract_text_rejects_unsupported_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notes.docx"
            path.write_text("not supported", encoding="utf-8")

            with self.assertRaises(UnsupportedDocumentTypeError):
                extract_text(str(path))

    def test_extract_text_reads_pdf_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notes.pdf"
            path.write_bytes(b"%PDF-1.4")
            first_page = Mock()
            first_page.extract_text.return_value = "first page"
            second_page = Mock()
            second_page.extract_text.return_value = "second page"

            with patch("app.services.ingestion.PdfReader") as reader:
                reader.return_value.pages = [first_page, second_page]

                self.assertEqual(extract_text(str(path)), "first page\n\nsecond page")

    def test_extract_text_rejects_image_only_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scan.pdf"
            path.write_bytes(b"%PDF-1.4")

            with patch("app.services.ingestion.PdfReader") as reader:
                page = Mock()
                page.extract_text.return_value = ""
                reader.return_value.pages = [page]

                with self.assertRaises(EmptyDocumentTextError):
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
