"""Rutas de la aplicación API.

Incluye:
- Rutas CRUD (ViewSets) via `DefaultRouter`.
- Endpoints utilitarios (CSRF, consultas Influx, generación de informes).
- Endpoints SSE para actualización en tiempo real.
"""

from rest_framework.routers import DefaultRouter
from .views import EquipoViewSet, MaquinaViewSet, SensorViewSet, SistemaViewSet, get_csrf_token, VariableViewSet, SubcategoriaViewSet
from django.urls import include, path
from . import views

router = DefaultRouter()
router.register(r'equipos', EquipoViewSet, basename='equipo')
router.register(r'variables', VariableViewSet, basename='variable')
router.register(r'subcategorias', SubcategoriaViewSet, basename='subcategorias')
router.register(r'maquinas', MaquinaViewSet, basename='maquinas')
router.register(r'sistemas', SistemaViewSet, basename='sistemas')
router.register(r'sensores', SensorViewSet, basename='sensores')


urlpatterns = [
    path('csrf/', get_csrf_token),  # esta línea conecta la vista CSRF
    path('', include(router.urls)),
    path("get_data_influx/",views.get_datos),
    path("get_last_hour_initial/",views.get_last_hour_initial),
    path("graficas_update/", views.stream_graficas_update, name='graficas_update'),
    path("graficas_update_sistemas/", views.stream_graficas_update_sistemas, name='graficas_update_sistemas'),
    path("get_query_inform/", views.get_query_inform, name='get_query_inform'),
    path("stream_predicciones/", views.stream_predicciones, name='stream_predicciones'),
    path("stream_sensores/", views.stream_sensores, name='stream_sensores'),
    path("get_acumulados/", views.get_acumulados, name='get_acumulados'),
    path("stream_predicciones_dia/", views.stream_predicciones_dia, name='stream_predicciones_dia'),
]

