from rest_framework import viewsets
from .models import Equipo
from rest_framework.permissions import AllowAny
from .serializers import EquipoSerializer
from django.views.decorators.http import require_GET
from api.influx_tools import consultar_influx
from django.http import JsonResponse

class EquipoViewSet(viewsets.ModelViewSet):
    queryset = Equipo.objects.all()
    serializer_class = EquipoSerializer
    permission_classes = [AllowAny]


# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
def get_csrf_token(request):
    return JsonResponse({'detail': 'CSRF cookie set'})

@require_GET
def obtener_datos(request):
    print('obtener_datos')
    return consultar_influx(request)
