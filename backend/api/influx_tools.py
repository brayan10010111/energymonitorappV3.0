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


def consultar_influx(request):
    try:
        print("CONSULTA")
        inicio = request.GET.get("inicio")
        fin = request.GET.get("fin")
        print("Inicio:", inicio)
        print("Fin:", fin)
        if not inicio or not fin:
            return JsonResponse({"error": "Faltan parámetros"}, status=400)

        client = get_influx_client()

        query = f'''
        from(bucket: "Energia")
        |> range(start: {inicio}, stop: {fin})
        |> filter(fn: (r) => r._measurement == "CASA")
        |> filter(fn: (r) => r._field == "A-B")
        |> keep(columns: ["_time", "_value"])
        '''
        print(query)
        result = client.query_api().query(query)

        datos = []
        for table in result:
            for record in table.records:
                datos.append({
                    "timestamp": record.get_time().isoformat(),
                    "valor": record.get_value()
                })

        return JsonResponse({"datos": datos})
    except Exception as e:
        print("Error en consultar_influx:", e)
        return JsonResponse({"error": str(e)}, status=500)

