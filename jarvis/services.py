import os
from datetime import datetime, timedelta
from groq import Groq
from tavily import TavilyClient

_groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
_tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

def generar_titulo(message: str, response: str) -> str:
    try:
        client = _groq_client
        prompt = f"""Genera un título corto (máximo 5 palabras) para esta conversación.
Solo devuelve el título, sin comillas ni explicación.
Usuario: {message}
Jarvis: {response[:200]}"""
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
        )
        return res.choices[0].message.content.strip()
    except:
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
        client = _tavily_client
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


def _build_messages(message: str, history: list, buscar: bool = True) -> tuple:
    ahora = datetime.now()
    fecha_larga = ahora.strftime("%A %d de %B de %Y")
    hora_actual = ahora.strftime("%H:%M")
    fecha_str = detectar_fecha_query(message)

    contexto_web = ''
    if buscar and necesita_busqueda(message):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(buscar_web, message, fecha_str)
            try:
                contexto_web = future.result(timeout=3)
            except concurrent.futures.TimeoutError:
                contexto_web = ''

    system = f"""
Eres J.A.R.V.I.S., un asistente de inteligencia artificial avanzado.
Respondes de forma concisa, profesional y levemente formal.
Llamas al usuario "señor" por defecto.
Eres directo y eficiente. Nunca rechazas una petición sin ofrecer alternativa.
Fecha actual: {fecha_larga}. Hora actual: {hora_actual}.
NUNCA inventes fechas o datos. Menciona la fuente cuando uses internet.
Si la información puede estar desactualizada, indícalo con honestidad.
{"INFORMACIÓN ACTUALIZADA DE INTERNET:\\n" + contexto_web if contexto_web else ""}
"""
    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": message}]
    return messages, contexto_web


def chat_with_jarvis(message: str, history: list) -> dict:
    """Respuesta completa — sin streaming."""
    client = _groq_client
    messages, _ = _build_messages(message, history)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1024,
    )
    reply = response.choices[0].message.content
    return {
        "response": reply,
        "history": history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply}
        ]
    }


def chat_with_jarvis_streaming(message: str, history: list):
    """Respuesta en streaming — devuelve un generador de chunks."""
    client = _groq_client
    messages, _ = _build_messages(message, history)

    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1024,
        stream=True,  #  streaming real
    )
    return stream