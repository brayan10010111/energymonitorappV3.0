from rest_framework.routers import DefaultRouter
from .views import EquipoViewSet, get_csrf_token
from django.urls import include, path
from . import views

router = DefaultRouter()
router.register(r'equipos', EquipoViewSet, basename='equipo')

urlpatterns = [
    path('csrf/', get_csrf_token),  # esta línea conecta la vista CSRF
    path('', include(router.urls)),
    path("get_data_influx/",views.obtener_datos),
    path("get_last_hour_initial/",views.get_last_hour_initial),
    path("graficas_update/", views.stream_graficas_update, name='graficas_update')
]

