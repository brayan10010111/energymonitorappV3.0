from api.influx_config import get_influx_client
from django.http import JsonResponse
from django.conf import settings


def registrar_medicion(equipo, campos_dict, timestamp, tags=None):
    #print("Registrar medición llamada")
    client = get_influx_client()
    #print("Estado de conexión:", client.health().status)
    write_api = client.write_api()
    point = {
        "measurement": equipo,
        "fields": {k: float(v) for k, v in campos_dict.items()},
        "time": timestamp
    }

    if tags:
        point["tags"] = tags

    write_api.write(bucket="Energia", record=point)

import datetime

def consultar_influx(request):
    try:
        inicio = request.GET.get("inicio")
        fin = request.GET.get("fin")
        medidor = request.GET.get("medidor") 
        campo = request.GET.get("campo") 
        # print("Inicio:", inicio)
        # print("Fin:", fin)
        if not inicio or not fin:
            return JsonResponse({"error": "Faltan parámetros"}, status=400)

        client = get_influx_client()
        start = datetime.datetime.fromisoformat(inicio.replace("Z", "+00:00"))
        end = datetime.datetime.fromisoformat(fin.replace("Z", "+00:00"))
        delta = end - start

        if delta <= datetime.timedelta(hours=1):
         # Agrupar por minuto
            group = "1m"
        elif delta >= datetime.timedelta(hours=23, minutes=59) and delta <= datetime.timedelta(hours=24, minutes=1):
            # Exactamente un día → 24 puntos (uno por hora)
            group = "1h"
        elif delta > datetime.timedelta(hours=24):
            # Más de un día → también por hora, pero tendrás más de 24 puntos
            group = "1h"
        else:
            # Rango intermedio → normalizar a 60 puntos
            total_minutes = int(delta.total_seconds() / 60)
            step = max(1, total_minutes // 60)
            group = f"{step}m"


        query = f'''
        from(bucket: "Energia")
        |> range(start: {inicio}, stop: {fin})
        |> filter(fn: (r) => r._measurement == "{medidor}")
        |> filter(fn: (r) => r._field == "A-B")
        |> aggregateWindow(every: {group}, fn: last)
        |> filter(fn: (r) => exists r._value) 
        |> yield(name: "last")

        '''
        # print(query)
        result = client.query_api().query(query)

        datos = []
        for table in result:
            for record in table.records:
                valor = record.get_value()
                if valor is None:   # si viene nulo
                    valor = 0 
                datos.append({
                    "timestamp": record.get_time().strftime("%H:%M"),
                    "valor": record.get_value()
                })

        return JsonResponse({"datos": datos})
    except Exception as e:
        print("Error en consultar_influx:", e)
        return JsonResponse({"error": str(e)}, status=500)



import asyncio
def get_influx_data_by_hour(time_range="-5s", measurement="nombre_de_tu_medicion", field="valor"):
    """
    Función SÍNCRONA y reutilizable para consultar datos de InfluxDB y agruparlos por hora.
    
    Args:
        time_range (str): El rango de tiempo para la consulta de InfluxDB (ej. "-5s", "-1h").
        measurement (str): El nombre de la 'measurement' en InfluxDB.
        field (str): El nombre del 'field' a consultar.

    Returns:
        list: Una lista de 24 elementos con la suma de los valores para cada hora.
    """
    # print(f"Ejecutando consulta síncrona para el rango: {time_range}")
    client = get_influx_client()
    query_api = client.query_api()

    while True:

        horas_local  = [0] * 24
        flux_query = f'''
            from(bucket: "Energia")
                |> range(start: {time_range}) 
                |> filter(fn: (r) => r._measurement == "{measurement}")
                |> filter(fn: (r) => r._field == "A-B")
                |> filter(fn: (r) => r["fase"] == "trifásico")
        '''
        try:
            tables = query_api.query(flux_query)

            # Procesar los resultados
            for table in tables:
                for record in table.records:
                    valor = record.get_value()
                    if valor is None:   # si viene nulo
                        valor = 0 
                    record_time = record.get_time().strftime("%H:%M")
                    record_value = record.get_value()

                    if record_time is not None and record_value is not None:
                        # La hora se obtiene en UTC, asegúrate de que esto sea lo que esperas.
                        # Si necesitas la hora local del servidor, deberás hacer una conversión de zona horaria.
                        hora = record.get_time().hour 
                        horas_local[hora] += record_value
            
            # print("Consulta a InfluxDB finalizada exitosamente.")
            return horas_local

        except Exception as e:
            print(f"Error al consultar InfluxDB en services.py: {e}")
            # Devuelve una lista vacía o relanza la excepción según tu estrategia de manejo de errores
            return [0] * 24
        

def consultar_influx_last_hour_initial(request,measurement="nombre_de_tu_medicion"):
    try:

        client = get_influx_client()
        query = f'''
        from(bucket: "Energia")
        |> range(start: -1h, stop: now())
        |> filter(fn: (r) => r._measurement == "{measurement}")
        |> filter(fn: (r) => r._field == "A-B")
        |> keep(columns: ["_time", "_value"])
        '''
        result = client.query_api().query(query)

        datos = []
        for table in result:
            for record in table.records:
                valor = record.get_value()
                if valor is None:   # si viene nulo
                    valor = 0 
                datos.append({
                    "timestamp": record.get_time().strftime("%H:%M"),
                    "valor": record.get_value()
                })
        datos = datos[-60:]

        return JsonResponse({"datos": datos})
    except Exception as e:
        print("Error en consultar_influx:", e)
        return JsonResponse({"error": str(e)}, status=500)
