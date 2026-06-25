"""
Configuración de URLs del proyecto (core).

Aquí se enrutan las URLs de nivel raíz. La regla es simple:
- /admin/  -> el panel de administración de Django.
- /api/    -> delega TODO lo que empiece por /api/ al archivo de
              rutas de la app 'jarvis' (jarvis/urls.py).

'include()' es lo que permite esa delegación: en vez de listar aquí
cada endpoint de jarvis, decimos "lo que sea /api/..., míralo allá".
Así cada app gestiona sus propias rutas y este archivo queda corto.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('jarvis.urls')),
]