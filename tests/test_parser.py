"""Tests for resume/parser.py."""

import io
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from yc_applier.resume.parser import parse_resume


def test_parse_resume_file_not_found():
    with pytest.raises(FileNotFoundError, match="Resume not found"):
        parse_resume("/nonexistent/path/resume.pdf")


def test_parse_resume_empty_pdf(tmp_path):
    """A PDF that yields no text should raise ValueError."""
    pdf_file = tmp_path / "empty.pdf"
    pdf_file.write_bytes(b"%PDF-1.4")  # minimal stub

    with patch("yc_applier.resume.parser.PdfReader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader.pages = [mock_page]
        mock_reader_cls.return_value = mock_reader

        with pytest.raises(ValueError, match="Could not extract any text"):
            parse_resume(pdf_file)


def test_parse_resume_returns_text(tmp_path):
    pdf_file = tmp_path / "resume.pdf"
    pdf_file.write_bytes(b"%PDF-1.4")

    with patch("yc_applier.resume.parser.PdfReader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "  John Doe\nSoftware Engineer  "
        mock_reader.pages = [mock_page]
        mock_reader_cls.return_value = mock_reader

        result = parse_resume(pdf_file)

    assert "John Doe" in result
    assert "Software Engineer" in result
    assert result == result.strip()


def test_parse_resume_multiple_pages(tmp_path):
    pdf_file = tmp_path / "resume.pdf"
    pdf_file.write_bytes(b"%PDF-1.4")

    with patch("yc_applier.resume.parser.PdfReader") as mock_reader_cls:
        mock_reader = MagicMock()
        page1 = MagicMock()
        page1.extract_text.return_value = "Page one content"
        page2 = MagicMock()
        page2.extract_text.return_value = "Page two content"
        mock_reader.pages = [page1, page2]
        mock_reader_cls.return_value = mock_reader

        result = parse_resume(pdf_file)

    assert "Page one content" in result
    assert "Page two content" in result
