from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .services import chat_with_jarvis
from .models import Sesion, Mensaje

@api_view(['POST'])
def chat(request):
    message = request.data.get('message', '')
    session_id = request.data.get('session_id', None)

    if not message:
        return Response({'error': 'Mensaje vacío'}, status=status.HTTP_400_BAD_REQUEST)

    # Obtener o crear sesión
    if session_id:
        try:
            sesion = Sesion.objects.get(id=session_id)
        except Sesion.DoesNotExist:
            sesion = Sesion.objects.create()
    else:
        sesion = Sesion.objects.create()

    # Cargar historial de la DB
    mensajes_db = sesion.mensajes.order_by('creado_en')
    history = [{'role': m.rol, 'content': m.contenido} for m in mensajes_db]

    # Llamar a Jarvis
    result = chat_with_jarvis(message, history)

    # Guardar en DB
    Mensaje.objects.create(sesion=sesion, rol='user', contenido=message)
    Mensaje.objects.create(sesion=sesion, rol='assistant', contenido=result['response'])

    return Response({
        'response': result['response'],
        'session_id': sesion.id,
    })


@api_view(['GET'])
def historial(request, session_id):
    try:
        sesion = Sesion.objects.get(id=session_id)
    except Sesion.DoesNotExist:
        return Response({'error': 'Sesión no encontrada'}, status=404)

    mensajes = sesion.mensajes.order_by('creado_en')
    data = [{'rol': m.rol, 'contenido': m.contenido, 'fecha': m.creado_en} for m in mensajes]
    return Response({'session_id': session_id, 'mensajes': data})


@api_view(['GET'])
def sesiones(request):
    todas = Sesion.objects.order_by('-creada_en')[:10]
    data = [{'id': s.id, 'creada_en': s.creada_en} for s in todas]
    return Response(data)