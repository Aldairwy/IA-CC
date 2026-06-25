"""
Tests de humo para Jarvis.

"Humo" (smoke tests) = pruebas básicas que verifican que lo esencial
no está roto. El nombre viene de electrónica: enchufas el aparato y
miras si sale humo. No prueban CADA detalle, sino que "lo importante
responde y no explota".

Conceptos clave que verás aquí:
- TestCase: la clase base de Django para tests. Cada método que empieza
  por 'test_' es UN test independiente.
- self.assert...(): las afirmaciones. Si no se cumplen, el test falla.
- mock/patch: reemplazar la llamada real a la IA por una falsa, para no
  depender de internet ni de una API key durante los tests.
- Django crea una BASE DE DATOS TEMPORAL para los tests y la borra al
  terminar. Tu db.sqlite3 real NUNCA se toca.
"""
from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Sesion, Mensaje


class ModeloTests(TestCase):
    """Tests de los modelos: la capa más simple, sin IA de por medio.
    Empezamos por aquí porque no necesita mocking: es puro Django + BD."""

    def test_crear_sesion_tiene_titulo_por_defecto(self):
        # Arrange + Act: creamos una sesión sin darle título.
        sesion = Sesion.objects.create()
        # Assert: debe tomar el valor por defecto del modelo.
        self.assertEqual(sesion.titulo, 'Nueva conversación')

    def test_mensaje_pertenece_a_su_sesion(self):
        # Arrange: una sesión.
        sesion = Sesion.objects.create()
        # Act: le añadimos un mensaje.
        Mensaje.objects.create(sesion=sesion, rol='user', contenido='Hola')
        # Assert: el related_name 'mensajes' debe devolver ese mensaje.
        self.assertEqual(sesion.mensajes.count(), 1)
        self.assertEqual(sesion.mensajes.first().contenido, 'Hola')

    def test_borrar_sesion_borra_sus_mensajes(self):
        # Esto verifica el on_delete=CASCADE del ForeignKey.
        # Arrange: sesión con un mensaje.
        sesion = Sesion.objects.create()
        Mensaje.objects.create(sesion=sesion, rol='user', contenido='Hola')
        # Act: borramos la sesión.
        sesion.delete()
        # Assert: no deben quedar mensajes huérfanos.
        self.assertEqual(Mensaje.objects.count(), 0)


class ChatEndpointTests(TestCase):
    """Tests del endpoint /api/chat/. Aquí SÍ necesitamos mocking,
    porque chat() llama a la IA por dentro."""

    def setUp(self):
        # setUp() corre ANTES de cada test de esta clase. Sirve para
        # preparar cosas comunes y no repetirlas. Aquí: un cliente HTTP
        # de pruebas que sabe hablar con la API de DRF.
        self.client = APIClient()

    def test_chat_sin_mensaje_devuelve_400(self):
        # No hace falta mock: el endpoint debe rechazar ANTES de llamar
        # a la IA si el mensaje viene vacío.
        # Act: POST sin 'message'.
        respuesta = self.client.post('/api/chat/', {}, format='json')
        # Assert: error 400 (Bad Request).
        self.assertEqual(respuesta.status_code, 400)

    @patch('jarvis.views.chat_with_jarvis')
    def test_chat_con_mensaje_responde_y_guarda(self, mock_chat):
        # @patch reemplaza chat_with_jarvis EN views.py por un falso.
        # OJO al detalle clave: parcheamos 'jarvis.views.chat_with_jarvis',
        # NO 'jarvis.services.chat_with_jarvis'. Hay que parchear donde se
        # USA, no donde se define. Es el error #1 de quien empieza con mocks.
        #
        # Le decimos al falso qué devolver cuando lo llamen:
        mock_chat.return_value = {'response': 'Hola, señor.'}

        # Act: mandamos un mensaje real.
        respuesta = self.client.post(
            '/api/chat/', {'message': 'Hola'}, format='json'
        )

        # Assert 1: responde 200 OK.
        self.assertEqual(respuesta.status_code, 200)
        # Assert 2: devuelve el texto que dio nuestro falso.
        self.assertEqual(respuesta.data['response'], 'Hola, señor.')
        # Assert 3 (el importante): guardó 2 mensajes en BD (user + assistant).
        self.assertEqual(Mensaje.objects.count(), 2)
        # Assert 4: creó una sesión.
        self.assertEqual(Sesion.objects.count(), 1)


class HistorialTruncadoTests(TestCase):
    """Verifica una regla de negocio concreta: el historial que se manda
    a la IA se limita a los últimos 20 mensajes. Si alguien cambia ese
    número sin querer, este test lo caza."""

    @patch('jarvis.views.chat_with_jarvis')
    def test_historial_se_limita_a_20(self, mock_chat):
        mock_chat.return_value = {'response': 'ok'}
        # Arrange: una sesión con 25 mensajes viejos.
        sesion = Sesion.objects.create()
        for i in range(25):
            Mensaje.objects.create(sesion=sesion, rol='user', contenido=f'msg {i}')

        # Act: mandamos un mensaje nuevo a esa sesión.
        client = APIClient()
        client.post(
            '/api/chat/',
            {'message': 'nuevo', 'session_id': sesion.id},
            format='json',
        )

        # Assert: chat_with_jarvis fue llamado con un history de máximo 20.
        # mock_chat.call_args captura con qué argumentos se llamó al falso.
        args, kwargs = mock_chat.call_args
        history_enviado = args[1]  # segundo argumento posicional = history
        self.assertLessEqual(len(history_enviado), 20)