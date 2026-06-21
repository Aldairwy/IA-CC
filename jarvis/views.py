from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .services import chat_with_jarvis, generar_titulo, chat_with_jarvis_streaming
from .models import Sesion, Mensaje
import threading
from django.http import StreamingHttpResponse
import json
import concurrent.futures 

def _generar_titulo_async(sesion_id: int, message: str, response: str):
    """Genera el título en segundo plano sin bloquear la respuesta."""
    try:
        sesion = Sesion.objects.get(id=sesion_id)
        sesion.titulo = generar_titulo(message, response)
        sesion.save()
    except Exception:
        pass


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
    """Endpoint nuevo — respuesta en streaming por frases."""
    import json
    data = json.loads(request.body)
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

        for chunk in chat_with_jarvis_streaming(message, history):
            delta = chunk.choices[0].delta.content or ''
            if delta:
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