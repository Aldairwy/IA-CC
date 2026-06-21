"""
jarvis/ai/base.py

Define el CONTRATO que todo proveedor de IA debe cumplir.

¿Por qué una clase abstracta? Porque queremos que 'services.py' hable
con "un proveedor de IA" sin saber si por debajo es Claude o Groq.
Esta clase es la "forma" común. Claude y Groq la rellenan cada uno
a su manera, pero el resto del código solo conoce ESTA interfaz.

Concepto: 'Abstract Base Class' (ABC). Una clase que NO se usa
directamente; solo define qué métodos deben existir. Si una subclase
olvida implementar uno, Python da error al instanciarla. Eso convierte
un error silencioso en un error ruidoso y temprano (fail loud).
"""
from abc import ABC, abstractmethod
from typing import Iterator


class AIProvider(ABC):
    """Interfaz común para cualquier proveedor de modelos de lenguaje.

    Trabajamos con un formato NEUTRAL de mensajes:
        [{"role": "user"|"assistant", "content": "texto"}, ...]
    El 'system' va aparte (parámetro propio), porque Claude lo exige así
    y Groq lo tolera. Unificamos por el más estricto: buena práctica.
    """

    @abstractmethod
    def chat(self, system: str, messages: list, tools: list | None = None) -> str:
        """Respuesta completa (sin streaming). Devuelve solo el texto.

        - system:   el system prompt, como string aparte.
        - messages: historial en formato neutral (sin el system dentro).
        - tools:    definición de herramientas para el agente. Hoy None;
                    el parámetro existe ya para no reescribir mañana.
        """
        raise NotImplementedError

    @abstractmethod
    def chat_stream(self, system: str, messages: list, tools: list | None = None) -> Iterator[str]:
        """Respuesta en streaming. Devuelve un generador de TROZOS DE TEXTO.

        Importante: cada proveedor emite trozos con una forma distinta.
        La responsabilidad de esta capa es ESCONDER esa diferencia y
        entregar siempre strings simples ('hola', ' mundo', ...).
        Así 'views.py' no necesita saber el formato de Claude ni de Groq.
        """
        raise NotImplementedError