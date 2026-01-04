from rest_framework import viewsets
from .models import Equipo
from rest_framework.permissions import AllowAny
from .serializers import EquipoSerializer
from django.views.decorators.http import require_GET
from api.influx_tools import consultar_influx,consultar_influx_last_hour_initial
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
    return consultar_influx(request)

@require_GET
def get_last_hour_initial(request):
    return consultar_influx_last_hour_initial(request)


async def stream_graficas_update(request):
    """
    Una vista que transmite actualizaciones del gráfico en tiempo real.
    """
    # Usamos StreamingHttpResponse para mantener la conexión abierta.
    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    # Headers para SSE
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no' # Desactiva el buffering en proxies como Nginx
    return response

import asyncio
from django.http import StreamingHttpResponse
import json
from asgiref.sync import sync_to_async
from api.influx_tools import get_influx_data_by_hour
async def event_stream():
        async_get_data = sync_to_async(get_influx_data_by_hour, thread_sensitive=True)
        while True:
            try:
                datos_actualizados = await async_get_data(
                time_range="-5s", 
                measurement="CASA", 
                field="A-B"
            )
                payload = {
                "tipo": "grafico_actualizado",
                "contenido": datos_actualizados
            }
            
                message = f"data: {json.dumps(payload)}\n\n"
                yield message.encode("utf-8")

            except Exception as e:
                print(f"Error en el bucle de event_stream: {e}")

            # Esperamos 5 segundos antes de la siguiente consulta
            await asyncio.sleep(5)


