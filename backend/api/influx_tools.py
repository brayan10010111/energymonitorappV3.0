"""Utilidades para InfluxDB (lectura/escritura y agregaciones).

Este módulo concentra la interacción con InfluxDB:
- Escritura de mediciones de energía (`Energia`), acumuladores (`Acumuladores`) y sensores (`Sensores`).
- Consultas para gráficas (rangos y ventanas de agregación).
- Generación de informes (CSV/XLSX).
- Helpers async para SSE (últimos N segundos).
- Helpers para el pipeline de predicción (energía + sensores).

Se usa desde:
- `api.views` (endpoints HTTP/SSE)
- `api.modbus_client` (registro de mediciones)
- `api.opc_datos` (registro de sensores)
- `api.predicciones` (dataset para modelo)
"""

from api.influx_config import get_influx_client
from django.conf import settings
import csv
from django.http import HttpResponse, JsonResponse
import logging
logger = logging.getLogger("estado_equipos")



def registrar_medicion(equipo, campos_dict, timestamp, tags=None):
    """Registra una medición en el bucket `Energia`.

    Filtra valores inválidos y escribe solo si hay al menos un campo numérico válido.
    """
    client = get_influx_client()
    write_api = client.write_api()

    # Filtrar valores inválidos antes de convertir
    clean_fields = {}
    for k, v in campos_dict.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip().lower() in ("none", "null", ""):
            continue
        try:
            clean_fields[k] = float(v)
        except (ValueError, TypeError):
            # si no se puede convertir, lo descartamos
            continue

    point = {
        "measurement": equipo,
        "fields": clean_fields,
        "time": timestamp
    }

    if tags:
        point["tags"] = tags

    # Solo escribir si hay campos válidos
    if clean_fields:
        write_api.write(bucket="Energia", record=point)
    else:
        logger.info(f"[{equipo}] No hay campos válidos para registrar en Influx")

def registrar_acumulador(
    nombre_equipo: str,
    valores: dict,
    timestamp,
    tags: dict | None = None,
    bucket: str = "Acumuladores"
):
    """Registra métricas derivadas (acumuladores) en InfluxDB.

    - Obtiene el `Sistema` del equipo desde la DB.
    - Escribe en el bucket `Acumuladores` usando `measurement = sistema`.

    Si el equipo no existe o no tiene sistema asociado, no registra.
    """
    from api.models import Equipo

    client = get_influx_client()
    write_api = client.write_api()

    # Filtrar valores válidos
    clean_fields = {}
    for campo, valor in valores.items():
        if valor is None:
            continue

        if isinstance(valor, str) and valor.strip().lower() in ("none", "null", ""):
            continue

        try:
            clean_fields[campo] = float(valor)
        except (ValueError, TypeError):
            continue

    if not clean_fields:
        logger.info(f"[{nombre_equipo}] No hay campos válidos para registrar en Influx")
        return

    # Obtener el sistema del equipo
    try:
        equipo = Equipo.objects.get(nombre=nombre_equipo)
    except Equipo.DoesNotExist:
        logger.warning(f"[{nombre_equipo}] No existe en la base. No se registra.")
        return

    # Validar si tiene sistema
    if equipo.sistema is None:
        logger.warning(f"[{nombre_equipo}] No tiene sistema asociado. No se registra.")
        return

    sistema = equipo.sistema.nombre

    # Construir punto Influx
    punto = {
        "measurement": sistema, 
        "fields": clean_fields,
        "time": timestamp,
        # "tags": {
        #     "equipo": nombre_equipo  # Tag para identificar el equipo dentro del sistema
        # }
    }

    # Agregar tags adicionales si existen
    if tags:
        punto["tags"].update(tags)

    write_api.write(bucket=bucket, record=punto)

def registrar_sensor(
    nombre_sensor: str,
    valores: dict,
    timestamp,
    tags: dict | None = None,
    bucket: str = "Sensores"
):
    """
    Registra una medición de un sensor en InfluxDB.

    Parámetros:
        nombre_sensor (str): Nombre del sensor o equipo (measurement)
        valores (dict): Campos a registrar {campo: valor}
        timestamp: Fecha/hora de la medición
        tags (dict | None): Tags opcionales
        bucket (str): Bucket de InfluxDB (default: Sensores)
    """

    client = get_influx_client()
    write_api = client.write_api()

    # Filtrar y convertir valores válidos
    clean_fields = {}

    for campo, valor in valores.items():
        if valor is None:
            continue

        if isinstance(valor, str) and valor.strip().lower() in ("none", "null", ""):
            continue

        try:
            clean_fields[campo] = float(valor)
        except (ValueError, TypeError):
            # Valor inválido → se descarta
            continue

    # Si no hay valores válidos, no escribimos nada
    if not clean_fields:
        logger.info(f"[{nombre_sensor}] No hay campos válidos para registrar en Influx")
        return

    # Construir punto Influx
    punto = {
        "measurement": nombre_sensor,
        "fields": clean_fields,
        "time": timestamp
    }

    if tags:
        punto["tags"] = tags

    # Escribir en Influx
    write_api.write(bucket=bucket, record=punto)

def consultar_influx(request):
    """Consulta serie temporal desde el bucket `Energia`.

    Espera query params:
    - `inicio` (ISO)
    - `fin` (ISO)
    - `medidor` (measurement)
    - `variable` (field)

    Ajusta automáticamente el `aggregateWindow` para normalizar el número de puntos.
    """
    import datetime
    try:
        inicio = request.GET.get("inicio")
        fin = request.GET.get("fin")
        medidor = request.GET.get("medidor") 
        variable = request.GET.get("variable") 
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
        |> filter(fn: (r) => r._field == "{variable}")
        |> aggregateWindow(every: {group}, fn: last)
        |> filter(fn: (r) => exists r._value) 
        |> yield(name: "last")

        '''
        result = client.query_api().query(query)

        datos = []
        for table in result:
            for record in table.records:
                valor = record.get_value()
                if valor is None:   # si viene nulo
                    valor = 0 
                datos.append({
                    "timestamp": record.get_time().isoformat(),
                    "valor": valor
                })


        return JsonResponse({"datos": datos})
    except Exception as e:
        logger.error("Error en consultar_influx:", e)
        return JsonResponse({"error": str(e)}, status=500)

def consultar_influx_last_hour_initial(request):
    """Consulta de precarga: últimos 60 puntos de la última hora.

    Se usa típicamente para llenar una gráfica al abrirla.
    """
    try:
        medidor = request.GET.get("medidor") 
        variable =  request.Get.get("variable")
        client = get_influx_client()
        query = f'''
        from(bucket: "Energia")
        |> range(start: -1h, stop: now())
        |> filter(fn: (r) => r._measurement == "{medidor}")
        |> filter(fn: (r) => r._field == "{variable})
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
        logger.error("Error en consultar_influx:", e)
        return JsonResponse({"error": str(e)}, status=500)

import csv
import datetime
from openpyxl import Workbook
from dateutil import parser

def crear_informe(request):
    """Genera un informe (CSV/XLSX) consultando el bucket `Energia`.

    Query params esperados:
    - `fechaInicio`, `fechaFin` (ISO)
    - `equipos` (csv)
    - `variables` (csv)
    - `formato` (csv|xlsx)
    """
    try:
        inicio = request.GET.get("fechaInicio")
        fin = request.GET.get("fechaFin")
        medidor = request.GET.get("equipos")
        variables = request.GET.get("variables")
        formato = request.GET.get("formato", "csv")  # por defecto CSV

        # Validar parámetros obligatorios
        if not inicio or not fin or not medidor or not variables:
            return JsonResponse({"error": "Faltan parámetros"}, status=400)

        # Validar rango de fechas
        try:
            inicio_dt = parser.parse(inicio)
            fin_dt = parser.parse(fin)
            if inicio_dt >= fin_dt:
                return JsonResponse({"error": "El rango de fechas es inválido"}, status=400)
        except Exception:
            return JsonResponse({"error": "Formato de fecha inválido"}, status=400)

        # Construir filtros de equipos
        lista = [item.strip() for item in medidor.split(",")]
        base = 'r["_measurement"] == "'
        equipos = " or ".join([base + item + '"' for item in lista])

        # Construir filtros de variables
        lista = [item.strip() for item in variables.split(",")]
        base = 'r["_field"] == "'
        variables = " or ".join([base + item + '"' for item in lista])

        client = get_influx_client()

        # Asegurar que las fechas estén entre comillas para Flux
        query = f'''
        from(bucket: "Energia")
        |> range(start: {inicio}, stop: {fin})
        |> filter(fn: (r) => {equipos})
        |> filter(fn: (r) => {variables})
        '''

        result = client.query_api().query(query)

        # Si no hay datos, devolver error claro
        if not result or all(len(table.records) == 0 for table in result):
            return JsonResponse({"error": "No hay datos en el rango seleccionado"}, status=404)

        fecha = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generar CSV
        if formato == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="informe_{fecha}.csv"'

            writer = csv.writer(response)
            writer.writerow(["Timestamp", "Medidor", "Variables", "Valor"])

            for table in result:
                for record in table.records:
                    writer.writerow([
                        record.get_time().isoformat(),
                        record.get_measurement(),
                        record.get_field(),
                        record.get_value() if record.get_value() is not None else 0
                    ])
            return response

        # Generar XLSX
        elif formato == "xlsx":
            wb = Workbook()
            ws = wb.active
            ws.title = "Informe"

            # Cabecera
            ws.append(["Timestamp", "Medidor", "Variables", "Valor"])

            # Filas
            for table in result:
                for record in table.records:
                    ws.append([
                        record.get_time().isoformat(),
                        record.get_measurement(),
                        record.get_field(),
                        record.get_value() if record.get_value() is not None else 0
                    ])

            response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f'attachment; filename="informe_{fecha}.xlsx"'
            wb.save(response)
            return response

        else:
            return JsonResponse({"error": "Formato no soportado"}, status=400)

    except Exception as e:
        logger.error("Error en crear_informe:", e)
        return JsonResponse({"error": str(e)}, status=500)


from asgiref.sync import sync_to_async
@sync_to_async
def get_influx_data_last_10s_async(medidor, variable):
    """Devuelve puntos de los últimos 10s para un `medidor` y `variable`.

    Está decorada con `sync_to_async` para poder usarse en endpoints SSE async.
    """

    client = get_influx_client()
    query_api = client.query_api()
    flux_query = f'''
        from(bucket: "Energia")
        |> range(start: -10s, stop: now())
        |> filter(fn: (r) => r._measurement == "{medidor}")
        |> filter(fn: (r) => r._field == "{variable}")
        |> yield(name: "last")
    '''
    tables = query_api.query(flux_query)
    datos = []
    for table in tables:
        for record in table.records:
            datos.append({
                "timestamp": record.get_time().isoformat(),
                "valor": record.get_value() or 0
            })
    return datos

from typing import List, Tuple
@sync_to_async
def get_equipos_online() -> List[Tuple[str, str, int]]:
    """Devuelve lista de equipos online con (nombre, sistema).

    Nota: se usa en flujos de predicción/agrupación.
    """
    from api.models import Equipo
    return list(Equipo.objects.filter(estado="Online").values_list("nombre", "sistema"))

@sync_to_async
def get_equipos_aire_comprimido_online() -> List[str]:
    """
    Devuelve los nombres de los equipos online del sistema AIRE COMPRIMIDO.
    """
    from api.models import Equipo
    return list(
        Equipo.objects.filter(
            estado="Online",
            sistema__nombre="AIRE COMPRIMIDO"
        ).values_list("nombre", flat=True)
    )

@sync_to_async
def get_sensores_aire_comprimido() -> List[Tuple[str, str]]:
    """
    Devuelve una lista de tuplas (variable, nodo) para los sensores de aire comprimido.
    """
    from api.models import Sensor
    sensores = Sensor.objects.filter(
        sistema__nombre="AIRE COMPRIMIDO"
    ).values_list("nombre")

    return list(sensores)

async def get_influx_data_for_air_compressor_prediction():
    """Obtiene dataset (energía + sensores) para predicción en una ventana de 30 minutos."""
    client = get_influx_client()
    query_api = client.query_api()
    sistema = "AIRE COMPRIMIDO"
    # filtro_aire_compresor = await get_equipos_aire_comprimido_online()
    sensores_aire_comprimido = await get_sensores_aire_comprimido()

    # if not filtro_aire_compresor and not sensores_aire_comprimido:
    #     logger.info("No hay equipos de Compresor de Aire online")
    #     return []

    sensores_list = ", ".join([f'"{nombre[0]}"' for nombre in sensores_aire_comprimido])
    # measurement_list = ", ".join([f'"{nombre}"' for nombre in filtro_aire_compresor])

    # ============================
    # ENERGÍA
    # ============================
    flux_query = f'''
        from(bucket: "Acumuladores")
        |> range(start: -30m, stop: now())
        |> filter(fn: (r) => r._measurement == "{sistema}")
        |> filter(fn: (r) => r._field =~ /.*_minuto$/)
        |> yield(name: "last")
    '''

    tables_energia = query_api.query(flux_query)

    datos_energia = []
    for table in tables_energia:
        for record in table.records:
            datos_energia.append({
                "_time": record.get_time().isoformat(),
                "_value": record.get_value() or 0,
                "_measurement": record.get_measurement(),
                "_field": record.get_field()
            })

    # ============================
    # SENSORES
    # ============================
    flux_query = f'''
        from(bucket: "Sensores")
        |> range(start: -30m, stop: now())
        |> filter(fn: (r) => contains(value: r._measurement, set: [{sensores_list}]))
        |> yield(name: "last")
    '''

    tables_sensores = query_api.query(flux_query)

    datos_sensores = []
    for table in tables_sensores:
        for record in table.records:
            datos_sensores.append({
                "_time": record.get_time().isoformat(),
                "_value": record.get_value() or 0,
                "_measurement": record.get_measurement(),
                "_field": record.get_field()
            })
    return [datos_energia, datos_sensores]


from datetime import datetime

class EnergyMeterAccumulator:
    """Acumulador basado en un contador total monotónico."""

    def __init__(self, name: str):
        self.name = name
        self.prev_total = None

        self.last_minute = None
        self.last_hour = None

        self.start_minute_total = None
        self.start_hour_total = None

        self.consumo_minuto = 0
        self.consumo_hora = 0

    def process(self, dato: float) -> dict:
        ahora = datetime.now()
        now_min = ahora.minute
        now_hour = ahora.hour

        # Normalizar dato
        dato = float(dato) if dato and dato > 0 else 0

        # Primer dato
        if self.prev_total is None:
            self.prev_total = dato
            self.start_minute_total = dato
            self.start_hour_total = dato
            self.last_minute = now_min
            self.last_hour = now_hour
            return {
                f"{self.name}_actual": dato,
                f"{self.name}_consumo_segundo": 0,
                f"{self.name}_consumo_minuto": 0,
                f"{self.name}_consumo_hora": 0,
            }

        # Calcular delta
        delta = dato - self.prev_total if dato >= self.prev_total else 0
        self.prev_total = dato

        # Cierre de minuto
        if now_min != self.last_minute:
            self.consumo_minuto = dato - self.start_minute_total
            self.start_minute_total = dato
            self.last_minute = now_min

        # Cierre de hora
        if now_hour != self.last_hour:
            self.consumo_hora = dato - self.start_hour_total
            self.start_hour_total = dato
            self.last_hour = now_hour

        return {
            f"{self.name}_actual": dato,
            f"{self.name}_consumo_segundo": delta,
            f"{self.name}_consumo_minuto": self.consumo_minuto,
            f"{self.name}_consumo_hora": self.consumo_hora,
        }
    

def sumar_acumulador(request):
    """Consulta el bucket `Acumuladores` y devuelve sumatoria por minuto para un sistema."""
    try:
        inicio = request.GET.get("inicio")
        fin = request.GET.get("fin")
        sistema = request.GET.get("sistema")


        if not inicio or not fin or not sistema:
            return JsonResponse({"error": "Faltan parámetros"}, status=400)

        client = get_influx_client()

        query = f'''
        from(bucket: "Acumuladores")
            |> range(start: time(v: "{inicio}"), stop: time(v: "{fin}"))
            |> filter(fn: (r) => r._measurement == "{sistema}")
            |> filter(fn: (r) => r._field =~ /.*_minuto$/)
            |> map(fn: (r) => ({{ r with _value: float(v: r._value) }}))
            |> aggregateWindow(every: 1m, fn: sum, createEmpty: false)
        '''


        result = client.query_api().query(query)

        datos = []
        for table in result:
            for record in table.records:
                datos.append({
                    "time": record.get_time().isoformat(),
                    "value": record.get_value()
                })

        return JsonResponse({"data": datos}, safe=False)

    except Exception as e:
        logger.error("Error en sumar_acumulador:", e)
        return JsonResponse({"error": str(e)}, status=500)
    


def sumar_acumulador_calculo_total(sistema:str):
    """Calcula el total (kW y kWh) acumulado del día actual para un sistema."""
    try:
        sistema = sistema

        now = datetime.utcnow()
        inicio = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        fin = now.isoformat() + "Z"
        client = get_influx_client()

        query = f'''
        from(bucket: "Acumuladores")
            |> range(start: time(v: "{inicio}"), stop: time(v: "{fin}"))
            |> filter(fn: (r) => r._measurement == "{sistema}")
            |> filter(fn: (r) => r._field =~ /.*_minuto$/)
            |> map(fn: (r) => ({{ r with _value: float(v: r._value) }}))
            |> aggregateWindow(every: 1m, fn: sum, createEmpty: false)
        '''


        result = client.query_api().query(query)

        valores = []
        for table in result:
            for record in table.records:
                valores.append(record.get_value())

        # kW acumulados por minuto
        total_kW = sum(valores)

        # Convertir a kWh
        total_kWh = total_kW / 60

        return {
            "total_kW": total_kW,
            "total_kWh": total_kWh
        }

    except Exception as e:
        logger.error("Error en sumar_acumulador:", e)


async def get_influx_data_for_air_compressor_prediction_all_day():
    """Obtiene dataset (energía + sensores) desde 00:00 hasta ahora para predicción diaria."""
    try:
        client = get_influx_client()
        query_api = client.query_api()
        sistema = "AIRE COMPRIMIDO"
        now = datetime.utcnow()
        inicio = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        fin = now.isoformat() + "Z"
        sensores_aire_comprimido = await get_sensores_aire_comprimido()


        sensores_list = ", ".join([f'"{nombre[0]}"' for nombre in sensores_aire_comprimido])
        query = f'''
            from(bucket: "Acumuladores")
                |> range(start: time(v: "{inicio}"), stop: time(v: "{fin}"))
                |> filter(fn: (r) => r._measurement == "{sistema}")
                |> filter(fn: (r) => r._field =~ /.*_minuto$/)
                |> map(fn: (r) => ({{ r with _value: float(v: r._value) }}))
                |> aggregateWindow(every: 1m, fn: sum, createEmpty: false)
        '''

        tables_energia = query_api.query(query)

        datos_energia = []
        for table in tables_energia:
            for record in table.records:
                datos_energia.append({
                    "_time": record.get_time().isoformat(),
                    "_value": record.get_value() or 0,
                    "_measurement": record.get_measurement(),
                    "_field": record.get_field()
                })

        flux_query = f'''
            from(bucket: "Sensores")
            |> range(start: -30m, stop: now())
            |> filter(fn: (r) => contains(value: r._measurement, set: [{sensores_list}]))
            |> yield(name: "last")
        '''

        tables_sensores = query_api.query(flux_query)

        datos_sensores = []
        for table in tables_sensores:
            for record in table.records:
                datos_sensores.append({
                    "_time": record.get_time().isoformat(),
                    "_value": record.get_value() or 0,
                    "_measurement": record.get_measurement(),
                    "_field": record.get_field()
                })
        return [datos_energia, datos_sensores]

    except Exception as e:
        logger.error("Error en get_influx_data_for_air_compressor_prediction_all_day:", e)
        return []
    

@sync_to_async
def get_influx_data_last_10s_for_sistems_async(sistema: str):
    """Devuelve el acumulado agregado de un sistema en los últimos 10s.

    Retorna un dict con forma `{timestamp, valor}` listo para SSE.
    """

    client = get_influx_client()

    query = f'''
    from(bucket: "Acumuladores")
        |> range(start: -10s, stop: now())
        |> filter(fn: (r) => r._measurement == "{sistema}")
        |> filter(fn: (r) => r._field =~ /.*_minuto$/)
        |> map(fn: (r) => ({{ r with _value: float(v: r._value) }}))
        |> aggregateWindow(every: 1m, fn: sum, offset: 1s)
    '''
    tables = client.query_api().query(query)

    valores = []
    timestamp = None

    for table in tables:
        for record in table.records:
            valores.append(record.get_value() or 0)
            timestamp = record.get_time().isoformat()

    total_kW = sum(valores)

    dato_total = {
        "timestamp": timestamp,
        "valor": total_kW
    }
    print("Dato total:", dato_total)
    return dato_total
