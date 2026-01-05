"""Vistas/handlers HTTP de la API.

Este módulo mezcla:
- CRUD REST usando `ModelViewSet` (DRF).
- Endpoints GET de consulta (Influx, informes).
- Endpoints SSE (Server-Sent Events) para actualización de gráficas en tiempo real.

Notas:
- Los endpoints SSE usan `StreamingHttpResponse` y generadores async que emiten eventos
    con el formato `data: <json>\n\n`.
"""

from rest_framework import viewsets

from api.predicciones import calcular_prediccion_consumo_dia, prediccion_en_tiempo_real
from .models import Equipo, Sistema
from rest_framework.permissions import AllowAny
from .serializers import EquipoSerializer, SistemaSerializer
from django.views.decorators.http import require_GET
from api.influx_tools import consultar_influx,consultar_influx_last_hour_initial, crear_informe, get_influx_data_last_10s_for_sistems_async,sumar_acumulador, get_influx_data_last_10s_async
from django.http import JsonResponse

class EquipoViewSet(viewsets.ModelViewSet):
    """CRUD REST para el modelo `Equipo`."""
    queryset = Equipo.objects.all()
    serializer_class = EquipoSerializer
    permission_classes = [AllowAny]

class VariableViewSet(viewsets.ModelViewSet):
    """CRUD REST para el modelo `Variable`."""
    from .models import Variable
    from .serializers import VariableSerializer

    queryset = Variable.objects.all()
    serializer_class = VariableSerializer
    permission_classes = [AllowAny]

class SensorViewSet(viewsets.ModelViewSet):
    """CRUD REST para el modelo `Sensor`."""
    from .models import Sensor
    from .serializers import SensorSerializer

    queryset = Sensor.objects.all()
    serializer_class = SensorSerializer
    permission_classes = [AllowAny]

class SubcategoriaViewSet(viewsets.ModelViewSet):
    """CRUD REST para el modelo `Subcategoria`."""
    from .models import Subcategoria
    from .serializers import SubcategoriaSerializer

    queryset = Subcategoria.objects.all()
    serializer_class = SubcategoriaSerializer
    permission_classes = [AllowAny]

class MaquinaViewSet(viewsets.ModelViewSet):
    """CRUD REST para el modelo `Maquina`."""
    from .models import Maquina
    from .serializers import MaquinaSerializer

    queryset = Maquina.objects.all()
    serializer_class = MaquinaSerializer
    permission_classes = [AllowAny]

class SistemaViewSet(viewsets.ModelViewSet):
    """CRUD REST para el modelo `Sistema`."""
    from .models import Sistema
    from .serializers import SistemaSerializer

    queryset = Sistema.objects.all()
    serializer_class = SistemaSerializer
    permission_classes = [AllowAny]


# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
def get_csrf_token(request):
    """Fuerza a Django a setear la cookie `csrftoken`.

    Se usa desde el frontend antes de POSTs que requieren CSRF.
    """
    return JsonResponse({'detail': 'CSRF cookie set'})

@require_GET
def get_datos(request):
    """Proxy HTTP hacia consulta de InfluxDB (`consultar_influx`)."""
    return consultar_influx(request)

@require_GET
def get_query_inform(request):
    """Genera un informe (csv/xlsx) a partir de datos en InfluxDB."""
    return crear_informe(request)

@require_GET
def get_last_hour_initial(request):
    """Consulta inicial de datos (última hora), útil para precargar una gráfica."""
    return consultar_influx_last_hour_initial(request)

@require_GET
def get_acumulados(request):
    """Devuelve acumulados (bucket de acumuladores) en un rango para un sistema."""
    return sumar_acumulador(request)



import environ
env = environ.Env()
environ.Env.read_env()
INTERVALO_REFRESCO = env.int("INTERVALO_REFRESCO", default=5)

from django.http import StreamingHttpResponse
import json, asyncio
from api.influx_tools import get_influx_data_last_10s_async

async def stream_graficas_update(request):
    """SSE: emite puntos nuevos para una gráfica por medidor/variable.

    Query params esperados:
    - `medidor`: measurement en Influx
    - `variable`: field en Influx
    """
    medidor = request.GET.get("medidor")
    variable = request.GET.get("variable")

    async def async_generator():
        while True:
            datos_actualizados = await get_influx_data_last_10s_async(medidor, variable)
            payload = {
                "tipo": "grafico_actualizado",
                "contenido": datos_actualizados
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(INTERVALO_REFRESCO)

    response = StreamingHttpResponse(async_generator(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


async def stream_graficas_update_sistemas(request):
    """SSE: emite el último acumulado agregado de un sistema.

    Query params:
    - `sistema`: nombre del sistema
    """
    sistema = request.GET.get("sistema")

    async def async_generator():
        while True:
            datos_actualizados = await get_influx_data_last_10s_for_sistems_async(sistema)
            payload = {
                "tipo": "grafico_actualizado",
                "contenido": [datos_actualizados] 
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(INTERVALO_REFRESCO*12)

    response = StreamingHttpResponse(async_generator(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response

async def stream_predicciones(request):
    """SSE: emite predicciones de corto plazo.

    Actualmente solo soporta `sistema == "AIRE COMPRIMIDO"`.
    """
    sistema = request.GET.get("sistema")
    if(sistema!="AIRE COMPRIMIDO"):
        return JsonResponse({"error":"Sistema no soportado para predicciones"}, status=400)
    
    async def async_generator_aire_comprimido():
        while True:
            predicciones = await prediccion_en_tiempo_real(INTERVALO_REFRESCO*12)
            payload = {
                "tipo": "grafico_actualizado",
                "contenido": predicciones
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(INTERVALO_REFRESCO*12)

    response = StreamingHttpResponse(async_generator_aire_comprimido(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response



async def stream_predicciones_dia(request):
    """SSE: emite el total estimado del día (real + predicción restante).

    Actualmente solo soporta `sistema == "AIRE COMPRIMIDO"`.
    """
    sistema = request.GET.get("sistema")
    if(sistema!="AIRE COMPRIMIDO"):
        return JsonResponse({"error":"Sistema no soportado para predicciones"}, status=400)
    
    async def async_calcular_prediccion_consumo_dia():
        while True:
            predicciones = await calcular_prediccion_consumo_dia(sistema,INTERVALO_REFRESCO*12)
            payload = {
                "tipo": "grafico_actualizado",
                "contenido": predicciones
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(INTERVALO_REFRESCO*12)

    response = StreamingHttpResponse(async_calcular_prediccion_consumo_dia(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response

