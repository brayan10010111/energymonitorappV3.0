from django.contrib import admin

# Register your models here.
from .models import Equipo, Sensor, Sistema, Maquina, Variable, Subcategoria
admin.site.register(Equipo)
admin.site.register(Sistema)
admin.site.register(Maquina)
admin.site.register(Variable)
admin.site.register(Subcategoria)
admin.site.register(Sensor)