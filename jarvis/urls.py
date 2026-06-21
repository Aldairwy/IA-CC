from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path('chat/', views.chat, name='jarvis-chat'),
    path('chat/stream/', csrf_exempt(views.chat_stream_view), name='jarvis-stream'),
    path('sesiones/', views.sesiones, name='jarvis-sesiones'),
    path('historial/<int:session_id>/', views.historial, name='jarvis-historial'),
    path('eliminar/<int:session_id>/', views.eliminar_sesion, name='jarvis-eliminar'),
]