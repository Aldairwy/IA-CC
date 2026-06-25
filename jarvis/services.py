import os
import logging
from functools import lru_cache
from datetime import datetime, timedelta
from tavily import TavilyClient
import requests 
import concurrent.futures
from .ai import get_provider

logger = logging.getLogger(__name__)

ELEVENLABS_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVENLABS_MODEL = "eleven_multilingual_v2"


@lru_cache(maxsize=1)
def _get_tavily_client() -> TavilyClient:
    """Devuelve el cliente de Tavily, creándolo solo la primera vez.

    ¿Por qué perezoso (lazy)? Antes el cliente se creaba al IMPORTAR este
    módulo. Eso significaba que un problema con la clave de Tavily podía
    tumbar el arranque entero del servidor, incluido el chat, que no usa
    Tavily para nada. Ahora el cliente se construye la primera vez que se
    BUSCA en la web. Si falla, falla solo la búsqueda, no todo Jarvis.

    @lru_cache(maxsize=1) guarda el resultado: se crea una vez y se reutiliza
    en las siguientes llamadas. Es el mismo patrón que usamos en ai/factory.py.
    """
    return TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

def generar_titulo(message: str, response: str) -> str:
    """Genera un título corto para la conversación usando el proveedor de IA activo.

    Antes esto dependía de un cliente Groq global (_groq_client) que dejó de
    existir tras mover la IA a la capa jarvis/ai/. Ahora delegamos en
    get_provider(), igual que el chat: un solo punto de cambio de proveedor.

    Si el proveedor falla, devolvemos un fallback razonable (las primeras
    palabras del mensaje). Pero a diferencia de antes, REGISTRAMOS el error
    en vez de tragárnoslo: un fallo silencioso es un bug que nunca verás.
    """
    system = (
        "Eres un generador de títulos. Devuelve un título corto, máximo 5 "
        "palabras, que resuma la conversación. Sin comillas ni explicación, "
        "solo el título."
    )
    contenido = f"Usuario: {message}\nJarvis: {response[:200]}"
    messages = [{"role": "user", "content": contenido}]

    try:
        provider = get_provider()
        titulo = provider.chat(system=system, messages=messages)
        titulo = titulo.strip().strip('"').strip()
        # Si el modelo devolvió vacío o algo absurdamente largo, usamos fallback.
        if not titulo or len(titulo) > 60:
            return message[:50]
        return titulo
    except Exception as e:
        logger.warning("No se pudo generar título con IA, usando fallback: %s", e)
        return message[:50]


def detectar_fecha_query(message: str) -> str:
    hoy = datetime.now()
    message_lower = message.lower()
    if 'hoy' in message_lower:
        return hoy.strftime("%d/%m/%Y")
    elif 'ayer' in message_lower:
        return (hoy - timedelta(days=1)).strftime("%d/%m/%Y")
    elif 'esta semana' in message_lower:
        return hoy.strftime("semana del %d/%m/%Y")
    elif 'este mes' in message_lower:
        return hoy.strftime("%B %Y")
    return ''


def necesita_busqueda(message: str) -> bool:
    keywords = [
        'busca', 'buscar', 'hoy', 'ahora', 'último', 'última', 'actualmente',
        'ayer', 'esta semana', 'este mes', 'reciente', 'últimas noticias',
        'qué es', 'quién es', 'cuánto', 'precio', 'noticias', 'clima',
        'temperatura', 'dólar', 'euro', 'resultado',
        'partido', 'marcador', 'gol', 'juego', 'liga', 'copa', 'torneo',
        'selección', 'fútbol', 'basketball', 'tenis', 'ganó', 'perdió', 'empató',
        'película', 'serie', 'estreno', 'canción', 'álbum', 'artista',
        'lanzó', 'lanzamiento', 'nuevo', 'nueva', 'versión', 'actualización',
        'colombia', 'bogotá', 'medellín', 'cali', 'peso colombiano',
    ]
    return any(k in message.lower() for k in keywords)


def buscar_web(query: str, fecha_str: str = '') -> str:
    try:
        client = _get_tavily_client()
        query_enriquecido = f"{query} {fecha_str}".strip() if fecha_str else query
        es_profunda = any(k in query.lower() for k in ['noticias', 'último', 'última', 'ayer', 'hoy'])
        result = client.search(
            query=query_enriquecido,
            max_results=3,
            search_depth="advanced" if es_profunda else "basic",
        )
        if not result.get('results'):
            return "No encontré resultados recientes."
        snippets = []
        for r in result['results']:
            titulo = r.get('title', '')
            contenido = r.get('content', '')[:400]
            url = r.get('url', '')
            snippets.append(f"**{titulo}**\n{contenido}\nFuente: {url}")
        return '\n\n---\n\n'.join(snippets)
    except Exception as e:
        return f"Error en búsqueda web: {str(e)}"


 
def _build_system_y_mensajes(message: str, history: list, buscar: bool = True) -> tuple:
    """Devuelve (system_prompt, messages_neutrales).
 
    'messages' = historial + el mensaje nuevo del usuario.
    El system va POR SEPARADO (ya no dentro de la lista).
    """
    ahora = datetime.now()
    fecha_larga = ahora.strftime("%A %d de %B de %Y")
    hora_actual = ahora.strftime("%H:%M")
    fecha_str = detectar_fecha_query(message)
 
    contexto_web = ''
    if buscar and necesita_busqueda(message):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(buscar_web, message, fecha_str)
            try:
                contexto_web = future.result(timeout=8)  # subido de 3s a 8s
            except concurrent.futures.TimeoutError:
                contexto_web = ''
 
    system = f"""Eres J.A.R.V.I.S., un asistente de inteligencia artificial avanzado.
Respondes de forma concisa, profesional y levemente formal.
Llamas al usuario "señor" por defecto.
Eres directo y eficiente. Nunca rechazas una petición sin ofrecer alternativa.
Fecha actual: {fecha_larga}. Hora actual: {hora_actual}.
NUNCA inventes fechas o datos. Menciona la fuente cuando uses internet.
Si la información puede estar desactualizada, indícalo con honestidad.
{("INFORMACIÓN ACTUALIZADA DE INTERNET:\n" + contexto_web) if contexto_web else ""}"""
 
    messages = history + [{"role": "user", "content": message}]
    return system, messages
 
 
def chat_with_jarvis(message: str, history: list) -> dict:
    """Respuesta completa — delega en el proveedor activo (Claude o Groq)."""
    system, messages = _build_system_y_mensajes(message, history)
    provider = get_provider()
    reply = provider.chat(system=system, messages=messages)
    return {
        "response": reply,
        "history": history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ],
    }
 
 
def chat_with_jarvis_streaming(message: str, history: list):
    """Respuesta en streaming — devuelve un generador de TROZOS DE TEXTO.
 
    OJO: antes esto devolvía objetos 'chunk' de Groq. Ahora devuelve
    strings simples. Por eso la VISTA también cambia (ver views.py).
    """
    system, messages = _build_system_y_mensajes(message, history)
    provider = get_provider()
    return provider.chat_stream(system=system, messages=messages)
 

 
class TTSError(Exception):
    """Error propio del servicio de voz.
 
    ¿Por qué una excepción personalizada? Para que la vista pueda
    distinguir 'falló el TTS' de cualquier otro error genérico y
    responder con el código HTTP correcto. Es el principio de
    'fail loud': fallar de forma explícita y nombrada, no con un
    error genérico que no dice nada.
    """
    pass
 
 
def sintetizar_voz(texto: str, voice_id: str = ELEVENLABS_VOICE_ID) -> bytes:
    """Convierte texto en audio usando ElevenLabs y devuelve los bytes MP3.
 
    La API key se lee del ENTORNO DEL SERVIDOR. Nunca llega al cliente.
    Esa es toda la razón de existir de esta función.
 
    Devuelve: bytes del audio (MP3).
    Lanza: TTSError si falta la clave o si ElevenLabs falla.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        # Fail loud: si no hay clave, lo decimos claramente en los logs
        # del servidor en vez de mandar una petición rota a ElevenLabs.
        raise TTSError("ELEVENLABS_API_KEY no está configurada en el servidor.")
 
    if not texto or not texto.strip():
        raise TTSError("Texto vacío para sintetizar.")
 
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    try:
        respuesta = requests.post(
            url,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": texto,
                "model_id": ELEVENLABS_MODEL,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.3,
                    "use_speaker_boost": True,
                },
            },
            timeout=30,  # nunca dejes una petición de red sin timeout
        )
    except requests.RequestException as e:
        # Errores de red (DNS, conexión, timeout). Los envolvemos en
        # NUESTRA excepción para que la vista no tenga que conocer 'requests'.
        raise TTSError(f"No se pudo contactar a ElevenLabs: {e}") from e
 
    if respuesta.status_code != 200:
        # ElevenLabs respondió pero con error (clave inválida, sin cuota...).
        raise TTSError(
            f"ElevenLabs devolvió {respuesta.status_code}: {respuesta.text[:200]}"
        )
 
    return respuesta.content