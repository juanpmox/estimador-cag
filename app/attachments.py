"""
Extraccion local del texto de adjuntos (Camino B).

Elegimos extraer el texto en el servicio (pypdf para PDF, python-docx para
Word) en vez de subir el PDF al LLM multimodal (Camino A) porque:

- es independiente del proveedor LLM (no nos acopla a la Files API de
  OpenAI/Anthropic),
- es testeable sin red ni llamadas reales al modelo,
- nos deja el texto en un formato que prepara el chunking de RAG del modulo 3.

Los imports de `pypdf`/`python-docx` son perezosos (dentro de las funciones)
para que la app arranque aunque las librerias no esten instaladas, y el fallo
se traduzca en un error de adjunto claro.
"""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings

# Extensiones que sabemos extraer localmente.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx", ".txt", ".md"})


def _extraer_pdf(data: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _extraer_docx(data: bytes) -> str:
    from io import BytesIO

    import docx

    documento = docx.Document(BytesIO(data))
    return "\n".join(p.text for p in documento.paragraphs)


def extract_text(filename: str, data: bytes, max_chars: int | None = None) -> str:
    """
    Extrae el texto de `data` segun la extension de `filename`.

    Lanza `ValueError` si la extension no esta soportada. Trunca a `max_chars`
    (por defecto `ATTACHMENT_MAX_CHARS`) para no reventar el contexto.
    """
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        soportadas = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(
            f"Tipo de adjunto no soportado '{extension}'. Soportados: {soportadas}"
        )

    if extension == ".pdf":
        texto = _extraer_pdf(data)
    elif extension == ".docx":
        texto = _extraer_docx(data)
    else:  # .txt / .md
        texto = data.decode("utf-8", errors="replace")

    limite = max_chars if max_chars is not None else get_settings().attachment_max_chars
    if limite is not None and limite > 0 and len(texto) > limite:
        texto = texto[:limite] + "\n[... texto truncado ...]"
    return texto.strip()


def build_transcript_with_attachments(
    transcript: str,
    attachments: list[tuple[str, str]],
) -> str:
    """
    Concatena el texto de los adjuntos a la transcripcion con un separador
    explicito por archivo: `--- attachment: <nombre> ---`.

    `attachments` es una lista de pares (nombre_de_archivo, texto_extraido).
    """
    if not attachments:
        return transcript

    bloques = []
    for nombre, texto in attachments:
        bloques.append(f"--- attachment: {nombre} ---\n{texto}")
    return transcript + "\n\n" + "\n\n".join(bloques)
