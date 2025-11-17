from django.db import models

class Equipo(models.Model):
    nombre = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    ip = models.GenericIPAddressField()
    estado = models.CharField(max_length=50, default="offline")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.modelo})"
