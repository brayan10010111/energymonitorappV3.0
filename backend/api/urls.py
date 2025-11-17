from rest_framework.routers import DefaultRouter
from .views import EquipoViewSet, get_csrf_token
from django.urls import include, path
from api.views import obtener_datos

router = DefaultRouter()
router.register(r'equipos', EquipoViewSet, basename='equipo')

urlpatterns = [
    path('csrf/', get_csrf_token),  # esta línea conecta la vista CSRF
    path('', include(router.urls)),
    path("get_data_influx/", obtener_datos),

]

