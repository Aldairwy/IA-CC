from django.db import models

class Sesion(models.Model):
    titulo = models.CharField(max_length=200, default='Nueva conversación')
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.titulo} ({self.id})"

class Mensaje(models.Model):
    ROLES = [('user', 'Usuario'), ('assistant', 'Jarvis')]
    sesion = models.ForeignKey(Sesion, on_delete=models.CASCADE, related_name='mensajes')
    rol = models.CharField(max_length=10, choices=ROLES)
    contenido = models.TextField()
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rol}: {self.contenido[:50]}"