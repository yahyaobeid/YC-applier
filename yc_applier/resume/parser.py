from pathlib import Path

from pypdf import PdfReader


def parse_resume(pdf_path: str | Path) -> str:
    """Extract plain text from a PDF resume."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume not found at: {path}")

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())

    full_text = "\n\n".join(pages)
    if not full_text.strip():
        raise ValueError(f"Could not extract any text from {path}. Is it a scanned PDF?")

    return full_text
