import os
from datetime import datetime
from groq import Groq
from tavily import TavilyClient

def necesita_busqueda(message: str) -> bool:
    keywords = [# Tiempo
        'busca', 'buscar', 'hoy', 'ahora', 'último', 'última', 'actualmente',
        'ayer', 'esta semana', 'este mes', 'reciente', 'últimas noticias',
        # Info general
        'qué es', 'quién es', 'cuánto', 'precio', 'noticias', 'clima',
        'temperatura', 'dólar', 'euro', 'resultado',
        # Deportes
        'partido', 'marcador', 'gol', 'juego', 'liga', 'copa', 'torneo',
        'selección', 'fútbol', 'basketball', 'tenis', 'ganó', 'perdió', 'empató',
        # Entretenimiento
        'película', 'serie', 'estreno', 'canción', 'álbum', 'artista',
        # Tecnología
        'lanzó', 'lanzamiento', 'nuevo', 'nueva', 'versión', 'actualización',
        # Colombia específico
        'colombia', 'bogotá', 'medellín', 'cali', 'peso colombiano']
    message_lower = message.lower()
    return any(k in message_lower for k in keywords)

def buscar_web(query: str) -> str:
    try:
        client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))
        result = client.search(query=query, max_results=3)
        snippets = [r['content'][:300] for r in result.get('results', [])]
        return '\n\n'.join(snippets)
    except Exception as e:
        return f"No pude obtener resultados web: {str(e)}"

def chat_with_jarvis(message: str, history: list) -> dict:
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))

    fecha = datetime.now().strftime("%d de %B de %Y")

    # Búsqueda web si es necesario
    contexto_web = ''
    if necesita_busqueda(message):
        contexto_web = buscar_web(message)

    system = f"""
Eres J.A.R.V.I.S., un asistente de inteligencia artificial avanzado.
Respondes de forma concisa, profesional y levemente formal.
Llamas al usuario "señor" por defecto.
Eres directo y eficiente. Nunca rechazas una petición sin ofrecer alternativa.
La fecha actual es {fecha}.
{"Información actualizada de internet: " + contexto_web if contexto_web else ""}
"""

    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": message}]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1024,
    )

    reply = response.choices[0].message.content

    updated_history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply}
    ]

    return {
        "response": reply,
        "history": updated_history
    }