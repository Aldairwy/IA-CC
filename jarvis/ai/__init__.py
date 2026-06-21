# jarvis/ai/__init__.py
# Reexportamos lo que el resto del proyecto necesita, para que puedan
# escribir:  from jarvis.ai import get_provider
from .factory import get_provider
from .base import AIProvider

__all__ = ["get_provider", "AIProvider"]