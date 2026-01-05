"""Lectura de variables desde OPC UA y registro en InfluxDB.

Este módulo:
- Obtiene el catálogo de sensores desde la API (`/sensores/`).
- Lee valores OPC UA (sin bloquear el event loop, usando `asyncio.to_thread`).
- Registra valores en InfluxDB (bucket de sensores).
- Corre en background (threads) mediante `start_opc_async()`.
"""




def listar_equipos_desde_db():
    """Devuelve todos los equipos (ORM) desde la base de datos."""
    from api.models import Equipo
    return Equipo.objects.all()

def get_equipos_desde_db():
    """Devuelve equipos cuyo estado actual es Online."""
    return listar_equipos_desde_db().filter(estado="Online") 

import asyncio
from opcua import Client
import environ
from typing import List, Dict, Any
import logging

import requests
logger = logging.getLogger("estado_equipos")


env = environ.Env()
environ.Env.read_env()
INTERVALO_OPC_SEGUNDOS = env.int("INTERVALO_OPC_SEGUNDOS", default=5)

async def leer_opcua_variables_async(
    url_env: str,
    nodo: str,
    intentos: int = 5,
    intervalo: float = INTERVALO_OPC_SEGUNDOS
) -> Dict[str, Any]:
    """
    Lee variables OPC UA de forma asíncrona sin bloquear el event loop.

    Parámetros:
        url_env (str): Nombre de la variable en .env con la URL OPC
        nodos (List[str]): Lista de nodos OPC UA a leer
        intentos (int): Reintentos si el valor aún no está disponible
        intervalo (float): Tiempo entre reintentos

    Retorna:
        Dict[str, Any]: Valores leídos o errores
    """

    url = env(url_env)
    client = Client(url)

    resultados = {}

    # Conectar sin bloquear
    try:
        await asyncio.to_thread(client.connect)
    except Exception as e:
        return {"error": f"No se pudo conectar al servidor OPC UA: {e}"}

    try:
        try:
            var = client.get_node(nodo)

            valor = None
            for _ in range(intentos):
                valor = await asyncio.to_thread(var.get_value)

                if valor is not None:
                    break

                await asyncio.sleep(intervalo)

            resultados[nodo] = valor if valor is not None else "Sin datos"

        except Exception as e:
            resultados[nodo] = f"Error leyendo nodo: {e}"

    finally:
        await asyncio.to_thread(client.disconnect)

    return resultados


from datetime import datetime
from zoneinfo import ZoneInfo
async def registrar_sensores_aire_influxdb(nombre: str, nodo: str):
    """Lee un nodo OPC UA y registra el valor como medición de sensor en InfluxDB."""
    from api.influx_tools import registrar_sensor

    valores = await leer_opcua_variables_async(
        url_env="OPC_URL",
        nodo="ns=2;s=" + nodo,
        intentos=5,
        intervalo=INTERVALO_OPC_SEGUNDOS
    )

    registrar_sensor(
        nombre,
        valores,
        datetime.now(ZoneInfo("America/Bogota")).isoformat()
    )


async def opc_async_forever(intervalo: int = INTERVALO_OPC_SEGUNDOS, variables=None):
    """Bucle infinito: lee sensores y los registra en Influx cada `intervalo` segundos."""
    if not variables:
        logger.error("Variables no proporcionadas para opc_async_forever")
        return

    logger.info("OPC ASÍNCRONO INICIADO")

    while True:
        try:
            await asyncio.gather(*[
                registrar_sensores_aire_influxdb(nombre, nodo)
                for nombre, nodo in variables.items()
            ])
        except Exception as e:
            logger.error(f"Error en bucle: {e}", exc_info=True)

        await asyncio.sleep(intervalo)

def obtener_variables():
    """Consulta al backend el catálogo de sensores y lo normaliza a dict `{nombre: nodo}`."""
    url = env("POSTGRES_URL") + "sensores/"
    response = requests.get(url)

    try:
        if response.status_code == 200:
            data = response.json()

            # Convertir lista → dict {nombre: nodo}
            return {item["nombre"]: item["nodo_opcua"] for item in data}

        return None

    except Exception as e:
        logger.error("Excepción al obtener variables:", exc_info=e)
        logger.error("Error en respuesta HTTP: %s", response.status_code)
        return None



import threading
import time
def start_opc_async():
    """Arranca hilos daemon:

    - Un hilo refresca el catálogo de sensores cada 60s.
    - Otro hilo ejecuta el loop OPC (asyncio) con el catálogo actual.
    """
    shared = {"sensores": None}   #  contenedor compartido

    def run_sensores():
        while True:
            shared["sensores"] = obtener_variables()
            logger.info("Variables actualizadas")
            time.sleep(60)  # espera 1 minuto

    def run_opc():
        logger.info("Iniciando OPC ASÍNCRONO...")
        while True:
            vars_actuales = shared["sensores"]
            if vars_actuales is not None:
                asyncio.run(opc_async_forever(intervalo=INTERVALO_OPC_SEGUNDOS, variables=vars_actuales))
            else:
                logger.warning("Variables aún no disponibles")
                time.sleep(INTERVALO_OPC_SEGUNDOS)

    # Lanzar hilo para OPC
    threading.Thread(target=run_opc, name="OPC-Async", daemon=True).start()
    logger.info("OPC ASÍNCRONO lanzado")

    # Lanzar hilo para Sensores
    threading.Thread(target=run_sensores, name="Sensores-Reader", daemon=True).start()
    logger.info("Lectura de variables cada 1 minuto lanzada")


