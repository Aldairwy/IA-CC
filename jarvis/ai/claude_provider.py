"""
jarvis/ai/claude_provider.py

Implementación del contrato AIProvider usando la API de Claude (Anthropic).

Aquí viven TODAS las particularidades de Claude. Si la API de Anthropic
cambia algún día, este es el ÚNICO archivo que tocas.
"""
import os
from typing import Iterator
from anthropic import Anthropic, APIError

from .base import AIProvider


class ClaudeProvider(AIProvider):
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            # Fail loud: si falta la clave, lo decimos claro al arrancar,
            # no a mitad de una petición del usuario.
            raise RuntimeError("ANTHROPIC_API_KEY no está configurada en el servidor.")
        self._client = Anthropic(api_key=api_key)
        # El modelo se saca a variable de entorno para poder cambiarlo
        # sin tocar código. Por defecto, Sonnet 4.6.
        self._model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    def chat(self, system: str, messages: list, tools: list | None = None) -> str:
        """Respuesta completa.

        DIFERENCIA CLAVE vs Groq:
        - 'system' va como parámetro propio, NO dentro de 'messages'.
        - 'max_tokens' es OBLIGATORIO en Claude.
        - La respuesta es una LISTA de bloques; el texto está en .content[0].text
        """
        try:
            kwargs = {
                "model": self._model,
                "max_tokens": 1024,
                "system": system,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools  # listo para el agente; hoy normalmente vacío

            respuesta = self._client.messages.create(**kwargs)
        except APIError as e:
            # Envolvemos el error del SDK en algo nuestro y legible.
            raise RuntimeError(f"Error de la API de Claude: {e}") from e

        # Extraemos el texto del primer bloque de tipo 'text'.
        # (Cuando haya tool-use, habrá bloques de otro tipo; por eso filtramos.)
        for bloque in respuesta.content:
            if bloque.type == "text":
                return bloque.text
        return ""  # respuesta sin texto (p.ej. solo tool_use); lo manejaremos en la fase agente

    def chat_stream(self, system: str, messages: list, tools: list | None = None) -> Iterator[str]:
        """Respuesta en streaming.

        Usamos el helper .stream() del SDK, que expone .text_stream:
        un generador que ya nos da SOLO los trozos de texto. Eso nos
        ahorra parsear los eventos crudos de Claude a mano.
        """
        try:
            kwargs = {
                "model": self._model,
                "max_tokens": 1024,
                "system": system,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            with self._client.messages.stream(**kwargs) as stream:
                for texto in stream.text_stream:
                    yield texto
        except APIError as e:
            raise RuntimeError(f"Error de la API de Claude (streaming): {e}") from e