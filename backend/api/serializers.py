"""Serializers de Django REST Framework.

Este módulo define cómo se exponen los modelos del ORM como JSON (y viceversa).
Se usan principalmente en los `ModelViewSet` declarados en `api.views`.
"""

from rest_framework import serializers
from .models import Equipo, Subcategoria

class EquipoSerializer(serializers.ModelSerializer):
    """Serializa el modelo `Equipo` (CRUD completo)."""
    class Meta:
        model = Equipo
        fields = '__all__'
        
from .models import Sistema, Maquina, Variable, Sensor

class SistemaSerializer(serializers.ModelSerializer):
    """Serializa el modelo `Sistema`."""
    class Meta:
        model = Sistema
        fields = '__all__'

class MaquinaSerializer(serializers.ModelSerializer):
    """Serializa el modelo `Maquina`."""
    class Meta:
        model = Maquina
        fields = '__all__'

class VariableSerializer(serializers.ModelSerializer):
    """Serializa el modelo `Variable`."""
    class Meta:
        model = Variable
        fields = '__all__'

class SubcategoriaSerializer(serializers.ModelSerializer):
    """Serializa el modelo `Subcategoria`."""
    class Meta:
        model = Subcategoria
        fields = '__all__'

class SensorSerializer(serializers.ModelSerializer):
    """Serializa el modelo `Sensor`."""
    class Meta:
        model = Sensor
        fields = '__all__'