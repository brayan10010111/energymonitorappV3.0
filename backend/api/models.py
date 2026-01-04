from django.db import models

class Equipo(models.Model):
    nombre = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    ip = models.GenericIPAddressField()  # <-- ya no es único
    id_modbus = models.PositiveIntegerField(default=1)
    estado = models.CharField(max_length=50, default="Offline")
    ultima_actualizacion = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    sistema = models.ForeignKey(
        "Sistema",
        on_delete=models.SET_NULL,
        null=True,          # Puede no tener sistema
        blank=True,         # Opcional en formularios
        related_name="equipos"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['ip', 'id_modbus'],
                name='unique_ip_modbus'
            )
        ]

    def __str__(self):
        return f"{self.nombre} ({self.ip}) - {self.estado}"


    
class Sistema(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre

class Sensor(models.Model):
    nombre = models.CharField(max_length=100)
    nodo_opcua = models.CharField(max_length=100)
    sistema = models.ForeignKey(
        "Sistema",
        on_delete=models.SET_NULL,
        null=True,          # Puede no tener sistema
        blank=True,         # Opcional en formularios
        related_name="sensores"
    )
    def __str__(self):
        return f"{self.nombre} - {self.nodo_opcua}"


class Maquina(models.Model):
    nombre = models.CharField(max_length=100)
    capacidad = models.CharField(max_length=100)
    unidad = models.CharField(max_length=50, default="")
    sistema = models.ForeignKey(Sistema, on_delete=models.CASCADE, related_name="maquinas")

    def __str__(self):
        return f"{self.nombre} [{self.unidad}]"


class Subcategoria(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

class Variable(models.Model):
    TIPOS = [
        ("UTF8", "UTF8"),
        ("INT16U", "INT16U"),
        ("INT32U", "INT32U"),
        ("DATETIME", "DATETIME"),
        ("FLOAT32", "FLOAT32"),
        ("4Q_FP_PF", "4Q_FP_PF"),
        ("FLOAT32/INT32U", "FLOAT32/INT32U"),
        ("BITMAP", "BITMAP"),
        ("INT64", "INT64"),
    ]

    nombre = models.CharField(max_length=100)
    unidad = models.CharField(max_length=50)
    registro = models.CharField(max_length=8)
    tipo = models.CharField(
        max_length=20,               
        choices=TIPOS,                
        default="FLOAT32"             
    )

    subcategoria = models.ForeignKey(
    'Subcategoria',
    on_delete=models.CASCADE,
    related_name='variables',
    null=True,
    blank=True
)


    def __str__(self):
        return f"{self.nombre} [{self.unidad}]"
