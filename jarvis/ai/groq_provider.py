"""
jarvis/ai/groq_provider.py

El mismo contrato, pero con Groq (tu proveedor actual).
Es básicamente tu código de antes, reorganizado para cumplir AIProvider.

Lo conservamos para poder VOLVER a Groq con una variable de entorno
(AI_PROVIDER=groq) si Claude falla o si quieres comparar. Migrar de
forma reversible es más seguro que borrar el código viejo.

OJO a la diferencia de formato respecto a Claude:
- En Groq el 'system' SÍ va dentro de 'messages' como {"role": "system"}.
  Por eso aquí lo RE-INSERTAMOS al principio. La capa de servicios nos
  pasa el system aparte (formato neutral) y cada proveedor lo acomoda
  a su manera. Eso es justamente lo que hace un adaptador.
"""
import os
from typing import Iterator
from groq import Groq

from .base import AIProvider


class GroqProvider(AIProvider):
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY no está configurada en el servidor.")
        self._client = Groq(api_key=api_key)
        self._model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def _armar_messages(self, system: str, messages: list) -> list:
        # Groq (estilo OpenAI) quiere el system como primer mensaje.
        return [{"role": "system", "content": system}] + messages

    def chat(self, system: str, messages: list, tools: list | None = None) -> str:
        full = self._armar_messages(system, messages)
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=full,
                max_tokens=1024,
            )
        except Exception as e:
            raise RuntimeError(f"Error de la API de Groq: {e}") from e
        return resp.choices[0].message.content or ""

    def chat_stream(self, system: str, messages: list, tools: list | None = None) -> Iterator[str]:
        full = self._armar_messages(system, messages)
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=full,
                max_tokens=1024,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    yield delta  # devolvemos el MISMO formato neutral que Claude: texto plano
        except Exception as e:
            raise RuntimeError(f"Error de la API de Groq (streaming): {e}") from e