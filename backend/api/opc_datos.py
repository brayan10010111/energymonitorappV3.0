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
from typing import Dict, Any, Optional
import logging
import os
import threading
import time

import requests
logger = logging.getLogger("estado_equipos")


env = environ.Env()
environ.Env.read_env()
INTERVALO_OPC_SEGUNDOS = env.int("INTERVALO_OPC_SEGUNDOS", default=5)


def _leer_sensores_opcua_sync(
    url: str,
    variables: Dict[str, str],
    intentos: int,
    intervalo: float,
) -> Dict[str, Dict[str, Any]]:
    """Lee todos los sensores en una sola sesión OPC UA.

    Esto evita crear N conexiones y N llamadas a `asyncio.to_thread` por ciclo,
    que era la causa principal de la explosión de hilos.

    Retorna un dict: {nombre_sensor: {<node_id>: valor | "Sin datos" | "Error ..."}}
    """

    client = Client(url)
    resultados: Dict[str, Dict[str, Any]] = {}

    try:
        client.connect()
    except Exception as e:
        err = f"No se pudo conectar al servidor OPC UA: {e}"
        for nombre, nodo in variables.items():
            node_id = f"ns=2;s={nodo}"
            resultados[nombre] = {node_id: err}
        return resultados

    try:
        for nombre, nodo in variables.items():
            node_id = f"ns=2;s={nodo}"
            try:
                var = client.get_node(node_id)

                valor: Any = None
                for _ in range(intentos):
                    valor = var.get_value()
                    if valor is not None:
                        break
                    time.sleep(intervalo)

                resultados[nombre] = {node_id: valor if valor is not None else "Sin datos"}

            except Exception as e:
                resultados[nombre] = {node_id: f"Error leyendo nodo: {e}"}

    finally:
        try:
            client.disconnect()
        except Exception:
            # Evitar que un disconnect fallido tumbe el loop
            logger.error("Error desconectando OPC UA", exc_info=True)
            pass

    return resultados

async def leer_opcua_variables_async(
    url_env: str,
    nodo: str,
    intentos: int = 5,
    intervalo: float = INTERVALO_OPC_SEGUNDOS
) -> Dict[str, Any]:
    """Compat: lectura de un único nodo.

    Internamente usa lectura bulk para evitar crear hilos por cada sensor.
    """

    url = env(url_env)
    variables = {"_single": nodo.replace("ns=2;s=", "")}
    resultado = await asyncio.to_thread(
        _leer_sensores_opcua_sync,
        url,
        variables,
        intentos,
        intervalo,
    )
    # resultado["_single"] es {<node_id>: valor}
    return resultado.get("_single", {nodo: "Sin datos"})


from datetime import datetime
from zoneinfo import ZoneInfo
async def _leer_y_registrar_sensores_bulk(variables: Dict[str, str]):
    """Lee todos los sensores (bulk) y registra cada uno en Influx."""
    from api.influx_tools import registrar_sensor

    url = env("OPC_URL")
    lecturas = await asyncio.to_thread(
        _leer_sensores_opcua_sync,
        url,
        variables,
        5,
        float(INTERVALO_OPC_SEGUNDOS),
    )

    timestamp = datetime.now(ZoneInfo("America/Bogota")).isoformat()
    for nombre_sensor, valores in lecturas.items():
        try:
            registrar_sensor(nombre_sensor, valores, timestamp)
        except Exception as e:
            logger.error("Error registrando sensor %s en Influx: %s", nombre_sensor, e, exc_info=True)


def _opc_persistent_loop(
    *,
    shared: Dict[str, Optional[Dict[str, str]]],
    shared_lock: threading.Lock,
    intervalo: float,
    intentos: int = 1,
    intervalo_reintento: float = 1.0,
):
    """Loop OPC UA con conexión persistente.

    - Mantiene una única conexión OPC UA abierta.
    - Cachea nodos para evitar resolverlos en cada iteración.
    - Si hay error de conexión/lectura, desconecta, limpia cache y reintenta.

    Se ejecuta en un hilo dedicado (daemon), por lo que no requiere asyncio.
    """
    from api.influx_tools import registrar_sensor

    url = env("OPC_URL")
    client = Client(url)

    connected = False
    node_cache: Dict[str, Any] = {}

    def is_connection_error(exc: BaseException) -> bool:
        # Errores típicos cuando el servidor OPC corta la conexión
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, TimeoutError, OSError)):
            return True
        msg = str(exc).lower()
        return any(
            s in msg
            for s in (
                "broken pipe",
                "connection reset",
                "connection aborted",
                "timed out",
                "bad file descriptor",
                "not connected",
            )
        )

    def ensure_connected() -> bool:
        nonlocal connected, client
        if connected:
            return True
        try:
            client.connect()
            connected = True
            logger.info("OPC UA conectado (persistente)")
            return True
        except Exception as e:
            logger.error("No se pudo conectar al servidor OPC UA: %s", e)
            # Recrear cliente ante fallas de conexión para evitar estados corruptos
            try:
                client.disconnect()
            except Exception:
                pass
            client = Client(url)
            connected = False
            return False

    def reset_connection():
        nonlocal connected, client
        try:
            client.disconnect()
        except Exception:
            pass
        # IMPORTANTE: recrear Client para que el thread interno del opcua
        # (renovación de secure channel) vuelva a inicializarse limpio.
        client = Client(url)
        connected = False
        node_cache.clear()

    backoff = 1.0
    backoff_max = 30.0

    while True:
        with shared_lock:
            vars_actuales = shared.get("sensores")

        if not vars_actuales:
            logger.warning("Variables aún no disponibles")
            time.sleep(intervalo)
            continue

        if not ensure_connected():
            time.sleep(backoff)
            backoff = min(backoff * 2, backoff_max)
            continue

        # Conectó OK: resetear backoff
        backoff = 1.0

        try:
            # Preparar cache de nodos según catálogo actual
            desired_node_ids = {f"ns=2;s={nodo}" for nodo in vars_actuales.values()}
            for node_id in list(node_cache.keys()):
                if node_id not in desired_node_ids:
                    node_cache.pop(node_id, None)

            # Lectura + escritura Influx
            timestamp = datetime.now(ZoneInfo("America/Bogota")).isoformat()
            for nombre, nodo in vars_actuales.items():
                node_id = f"ns=2;s={nodo}"
                try:
                    var = node_cache.get(node_id)
                    if var is None:
                        var = client.get_node(node_id)
                        node_cache[node_id] = var

                    valor: Any = None
                    for _ in range(max(1, intentos)):
                        valor = var.get_value()
                        if valor is not None:
                            break
                        time.sleep(intervalo_reintento)

                    valores = {node_id: valor if valor is not None else "Sin datos"}
                    registrar_sensor(nombre, valores, timestamp)

                except Exception as e:
                    # Si es un error de conexión, forzamos reconexión global.
                    if is_connection_error(e):
                        raise
                    # Si falla un nodo, registramos error para ese sensor y seguimos.
                    try:
                        registrar_sensor(nombre, {node_id: f"Error leyendo nodo: {e}"}, timestamp)
                    except Exception:
                        pass

        except Exception as e:
            if is_connection_error(e):
                logger.warning("Conexión OPC UA perdida (%s). Reintentando...", e)
            else:
                logger.error("Error crítico en ciclo OPC persistente: %s", e, exc_info=True)
            reset_connection()

        time.sleep(intervalo)


async def opc_async_forever(intervalo: int = INTERVALO_OPC_SEGUNDOS, variables=None):
    """Bucle infinito (legacy): lee sensores y registra en Influx cada `intervalo`.

    Nota: se conserva por compatibilidad, pero ahora usa lectura bulk.
    """
    if not variables:
        logger.error("Variables no proporcionadas para opc_async_forever")
        return

    logger.info("OPC ASÍNCRONO INICIADO")

    while True:
        try:
            await _leer_y_registrar_sensores_bulk(variables)
        except Exception as e:
            logger.error("Error en bucle OPC: %s", e, exc_info=True)

        await asyncio.sleep(intervalo)

from requests.exceptions import ReadTimeout, ConnectTimeout, ConnectionError


def obtener_variables(max_retries=3, delay=2):
    """Obtiene el catálogo de sensores y lo normaliza a dict {nombre: nodo}.

    IMPORTANTE: antes hacía `requests.get` hacia el mismo backend (auto-llamada),
    lo que puede saturar workers y congelar consultas. Preferimos ORM; dejamos
    fallback HTTP por compatibilidad.
    """

    # 1) ORM (preferido)
    try:
        from api.models import Sensor
        data = list(Sensor.objects.all().values("nombre", "nodo_opcua"))
        return {item["nombre"]: item["nodo_opcua"] for item in data}
    except Exception as e:
        logger.warning("No se pudo obtener sensores por ORM; usando fallback HTTP: %s", e)

    # 2) Fallback HTTP con reintentos
    url = env("POSTGRES_URL") + "sensores/"
    for intento in range(1, max_retries + 1):
        try:
            response = requests.get(url, timeout=(3, 10))  # (connect_timeout, read_timeout)

            if response.status_code == 200:
                data = response.json()
                return {item["nombre"]: item["nodo_opcua"] for item in data}

            logger.error("Respuesta inesperada del backend sensores: %s", response.status_code)
            return None

        except (ReadTimeout, ConnectTimeout):
            logger.warning("Timeout al consultar %s. Reintento %s/%s...", url, intento, max_retries)
        except ConnectionError:
            logger.error("No se pudo conectar con el backend en %s. Reintento %s/%s...", url, intento, max_retries)
        except Exception as e:
            logger.error("Excepción inesperada al obtener sensores (HTTP): %s", e, exc_info=True)
            return None

        time.sleep(delay)

    logger.error("No fue posible obtener sensores después de varios intentos.")
    return None


_opc_start_lock = threading.Lock()
_opc_started = False


def start_opc_async():
    """Arranca hilos daemon:

    - Un hilo refresca el catálogo de sensores cada 60s.
    - Otro hilo ejecuta el loop OPC (asyncio) con el catálogo actual.
    """
    # Evitar doble arranque por autoreload de Django (runserver) o imports repetidos
    # - En runserver, RUN_MAIN=="true" es el proceso real.
    if os.environ.get("RUN_MAIN") not in (None, "true"):
        logger.info("Saltando start_opc_async() en proceso de autoreload")
        return

    if os.environ.get("ENABLE_BACKGROUND_TASKS", "true").lower() not in ("1", "true", "yes", "on"):
        logger.info("ENABLE_BACKGROUND_TASKS desactivado; no se inicia OPC en segundo plano")
        return

    global _opc_started
    with _opc_start_lock:
        if _opc_started:
            logger.info("start_opc_async() ya fue ejecutado; no se crean más hilos")
            return
        _opc_started = True

    shared: Dict[str, Optional[Dict[str, str]]] = {"sensores": None}
    shared_lock = threading.Lock()

    def run_sensores():
        while True:
            nuevos = obtener_variables()
            with shared_lock:
                shared["sensores"] = nuevos
            logger.info("Variables actualizadas")
            time.sleep(60)  # espera 1 minuto

    def run_opc():
        logger.info("Iniciando OPC ASÍNCRONO...")
        _opc_persistent_loop(
            shared=shared,
            shared_lock=shared_lock,
            intervalo=float(INTERVALO_OPC_SEGUNDOS),
            intentos=1,
            intervalo_reintento=1.0,
        )

    # Lanzar hilo para OPC
    threading.Thread(target=run_opc, name="OPC-Async", daemon=True).start()
    logger.info("OPC ASÍNCRONO lanzado")

    # Lanzar hilo para Sensores
    threading.Thread(target=run_sensores, name="Sensores-Reader", daemon=True).start()
    logger.info("Lectura de variables cada 1 minuto lanzada")


