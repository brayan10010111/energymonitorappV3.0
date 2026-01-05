"""Modelos de dominio de la aplicación.

Este módulo define la estructura de datos persistida en la base relacional (Django ORM).

Entidades principales:
- `Sistema`: agrupador lógico de equipos/sensores/máquinas (p. ej. "AIRE COMPRIMIDO").
- `Equipo`: medidor/PLC accesible por IP + `id_modbus` (par único).
- `Sensor`: señal/variable proveniente de OPC UA, asociada a un `Sistema`.
- `Maquina`: entidad de negocio asociada a un `Sistema`.
- `Variable` y `Subcategoria`: catálogo de variables Modbus y su clasificación.
"""

from django.db import models

class Equipo(models.Model):
    """Equipo/medidor accesible por Modbus TCP.

    La unicidad operativa se define por la combinación (`ip`, `id_modbus`),
    permitiendo varios slaves detrás de una misma IP.

    `estado` se actualiza en procesos de monitoreo (ver `api.keepalive` / `api.modbus_client`).
    """
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
        """Restricciones a nivel de base de datos."""
        constraints = [
            models.UniqueConstraint(
                fields=['ip', 'id_modbus'],
                name='unique_ip_modbus'
            )
        ]

    def __str__(self):
        """Representación legible para admin/logs."""
        return f"{self.nombre} ({self.ip}) - {self.estado}"


    
class Sistema(models.Model):
    """Sistema o subsistema productivo.

    Se usa como agrupador para:
    - Equipos (FK opcional en `Equipo`)
    - Sensores OPC UA (FK opcional en `Sensor`)
    - Máquinas (FK obligatorio en `Maquina`)
    """
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        """Representación legible."""
        return self.nombre

class Sensor(models.Model):
    """Sensor/variable leída desde un servidor OPC UA."""
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
        """Representación legible."""
        return f"{self.nombre} - {self.nodo_opcua}"


class Maquina(models.Model):
    """Máquina asociada a un sistema (catálogo)."""
    nombre = models.CharField(max_length=100)
    capacidad = models.CharField(max_length=100)
    unidad = models.CharField(max_length=50, default="")
    sistema = models.ForeignKey(Sistema, on_delete=models.CASCADE, related_name="maquinas")

    def __str__(self):
        """Representación legible."""
        return f"{self.nombre} [{self.unidad}]"


class Subcategoria(models.Model):
    """Subcategoría para agrupar variables (catálogo)."""
    nombre = models.CharField(max_length=100)

    def __str__(self):
        """Representación legible."""
        return self.nombre

class Variable(models.Model):
    """Variable/campo medible en equipos (catálogo Modbus).

    - `registro` indica el registro Modbus (en base 1 en este proyecto).
    - `tipo` determina el decodificado de registros (ver `api.modbus_client`).
    - Se puede asociar a una `Subcategoria` (opcional).
    """
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
        """Representación legible."""
        return f"{self.nombre} [{self.unidad}]"
