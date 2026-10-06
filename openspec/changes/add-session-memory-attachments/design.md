# Design

## Context

Ver `proposal.md` para la motivacion. Punto de partida (sesion 04): `POST /api/v1/estimate` recibe un `EstimationRequest` JSON tipado y renderiza `v1/` con `render_estimation_prompt(request, version) -> (system, user)`, que se pasan como dos mensajes a `generate_estimation(system, user)`. El contrato vive en `app/schemas.py` y la seleccion de proveedor en `app/config.py`. No hay estado entre peticiones.

Restricciones no negociables del repo (ver `openspec/config.yaml`): los prompts viven siempre en templates Jinja2 versionados (`app/prompts/estimation/<version>/`), una version nueva es una copia de la carpeta, el loader/endpoint no se tocan para elegir version, y los tests no llaman a APIs externas de LLM.

## Goals / Non-Goals

**Goals:**

- Estado de sesion en memoria del proceso con dos estructuras separadas: historial (ventana deslizante) y `project_metadata` (hechos del proyecto).
- Endpoints de sesion y de estimacion multi-turno con adjuntos, sin romper el endpoint v1 existente.
- Inyeccion del `project_metadata` en el system prompt via una version nueva de prompt (`v2/`).

**Non-Goals:**

- Persistencia entre reinicios, resumen acumulativo/anclas, tier dinamico, LLM extractor, Camino A (multimodal), Actor-Critic-Boss (ver "Fuera de alcance" del proposal).

## Decisions

### D1. Adjuntos: Camino B (extraccion local) en vez del Camino A (multimodal)

Elegimos extraccion local con `pypdf` (PDF) y `python-docx` (Word).

- **Razon**: independiente del proveedor LLM (no acopla el servicio a la Files API de OpenAI/Anthropic), testeable sin red ni llamadas reales al modelo, y deja el texto en un formato que prepara el chunking de RAG del modulo 3.
- **Alternativa descartada**: Camino A (subir el PDF al LLM multimodal) es mas simple y con menos codigo, pero acopla el servicio al proveedor, complica los tests (no se puede validar sin llamar al modelo) y no controlamos el contenido inyectado.

### D2. `project_metadata`: heuristica simple en vez de LLM extractor

Extraemos los hechos con reglas/regex sobre la transcripcion y la respuesta del turno.

- **Razon**: coste cero por turno, latencia despreciable, determinista y testeable sin LLM (respeta la regla de "los tests no llaman a APIs"). En esta fase los campos son pocos (nombre, equipo, tecnologias, alcance) y las frases son acotadas.
- **Alternativa descartada**: LLM extractor (segunda llamada por turno) es mas robusto con lenguaje libre pero añade una llamada al proveedor por turno y hace los tests dependientes de un modelo.

### D3. Ventana deslizante con `deque(maxlen=MAX_TURNS)`

`ConversationHistory` guarda turnos (par user+assistant) en un `collections.deque` con `maxlen = MAX_TURNS`. Al superar el limite, `deque` descarta automaticamente el par mas antiguo. El system prompt no vive en el historial: se regenera desde el `project_metadata` en cada llamada y se antepone en `to_messages_list()`.

- **Razon**: la ventana deslizante es la estrategia por defecto razonable (memoria acotada, sin coste de resumen) y `deque` implementa el descarte FIFO de forma nativa. Mantener el system prompt fuera del historial garantiza que nunca se descarta y que siempre refleja el `project_metadata` actual.
- **Alternativa descartada**: resumir turnos antiguos (estrategia de resumen/anclas) es lo que se construye en el directo.

### D4. Estado en un diccionario en memoria del proceso

`SessionStore` es un dict `session_id -> Session` como singleton de modulo. Se documenta la volatilidad (se pierde al reiniciar el servicio) como decision consciente de esta fase: sin BBDD ni Redis. Si en el futuro hace falta persistencia, la interfaz `SessionStore` (create/get/reset) es el punto de sustitucion.

### D5. Prompts: nueva version `v2/`, no modificar `v1/`

`v2/system.j2` añade el bloque `<project_metadata>` (vacio si no hay hechos) y el encuadre conversacional; `v2/user.j2` envuelve la transcripcion (que ya incluye los adjuntos concatenados). Se copia `examples.j2`. El loader gana `render_session_prompt(project_metadata, transcript, version="v2")`; `v1/` y `render_estimation_prompt` quedan intactos, igual que el endpoint v1.

- **Razon**: cumple la convencion "una version nueva es una copia de la carpeta" y permite comparar/rollback. El endpoint conversacional usa `v2` por defecto pero acepta `?prompt_version=`.

### D6. Llamada multi-mensaje al LLM

El historial obliga a enviar N mensajes, no solo `(system, user)`. Se añade `generate_estimation_messages(messages)` a `llm_service.py`, que separa el mensaje `system` para Anthropic y lo pasa como `system=` y el resto como `messages=`. `generate_estimation(system, user)` puede delegar en esta funcion.

### D7. Compatibilidad de cliente HTTP en tests

El entorno puede exponer `httpx` o `httpx2`; `tests/conftest.py` normaliza el import y usa `httpx2.alias_httpx()` cuando aplica. Los tests async corren con `pytest.mark.anyio` (plugin ya presente via `anyio`), evitando añadir `pytest-asyncio`.

## Risks / Trade-offs

- [La heuristica no detecta hechos con lenguaje libre] → Mitigacion: se documenta como limitacion; el directo reemplaza por extractor con LLM. Los campos detectados se mergean (no se pierden hechos previos).
- [La memoria se pierde al reiniciar el servicio] → Mitigacion: aceptado en esta fase; `SessionStore` es el punto de sustitucion por algo persistente.
- [Acoplamiento del render a `StrictUndefined`] → Mitigacion: `render_session_prompt` pasa un dict con todas las claves de `ProjectMetadata` (aunque sean `None`) para que el template no falle.
- [Alternancia de roles exigida por Anthropic] → Mitigacion: la ventana deslizante conserva pares completos, de modo que la secuencia siempre empieza por `user` y alterna.
- [`pypdf`/`python-docx` no instalados en todos los entornos] → Mitigacion: imports perezosos dentro de las funciones de extraccion; el fallo se traduce en un `400` claro.

## Migration Plan

- No hay migracion de datos: el estado es efimero y el endpoint v1 no cambia.
- Rollback: al ser endpoints y modulos nuevos (mas una version de prompt nueva), revertir el commit deja el sistema en el estado de la sesion 04.

