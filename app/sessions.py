"""
Estado de una sesion conversacional del estimador.

Dos conceptos separados a proposito:

- **Historial conversacional** (`ConversationHistory`): el array de mensajes
  (pares user+assistant) que viaja a la API del LLM en cada llamada. Es un
  detalle de *transporte* y esta acotado por una ventana deslizante.
- **Memoria del proyecto** (`ProjectMetadata`): los hechos que conocemos del
  proyecto en curso (nombre, equipo, tecnologias, alcance). Se preserva entre
  turnos y se inyecta en el system prompt, pero vive *aparte* del historial:
  sobrevive a la ventana deslizante.

El estado vive en memoria del proceso (un diccionario `session_id -> Session`),
sin BBDD ni Redis. Aceptamos esa volatilidad en esta fase: el objetivo es
demostrar el patron (memoria + historial separados) y el estado se pierde al
reiniciar el servicio. Cuando haga falta persistencia, `SessionStore` es el
unico punto a sustituir (su interfaz create/get/clear no cambia).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.config import get_settings
from app.schemas import ProjectMetadata


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ConversationTurn:
    """Un turno conversacional: el mensaje del usuario y la respuesta del modelo."""

    user: str
    assistant: str


@dataclass
class ConversationHistory:
    """
    Historial de mensajes con ventana deslizante.

    Guarda hasta `max_turns` turnos (cada turno es un par user+assistant). Al
    superar el limite, `deque` descarta automaticamente el par mas antiguo, de
    modo que la secuencia conservada siempre empieza por un mensaje `user` y
    alterna roles (requisito de proveedores como Anthropic).

    El system prompt NO vive aqui: es el invariante que se regenera desde el
    `ProjectMetadata` actual en cada llamada y se antepone en
    `to_messages_list()`.
    """

    max_turns: int
    _turns: deque[ConversationTurn] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_turns < 1:
            raise ValueError("max_turns debe ser >= 1")
        self._turns = deque(maxlen=self.max_turns)

    def add_turn(self, user: str, assistant: str) -> None:
        """Añade un turno; si se supera la ventana, descarta el mas antiguo."""
        self._turns.append(ConversationTurn(user=user, assistant=assistant))

    @property
    def turns(self) -> list[ConversationTurn]:
        """Copia de los turnos conservados (del mas antiguo al mas reciente)."""
        return list(self._turns)

    def __len__(self) -> int:
        return len(self._turns)

    def to_messages_list(self, system_prompt: str) -> list[dict]:
        """
        Devuelve el array `messages` listo para la API del LLM: el system
        prompt (ya regenerado por el caller a partir del `ProjectMetadata`
        actual) seguido de los turnos conservados como pares user/assistant.
        """
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        for turn in self._turns:
            messages.append({"role": "user", "content": turn.user})
            messages.append({"role": "assistant", "content": turn.assistant})
        return messages


class Session:
    """
    Una conversacion con identificador: historial + memoria del proyecto.

    El `session_id` es lo que el cliente reenvia en cada peticion para que el
    servicio recupere esta sesion.
    """

    def __init__(self, max_turns: int, session_id: str | None = None) -> None:
        self.session_id: str = session_id or str(uuid4())
        self.history: ConversationHistory = ConversationHistory(max_turns=max_turns)
        self.metadata: ProjectMetadata = ProjectMetadata()
        self.created_at: datetime = _now()
        self.updated_at: datetime = _now()

    def to_messages_list(self, version: str = "v2") -> list[dict]:
        """
        Array `messages` para el LLM con el system prompt regenerado desde el
        `ProjectMetadata` actual (por eso la memoria se refleja en cada turno
        aunque el system prompt no viva en el historial).
        """
        from app.prompts.loader import render_session_system_prompt

        system_prompt = render_session_system_prompt(
            self.metadata.model_dump(), version=version
        )
        return self.history.to_messages_list(system_prompt)

    def touch(self) -> None:
        """Marca la sesion como actualizada (tras procesar un turno)."""
        self.updated_at = _now()


class SessionStore:
    """
    Almacen de sesiones en memoria del proceso (dict indexado por session_id).

    Volatilidad aceptada: el estado se pierde al reiniciar el servicio. Es
    suficiente para esta fase; sustituir por algo persistente (BBDD/Redis) no
    cambia la interfaz create/get/clear.
    """

    def __init__(self, max_turns: int | None = None) -> None:
        self._sessions: dict[str, Session] = {}
        self._max_turns = max_turns

    @property
    def _effective_max_turns(self) -> int:
        if self._max_turns is not None:
            return self._max_turns
        return get_settings().session_max_turns

    def create(self) -> Session:
        """Crea una sesion vacia y la registra."""
        session = Session(max_turns=self._effective_max_turns)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        """Devuelve la sesion o None si no existe."""
        return self._sessions.get(session_id)

    def clear(self) -> None:
        """Elimina todas las sesiones (util en tests)."""
        self._sessions.clear()

    def __len__(self) -> int:
        return len(self._sessions)


# Singleton de proceso. La app importa esta instancia; los tests pueden
# limpiarla con `session_store.clear()`.
session_store = SessionStore()

