"""
Tests de la extraccion local de adjuntos (Camino B): PDF con pypdf y Word con
python-docx. Todo se genera en memoria; no hay red ni LLM.
"""

import io

import docx
import pytest

from app.attachments import build_transcript_with_attachments, extract_text


def _build_docx(text: str) -> bytes:
    documento = docx.Document()
    documento.add_paragraph(text)
    buffer = io.BytesIO()
    documento.save(buffer)
    return buffer.getvalue()


def _build_pdf(text: str) -> bytes:
    """PDF minimo valido con una pagina de texto (sin dependencias externas)."""
    content = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET"
    stream = content.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_pos = len(out)
    size = len(objects) + 1
    out += f"xref\n0 {size}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)


def test_extract_text_from_docx():
    data = _build_docx("Requisito: autenticacion con OAuth2 y PostgreSQL")

    texto = extract_text("requisitos.docx", data)

    assert "OAuth2" in texto
    assert "PostgreSQL" in texto


def test_extract_text_from_pdf():
    data = _build_pdf("Especificacion tecnica: microservicios en Kubernetes")

    texto = extract_text("spec.pdf", data)

    assert "Kubernetes" in texto


def test_extract_text_from_plain_text():
    assert extract_text("notas.txt", "hola mundo".encode()) == "hola mundo"


def test_unsupported_extension_raises_value_error():
    with pytest.raises(ValueError):
        extract_text("imagen.png", b"\x89PNG")


def test_truncates_to_max_chars():
    texto = extract_text("notas.txt", b"a" * 100, max_chars=10)

    assert texto.startswith("a" * 10)
    assert "truncado" in texto


def test_build_transcript_without_attachments_is_verbatim():
    assert build_transcript_with_attachments("solo texto", []) == "solo texto"


def test_build_transcript_includes_separator_per_attachment():
    resultado = build_transcript_with_attachments(
        "transcripcion base",
        [("spec.pdf", "contenido del pdf"), ("notas.docx", "contenido del docx")],
    )

    assert resultado.startswith("transcripcion base")
    assert "--- attachment: spec.pdf ---" in resultado
    assert "contenido del pdf" in resultado
    assert "--- attachment: notas.docx ---" in resultado
    assert "contenido del docx" in resultado
