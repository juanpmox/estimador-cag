"""
Servicio encargado de construir el prompt (arquitectura CAG) y llamar al LLM
configurado (OpenAI o Anthropic) para generar una estimacion de software.
"""

from dataclasses import dataclass
from typing import Iterator
import time

from app.config import Settings, get_settings
from app.context.examples import get_examples_as_text

SYSTEM_PROMPT_TEMPLATE = """Eres un estimador de software experto con mas de 15 anios de experiencia \
liderando equipos de desarrollo. Tu tarea es generar estimaciones de esfuerzo, \
costes y duracion a partir de la transcripcion de una reunion con un cliente.

Debes basarte en el estilo, nivel de detalle y criterio de los siguientes \
ejemplos de estimaciones previas realizadas por el equipo. Usalos como \
referencia de formato y de rangos de horas razonables, pero adapta el \
contenido a la nueva transcripcion:

{examples}

Instrucciones:
- Responde siempre en el mismo formato que los ejemplos (titulo, desglose de \
tareas con horas, total estimado, equipo recomendado y duracion estimada).
- Basa el desglose de tareas en lo que efectivamente se menciona en la \
transcripcion de la reunion.
- Si falta informacion relevante, senala los supuestos que estas asumiendo.
- Se conciso y profesional. No incluyas explicaciones fuera del formato de \
estimacion.
"""


@dataclass
class EstimationResult:
    estimation: str
    model: str
    provider: str


def build_system_prompt() -> str:
    """
    Construye el system prompt CAG (rol del modelo + ejemplos estaticos).
    Es publica porque tanto el endpoint REST como la interfaz de Streamlit
    la usan (esta ultima para mostrarla en el panel lateral de contexto).
    """
    return SYSTEM_PROMPT_TEMPLATE.format(examples=get_examples_as_text())


def _call_openai(transcription: str, settings: Settings) -> EstimationResult:
    from openai import OpenAI

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY no esta configurada en el .env")

    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": transcription},
        ],
        temperature=0.4,
    )

    estimation_text = response.choices[0].message.content or ""

    return EstimationResult(
        estimation=estimation_text.strip(),
        model=settings.openai_model,
        provider="openai",
    )


def _call_openrouter(transcription: str, settings: Settings) -> EstimationResult:
    # OpenRouter expone una API compatible con la de OpenAI, asi que
    # reutilizamos el SDK de OpenAI apuntando a otro base_url. Esto permite
    # acceder a modelos de Anthropic, Google, Meta, etc. con una sola key.
    from openai import OpenAI

    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY no esta configurada en el .env")

    client = OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )

    # Headers opcionales recomendados por OpenRouter para identificar la app
    # en su dashboard de rankings/analytics. No son obligatorios.
    extra_headers = {}
    if settings.openrouter_site_url:
        extra_headers["HTTP-Referer"] = settings.openrouter_site_url
    if settings.openrouter_site_name:
        extra_headers["X-Title"] = settings.openrouter_site_name

    response = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": transcription},
        ],
        temperature=0.4,
        extra_headers=extra_headers or None,
    )

    estimation_text = response.choices[0].message.content or ""

    return EstimationResult(
        estimation=estimation_text.strip(),
        model=settings.openrouter_model,
        provider="openrouter",
    )


def _call_anthropic(transcription: str, settings: Settings) -> EstimationResult:
    from anthropic import Anthropic

    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY no esta configurada en el .env")

    client = Anthropic(api_key=settings.anthropic_api_key)

    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1500,
        system=build_system_prompt(),
        messages=[
            {"role": "user", "content": transcription},
        ],
    )

    # Concatena todos los bloques de tipo texto de la respuesta.
    estimation_text = "".join(
        block.text for block in response.content if block.type == "text"
    )

    return EstimationResult(
        estimation=estimation_text.strip(),
        model=settings.anthropic_model,
        provider="anthropic",
    )


def generate_estimation(transcription: str) -> EstimationResult:
    """
    Punto de entrada del servicio: construye el prompt CAG (system prompt +
    ejemplos estaticos + transcripcion del usuario) y delega la llamada al
    proveedor configurado en LLM_PROVIDER.
    """
    settings = get_settings()

    if settings.llm_provider == "openai":
        return _call_openai(transcription, settings)
    elif settings.llm_provider == "anthropic":
        return _call_anthropic(transcription, settings)
    elif settings.llm_provider == "openrouter":
        return _call_openrouter(transcription, settings)
    else:
        raise ValueError(f"Proveedor LLM no soportado: {settings.llm_provider}")


# ---------------------------------------------------------------------------
# Streaming: usado por la interfaz de Streamlit (st.write_stream).
#
# Cada funcion es un generador que va cediendo (yield) fragmentos de texto a
# medida que el modelo los produce. Ademas, escriben metricas de la llamada
# (modelo, tokens de entrada/salida, tiempo de respuesta) en el diccionario
# `stats` que recibe como parametro, para que el caller pueda leerlas una vez
# el streaming termina (un generador no puede "return" datos junto al ultimo
# yield de forma comoda, asi que usamos este dict mutable como salida lateral).
# ---------------------------------------------------------------------------


def _stream_openai_compatible(
    transcription: str,
    stats: dict,
    *,
    api_key: str,
    model: str,
    provider_name: str,
    base_url: str | None = None,
    extra_headers: dict | None = None,
) -> Iterator[str]:
    """
    Streaming compartido para OpenAI y OpenRouter (API compatible con la de
    OpenAI). Usa `stream_options={"include_usage": True}` para recibir el
    conteo de tokens en el ultimo chunk del stream.
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)

    start = time.perf_counter()
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": transcription},
        ],
        temperature=0.4,
        stream=True,
        stream_options={"include_usage": True},
        extra_headers=extra_headers or None,
    )

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
        # El chunk final (sin choices) trae el resumen de uso de tokens.
        usage = getattr(chunk, "usage", None)
        if usage:
            stats["input_tokens"] = usage.prompt_tokens
            stats["output_tokens"] = usage.completion_tokens

    stats["model"] = model
    stats["provider"] = provider_name
    stats["elapsed_seconds"] = round(time.perf_counter() - start, 2)


def _stream_openai(transcription: str, settings: Settings, stats: dict) -> Iterator[str]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY no esta configurada en el .env")
    yield from _stream_openai_compatible(
        transcription,
        stats,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        provider_name="openai",
    )


def _stream_openrouter(transcription: str, settings: Settings, stats: dict) -> Iterator[str]:
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY no esta configurada en el .env")

    extra_headers = {}
    if settings.openrouter_site_url:
        extra_headers["HTTP-Referer"] = settings.openrouter_site_url
    if settings.openrouter_site_name:
        extra_headers["X-Title"] = settings.openrouter_site_name

    yield from _stream_openai_compatible(
        transcription,
        stats,
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        provider_name="openrouter",
        base_url=settings.openrouter_base_url,
        extra_headers=extra_headers,
    )


def _stream_anthropic(transcription: str, settings: Settings, stats: dict) -> Iterator[str]:
    from anthropic import Anthropic

    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY no esta configurada en el .env")

    client = Anthropic(api_key=settings.anthropic_api_key)

    start = time.perf_counter()
    with client.messages.stream(
        model=settings.anthropic_model,
        max_tokens=1500,
        system=build_system_prompt(),
        messages=[{"role": "user", "content": transcription}],
    ) as stream:
        for text in stream.text_stream:
            yield text
        final_message = stream.get_final_message()
        stats["input_tokens"] = final_message.usage.input_tokens
        stats["output_tokens"] = final_message.usage.output_tokens

    stats["model"] = settings.anthropic_model
    stats["provider"] = "anthropic"
    stats["elapsed_seconds"] = round(time.perf_counter() - start, 2)


def stream_estimation(transcription: str, stats: dict) -> Iterator[str]:
    """
    Version en streaming de `generate_estimation`, usada por streamlit_app.py.

    Cede fragmentos de texto a medida que el LLM los genera y, al terminar,
    deja las metricas de la llamada (modelo, proveedor, tokens, tiempo de
    respuesta) escritas en el dict `stats` pasado por el caller.
    """
    settings = get_settings()

    if settings.llm_provider == "openai":
        yield from _stream_openai(transcription, settings, stats)
    elif settings.llm_provider == "anthropic":
        yield from _stream_anthropic(transcription, settings, stats)
    elif settings.llm_provider == "openrouter":
        yield from _stream_openrouter(transcription, settings, stats)
    else:
        raise ValueError(f"Proveedor LLM no soportado: {settings.llm_provider}")
