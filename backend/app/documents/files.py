import io
import re
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_CHUNK_CHARS = 1000


def stored_path(stored_name: str) -> Path:
    return UPLOAD_DIR / stored_name


def save_file(extension: str, content: bytes) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    stored_path(stored_name).write_bytes(content)
    return stored_name


def delete_file(stored_name: str) -> None:
    stored_path(stored_name).unlink(missing_ok=True)


def parse_document(extension: str, content: bytes) -> list[tuple[int | None, str]]:
    if extension == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        return [(number, page.extract_text() or "") for number, page in enumerate(reader.pages, 1)]
    if extension == ".docx":
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs = [
            "".join(node.text or "" for node in paragraph.iter(namespace + "t"))
            for paragraph in root.iter(namespace + "p")
        ]
        return [(None, "\n\n".join(filter(None, paragraphs)))]
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("gb18030")
    return [(None, text)]


def make_chunks(sections: list[tuple[int | None, str]]) -> list[tuple[int | None, str]]:
    chunks: list[tuple[int | None, str]] = []
    for page_number, text in sections:
        current = ""
        for paragraph in filter(None, (part.strip() for part in re.split(r"\n\s*\n", text))):
            if len(paragraph) > MAX_CHUNK_CHARS:
                if current:
                    chunks.append((page_number, current))
                    current = ""
                chunks.extend(
                    (page_number, paragraph[start : start + MAX_CHUNK_CHARS])
                    for start in range(0, len(paragraph), MAX_CHUNK_CHARS)
                )
            elif not current:
                current = paragraph
            elif len(current) + len(paragraph) + 2 <= MAX_CHUNK_CHARS:
                current += "\n\n" + paragraph
            else:
                chunks.append((page_number, current))
                current = paragraph
        if current:
            chunks.append((page_number, current))
    return chunks
