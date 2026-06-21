"""
jarvis/ai/factory.py

Decide QUÉ proveedor usar, según la variable de entorno AI_PROVIDER.

Esto es el patrón 'Factory' (fábrica): una función central que
construye el objeto correcto. El resto del código pide
"dame el proveedor" sin saber cuál es. Cambiar de proveedor es
cambiar UNA variable de entorno, sin tocar código.

    AI_PROVIDER=claude   -> ClaudeProvider   (por defecto)
    AI_PROVIDER=groq     -> GroqProvider

Cacheamos la instancia con una variable de módulo para no recrear
el cliente en cada petición (crear el cliente tiene un coste).
"""
import os
from functools import lru_cache

from .base import AIProvider
from .claude_provider import ClaudeProvider
from .groq_provider import GroqProvider


@lru_cache(maxsize=1)
def get_provider() -> AIProvider:
    nombre = os.getenv("AI_PROVIDER", "claude").lower()

    if nombre == "claude":
        return ClaudeProvider()
    if nombre == "groq":
        return GroqProvider()

    # Fail loud: si alguien escribe algo raro en AI_PROVIDER, que se note.
    raise ValueError(
        f"AI_PROVIDER='{nombre}' no es válido. Usa 'claude' o 'groq'."
    )