from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.chat, name='jarvis-chat'),
    path('historial/<int:session_id>/', views.historial, name='jarvis-historial'),
    path('sesiones/', views.sesiones, name='jarvis-sesiones'),
]