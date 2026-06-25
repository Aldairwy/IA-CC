from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .services import (
    chat_with_jarvis, generar_titulo, chat_with_jarvis_streaming,
    sintetizar_voz, TTSError,
)
from .models import Sesion, Mensaje
import threading
import logging
from django.http import StreamingHttpResponse, HttpResponse
import json
import concurrent.futures

logger = logging.getLogger(__name__)


def _generar_titulo_async(sesion_id: int, message: str, response: str):
    """Genera el título en segundo plano sin bloquear la respuesta.

    Corre en un hilo aparte: si algo falla aquí, NO debe afectar a la
    respuesta que el usuario ya recibió. Por eso atrapamos cualquier
    excepción. Pero, a diferencia de antes, la REGISTRAMOS en vez de
    tirarla a la basura con 'pass': un fallo que no se ve es un bug que
    nunca arreglas (justo lo que pasó con el bug de _groq_client).
    """
    try:
        sesion = Sesion.objects.get(id=sesion_id)
        sesion.titulo = generar_titulo(message, response)
        sesion.save()
    except Sesion.DoesNotExist:
        # Caso esperable: la sesión se borró antes de que el hilo corriera.
        # No es un error grave; basta con dejar constancia a nivel informativo.
        logger.info("No se generó título: la sesión %s ya no existe.", sesion_id)
    except Exception:
        # Cualquier otro fallo (la IA del título, la BD, etc.). No tumbamos
        # nada, pero lo registramos CON traza completa para poder depurarlo.
        logger.exception("Fallo inesperado generando título para sesión %s", sesion_id)



@api_view(['POST'])
def tts(request):
    """Proxy de Text-to-Speech.

    El cliente manda SOLO texto. El servidor pone la API key y
    devuelve el audio. La clave nunca toca el navegador.

    Entrada (JSON): { "text": "Hola, señor." }
    Salida OK:      audio MP3 (Content-Type: audio/mpeg)
    Salida error:   JSON { "error": "..." } con código 4xx/5xx
    """
    texto = request.data.get('text', '')

    if not texto.strip():
        return Response({'error': 'Texto vacío'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        audio_bytes = sintetizar_voz(texto)
    except TTSError as e:
        # 502 = Bad Gateway: nosotros estamos bien, pero el servicio
        # de terceros del que dependemos falló. Es el código semánticamente
        # correcto para un proxy cuyo upstream falla.
        return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    # Devolvemos los bytes crudos del audio con el content-type correcto.
    # Usamos HttpResponse (no DRF Response) porque no es JSON, es binario.
    return HttpResponse(audio_bytes, content_type='audio/mpeg')


@api_view(['POST'])
def chat(request):
    """Endpoint original — respuesta completa sin streaming."""
    message = request.data.get('message', '')
    session_id = request.data.get('session_id', None)

    if not message:
        return Response({'error': 'Mensaje vacío'}, status=status.HTTP_400_BAD_REQUEST)

    if session_id:
        try:
            sesion = Sesion.objects.get(id=session_id)
        except Sesion.DoesNotExist:
            sesion = Sesion.objects.create()
    else:
        sesion = Sesion.objects.create()

    mensajes_db = sesion.mensajes.order_by('-creado_en')[:20][::-1]
    history = [{'role': m.rol, 'content': m.contenido} for m in mensajes_db]

    result = chat_with_jarvis(message, history)

    Mensaje.objects.create(sesion=sesion, rol='user', contenido=message)
    Mensaje.objects.create(sesion=sesion, rol='assistant', contenido=result['response'])

    es_primer_mensaje = sesion.mensajes.count() == 2
    if es_primer_mensaje:
        hilo = threading.Thread(
            target=_generar_titulo_async,
            args=(sesion.id, message, result['response']),
            daemon=True
        )
        hilo.start()

    return Response({
        'response': result['response'],
        'session_id': sesion.id,
        'titulo': sesion.titulo,
    })


def chat_stream_view(request):
    """Endpoint de respuesta en streaming (Server-Sent Events).

    Nota de diseño: a diferencia de las otras vistas, esta NO usa @api_view
    de DRF. Es a propósito: DRF está pensado para respuestas completas que se
    serializan de una vez, mientras que el streaming va soltando trozos de
    texto. Por eso aquí leemos el body a mano y devolvemos StreamingHttpResponse.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        # Body vacío o mal formado: respondemos 400 en vez de reventar con
        # un error 500 feo. Fail loud, pero de forma controlada.
        return StreamingHttpResponse(status=400)

    message = data.get('message', '')
    session_id = data.get('session_id', None)

    if not message:
        return StreamingHttpResponse(status=400)

    if session_id:
        try:
            sesion = Sesion.objects.get(id=session_id)
        except Sesion.DoesNotExist:
            sesion = Sesion.objects.create()
    else:
        sesion = Sesion.objects.create()

    mensajes_db = sesion.mensajes.order_by('-creado_en')[:20][::-1]
    history = [{'role': m.rol, 'content': m.contenido} for m in mensajes_db]

    def generar():
        respuesta_completa = []

        for delta in chat_with_jarvis_streaming(message, history):
            respuesta_completa.append(delta)
            yield f"data: {json.dumps({'delta': delta, 'session_id': sesion.id})}\n\n"

        
        texto_final = ''.join(respuesta_completa)
        es_primera_vez = not sesion.mensajes.exists ()
        Mensaje.objects.create(sesion=sesion, rol='user', contenido=message)
        Mensaje.objects.create(sesion=sesion, rol='assistant', contenido=texto_final)

        if es_primera_vez:
            hilo = threading.Thread(
                target=_generar_titulo_async,
                args=(sesion.id, message, texto_final),
                daemon=True
            )
            hilo.start()

        yield f"data: {json.dumps({'done': True, 'session_id': sesion.id, 'titulo': sesion.titulo})}\n\n"

    return StreamingHttpResponse(generar(), content_type='text/event-stream')


@api_view(['GET'])
def sesiones(request):
    todas = Sesion.objects.order_by('-actualizada_en')[:20]
    data = [{'id': s.id, 'titulo': s.titulo, 'fecha': s.actualizada_en} for s in todas]
    return Response(data)


@api_view(['GET'])
def historial(request, session_id):
    try:
        sesion = Sesion.objects.get(id=session_id)
    except Sesion.DoesNotExist:
        return Response({'error': 'Sesión no encontrada'}, status=404)

    mensajes = sesion.mensajes.order_by('creado_en')
    data = [{'rol': m.rol, 'contenido': m.contenido} for m in mensajes]
    return Response({'session_id': session_id, 'titulo': sesion.titulo, 'mensajes': data})


@api_view(['DELETE'])
def eliminar_sesion(request, session_id):
    try:
        sesion = Sesion.objects.get(id=session_id)
        sesion.delete()
        return Response({'ok': True})
    except Sesion.DoesNotExist:
        return Response({'error': 'No encontrada'}, status=404)