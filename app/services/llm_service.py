"""
Wrapper de proveedor de LLM: dado un system y un user prompt ya renderizados
(ver app/prompts/loader.py), llama al proveedor configurado (OpenAI,
Anthropic u OpenRouter) y devuelve el texto generado.

Esta capa ya NO construye el prompt — esa responsabilidad vive por completo
en los templates Jinja2 versionados de app/prompts/estimation/. Aqui solo
importa a que proveedor y modelo se llama, con que mensajes.
"""

from dataclasses import dataclass
from typing import Iterator
import time

from app.config import Settings, get_settings


@dataclass
class EstimationResult:
    estimation: str
    model: str
    provider: str


def _call_openai(system: str, user: str, settings: Settings) -> EstimationResult:
    from openai import OpenAI

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY no esta configurada en el .env")

    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
    )

    estimation_text = response.choices[0].message.content or ""

    return EstimationResult(
        estimation=estimation_text.strip(),
        model=settings.openai_model,
        provider="openai",
    )


def _call_openrouter(system: str, user: str, settings: Settings) -> EstimationResult:
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

    extra_headers = {}
    if settings.openrouter_site_url:
        extra_headers["HTTP-Referer"] = settings.openrouter_site_url
    if settings.openrouter_site_name:
        extra_headers["X-Title"] = settings.openrouter_site_name

    response = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
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


def _call_anthropic(system: str, user: str, settings: Settings) -> EstimationResult:
    from anthropic import Anthropic

    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY no esta configurada en el .env")

    client = Anthropic(api_key=settings.anthropic_api_key)

    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1500,
        system=system,
        messages=[
            {"role": "user", "content": user},
        ],
    )

    estimation_text = "".join(
        block.text for block in response.content if block.type == "text"
    )

    return EstimationResult(
        estimation=estimation_text.strip(),
        model=settings.anthropic_model,
        provider="anthropic",
    )


def generate_estimation(system: str, user: str) -> EstimationResult:
    """
    Llama al proveedor configurado en LLM_PROVIDER con dos mensajes
    separados (system, user) y devuelve la estimacion generada.

    `system` y `user` deben venir ya renderizados por
    `app.prompts.loader.render_estimation_prompt` — este modulo no sabe
    nada de templates ni de la estructura del prompt.
    """
    settings = get_settings()

    if settings.llm_provider == "openai":
        return _call_openai(system, user, settings)
    elif settings.llm_provider == "anthropic":
        return _call_anthropic(system, user, settings)
    elif settings.llm_provider == "openrouter":
        return _call_openrouter(system, user, settings)
    else:
        raise ValueError(f"Proveedor LLM no soportado: {settings.llm_provider}")


# ---------------------------------------------------------------------------
# Streaming: se mantiene disponible para cuando se reintroduzca en el cliente
# (quedo fuera del alcance de este refactor a formulario tipado, ver README).
# Cada funcion es un generador que cede (yield) fragmentos de texto a medida
# que el modelo los produce, y escribe metricas de la llamada (modelo,
# tokens, tiempo de respuesta) en el dict `stats` que recibe como parametro.
# ---------------------------------------------------------------------------


def _stream_openai_compatible(
    system: str,
    user: str,
    stats: dict,
    *,
    api_key: str,
    model: str,
    provider_name: str,
    base_url: str | None = None,
    extra_headers: dict | None = None,
) -> Iterator[str]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)

    start = time.perf_counter()
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
        stream=True,
        stream_options={"include_usage": True},
        extra_headers=extra_headers or None,
    )

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
        usage = getattr(chunk, "usage", None)
        if usage:
            stats["input_tokens"] = usage.prompt_tokens
            stats["output_tokens"] = usage.completion_tokens

    stats["model"] = model
    stats["provider"] = provider_name
    stats["elapsed_seconds"] = round(time.perf_counter() - start, 2)


def _stream_openai(system: str, user: str, settings: Settings, stats: dict) -> Iterator[str]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY no esta configurada en el .env")
    yield from _stream_openai_compatible(
        system,
        user,
        stats,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        provider_name="openai",
    )


def _stream_openrouter(system: str, user: str, settings: Settings, stats: dict) -> Iterator[str]:
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY no esta configurada en el .env")

    extra_headers = {}
    if settings.openrouter_site_url:
        extra_headers["HTTP-Referer"] = settings.openrouter_site_url
    if settings.openrouter_site_name:
        extra_headers["X-Title"] = settings.openrouter_site_name

    yield from _stream_openai_compatible(
        system,
        user,
        stats,
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        provider_name="openrouter",
        base_url=settings.openrouter_base_url,
        extra_headers=extra_headers,
    )


def _stream_anthropic(system: str, user: str, settings: Settings, stats: dict) -> Iterator[str]:
    from anthropic import Anthropic

    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY no esta configurada en el .env")

    client = Anthropic(api_key=settings.anthropic_api_key)

    start = time.perf_counter()
    with client.messages.stream(
        model=settings.anthropic_model,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            yield text
        final_message = stream.get_final_message()
        stats["input_tokens"] = final_message.usage.input_tokens
        stats["output_tokens"] = final_message.usage.output_tokens

    stats["model"] = settings.anthropic_model
    stats["provider"] = "anthropic"
    stats["elapsed_seconds"] = round(time.perf_counter() - start, 2)


def stream_estimation(system: str, user: str, stats: dict) -> Iterator[str]:
    """
    Version en streaming de `generate_estimation`. Cede fragmentos de texto
    a medida que el LLM los genera y, al terminar, deja las metricas de la
    llamada escritas en el dict `stats` pasado por el caller.
    """
    settings = get_settings()

    if settings.llm_provider == "openai":
        yield from _stream_openai(system, user, settings, stats)
    elif settings.llm_provider == "anthropic":
        yield from _stream_anthropic(system, user, settings, stats)
    elif settings.llm_provider == "openrouter":
        yield from _stream_openrouter(system, user, settings, stats)
    else:
        raise ValueError(f"Proveedor LLM no soportado: {settings.llm_provider}")
