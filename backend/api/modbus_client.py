"""Cliente Modbus TCP asíncrono.

Este módulo implementa:
- Decodificación de registros Modbus según el tipo de variable.
- Lectura asíncrona por bloques para eficiencia (reduce round-trips).
- Registro de mediciones en InfluxDB (`Energia` y acumuladores).
- Arranque en background (threads) mediante `start_modbus_async()`.

La lista de variables se obtiene desde la API (`/variables/`) usando `POSTGRES_URL`.
"""

import time
import threading
import os

import struct
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
# api/modbus_async.py
import asyncio
import struct

from typing import Dict, Any, List, Tuple

from pymodbus.client import AsyncModbusTcpClient
from asgiref.sync import sync_to_async
from django.db import close_old_connections

import logging
logger = logging.getLogger("estado_equipos")

from api.influx_tools import registrar_acumulador
from api.influx_tools import EnergyMeterAccumulator


import environ

# Initialise environment variables
env = environ.Env()
environ.Env.read_env()
INTERVALO_MODBUS_SEGUNDOS = env.int("INTERVALO_MODBUS_SEGUNDOS", default=5)

_modbus_start_lock = threading.Lock()
_modbus_started = False

# Persistencia de acumuladores por equipo.
# Importante: NO debe estar dentro de registrar_medicion_safe(), o se reinicia cada ciclo.
_energy_meters: Dict[str, EnergyMeterAccumulator] = {}
_energy_meters_lock = threading.Lock()
# =============================================================================
# LECTURA FINAL
# =============================================================================
def size_for_type(tipo: str) -> int:
    """Devuelve el número de registros (16-bit) que ocupa un tipo Modbus."""
    if tipo == "INT64":
        return 4
    elif tipo == "FLOAT32":
        return 2
    elif tipo == "4Q_FP_PF":
        return 1   # ocupa un solo registro de 16 bits
    else:
        return 1

def decode_value(tipo: str, regs: list[int]):
    """Decodifica una lista de registros Modbus según el tipo.

    Args:
        tipo: tipo lógico (ej. FLOAT32, INT64, 4Q_FP_PF).
        regs: lista de enteros (registros 16-bit) ya leídos.

    Returns:
        Valor decodificado (float/int/str) o None si no se puede.
    """
    try:
        if tipo == "INT64" and len(regs) >= 4:
            return (regs[0] << 48) | (regs[1] << 32) | (regs[2] << 16) | regs[3]

        elif tipo == "FLOAT32" and len(regs) >= 2:
            combined = (regs[0] << 16) | regs[1]
            return struct.unpack(">f", combined.to_bytes(4, "big"))[0]

        elif tipo == "4Q_FP_PF" and len(regs) >= 1:
            code = regs[0]
            # Si quieres ver el código crudo:
            # return code
            # O si prefieres mapear:
            if code == 65472: return -1 #Error o vacio
            elif code == 0: return 0 #PF = 0
            elif code == 1: return 1 #Inductivo
            elif code == 2: return 2 #Capacitivo
            else: return f"Code {code}"

        elif len(regs) >= 1:
            return regs[0]


        elif len(regs) >= 1:
            return regs[0]

    except Exception as e:
        logger.debug(f"Error decodificando {tipo}: {e}")
    return None





async def leer_equipo_async(nombre: str, ip: str, id_modbus: int, variables: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Lee un equipo vía Modbus TCP asíncrono y devuelve datos como dict.
    Agrupa variables en bloques para eficiencia.
    """
    datos = {var["nombre"]: None for var in variables}
    # Convertir registros a enteros y ordenar
    variables_sorted = sorted(variables, key=lambda v: int(v["registro"]))
    # Agrupar en bloques
    bloques = []
    bloque_actual = []
    max_gap = 20   # máximo salto permitido entre registros dentro de un bloque
    max_block_size = 50  #  máximo tamaño de bloque

    for var in variables_sorted:
        reg = int(var["registro"])
        if not bloque_actual:
            bloque_actual.append(var)
        else:
            last_reg = int(bloque_actual[-1]["registro"])
            if reg - last_reg <= max_gap and len(bloque_actual) < max_block_size:
                bloque_actual.append(var)
            else:
                bloques.append(bloque_actual)
                bloque_actual = [var]
    if bloque_actual:
        bloques.append(bloque_actual)

    client = AsyncModbusTcpClient(ip, port=502, timeout=5.0, retries=1)
    try:
        if not await client.connect():
            logger.warning(f"[{nombre}] Sin conexión a {ip}")
            return {"equipo": nombre, "ip": ip, "datos": datos, "success": False}

        # Leer cada bloque
        for bloque in bloques:
            # ajustar base-1 → base-0
            start = int(bloque[0]["registro"]) - 1
            end   = int(bloque[-1]["registro"]) - 1

            # calcular tamaño real del bloque
            max_reg = max(int(v["registro"]) - 1 + size_for_type(v["tipo"]) for v in bloque)
            min_reg = min(int(v["registro"]) - 1 for v in bloque)
            count   = (max_reg - min_reg) + 2

            try:
                result = await client.read_holding_registers(address=min_reg, count=count, device_id=id_modbus)
                if result.isError():
                    logger.debug(f"[{nombre}] Bloque {min_reg}-{max_reg} no disponible")
                    continue

                # Mapear variables dentro del bloque
                for var in bloque:
                    reg  = int(var["registro"]) - 1  # base-0
                    tipo = var["tipo"]
                    size = size_for_type(tipo)
                    offset = reg - min_reg

                    raw = result.registers[offset:offset+size]
                    valor = decode_value(tipo, raw)

                    datos[var["nombre"]] = valor

            except Exception as e:
                logger.debug(f"[{nombre}] Error leyendo bloque {min_reg}-{max_reg}: {e}")


        return {"equipo": nombre, "ip": ip, "datos": datos, "success": True}

    except Exception as e:
        logger.error(f"[{nombre}] Error general: {e}")
        return {"equipo": nombre, "ip": ip, "datos": datos, "success": False}
    finally:
        client.close() 

# =============================================================================
# ORM SEGURO
# =============================================================================
@sync_to_async
def get_equipos_online() -> List[Tuple[str, str, int]]:
    """Devuelve (nombre, ip, id_modbus) de equipos con estado Online."""
    from api.models import Equipo
    return list(Equipo.objects.filter(estado="Online").values_list("nombre", "ip", "id_modbus"))

# @sync_to_async
# def registrar_medicion_safe(equipo: str, datos: Dict[str, Any], timestamp: str):
#     from api.influx_tools import registrar_medicion  
#     registrar_medicion(equipo, datos, timestamp)

@sync_to_async
def registrar_medicion_safe(equipo: str, datos: Dict[str, Any], timestamp: str):
    """Registra una medición de energía en InfluxDB (y acumuladores).

    Se llama desde el loop asíncrono pero ejecuta IO sin bloquear el event loop
    gracias a `sync_to_async`.
    """
    from api.influx_tools import registrar_medicion

    # Extraer la variable de consumo actual
    consumo_actual = datos.get("Active Energy Delivered (Into Load)", 0)

    # Crear/reusar acumulador persistente por equipo
    with _energy_meters_lock:
        meter = _energy_meters.get(equipo)
        if meter is None:
            meter = EnergyMeterAccumulator(equipo)
            _energy_meters[equipo] = meter

    # Procesar dato con la clase (el objeto mantiene estado entre ciclos)
    resultado = meter.process(consumo_actual)

    #Fusionar los diccionarios: mantener todas las variables originales + las nuevas métricas
    # datos_combinados = {**datos, **resultado} 

    # Registrar en InfluxDB
    registrar_medicion(equipo, datos, timestamp)
    registrar_acumulador(equipo, resultado, timestamp)

    return datos



# =============================================================================
# CICLO PRINCIPAL
# =============================================================================
async def ciclo_modbus_async_all(variables=None):
    """Ciclo único: lee todos los equipos Online y registra mediciones en Influx."""
    equipos = await get_equipos_online()
    if not equipos:
        logger.info("No hay equipos online")
        return

    logger.info(f"Leyendo {len(equipos)} equipos...")
    tareas = [leer_equipo_async(n, ip, id_modbus, variables=variables) for n, ip, id_modbus in equipos]
    resultados = await asyncio.gather(*tareas)
    exitosos = [r for r in resultados if r["success"]]
    logger.info(f"Modbus: {len(exitosos)}/{len(equipos)} leídos correctamente")
    # Guardar en DB
    await asyncio.gather(*[
        registrar_medicion_safe(r["equipo"], r["datos"],
            datetime.now(ZoneInfo("America/Bogota")).isoformat())
        for r in exitosos
    ], return_exceptions=True)

    close_old_connections()



def obtener_variables():
    """Obtiene el catálogo de variables.

    IMPORTANTE: antes hacía un `requests.get` hacia el mismo backend, lo cual puede
    bloquear el servidor (auto-llamada) y generar picos de CPU/colas de requests.
    Preferimos el ORM; dejamos fallback HTTP por compatibilidad.
    """
    # 1) ORM (rápido, sin red)
    try:
        from api.models import Variable
        data = list(Variable.objects.all().values("nombre", "registro", "tipo"))
        return data
    except Exception as e:
        logger.warning("No se pudo obtener variables por ORM; usando fallback HTTP: %s", e)

    # 2) Fallback HTTP
    try:
        url = env("POSTGRES_URL") + "variables/"
        response = requests.get(url, timeout=(3, 10))
        if response.status_code == 200:
            return response.json()
        logger.error("Error en respuesta HTTP variables: %s", response.status_code)
        return None
    except Exception as e:
        logger.error("Excepción al obtener variables (HTTP): %s", e, exc_info=True)
        return None


# =============================================================================
# BUCLE + INICIO
# =============================================================================
async def modbus_async_forever(intervalo: int = INTERVALO_MODBUS_SEGUNDOS,variables=None):
    """Loop infinito: ejecuta `ciclo_modbus_async_all()` cada `intervalo` segundos."""
    if variables is None:
        logger.error("Variables no proporcionadas para modbus_async_forever")
        return
    logger.info("MODBUS ASÍNCRONO INICIADO (UNIVERSAL 2025)")
    while True:
        try:
            await ciclo_modbus_async_all(variables=variables)
        except Exception as e:
            logger.error(f"Error en bucle: {e}", exc_info=True)
        await asyncio.sleep(intervalo)


def start_modbus_async():
    """Arranca hilos daemon:

    - Un hilo refresca el catálogo de variables cada 60s.
    - Otro hilo corre el loop Modbus (asyncio) con el catálogo actual.
    """
    # Evitar doble arranque por autoreload de Django (runserver) o imports repetidos
    if os.environ.get("RUN_MAIN") not in (None, "true"):
        logger.info("Saltando start_modbus_async() en proceso de autoreload")
        return

    if os.environ.get("ENABLE_BACKGROUND_TASKS", "true").lower() not in ("1", "true", "yes", "on"):
        logger.info("ENABLE_BACKGROUND_TASKS desactivado; no se inicia Modbus en segundo plano")
        return

    global _modbus_started
    with _modbus_start_lock:
        if _modbus_started:
            logger.info("start_modbus_async() ya fue ejecutado; no se crean más hilos")
            return
        _modbus_started = True

    shared = {"variables": None}   #  contenedor compartido

    def run_variables():
        while True:
            shared["variables"] = obtener_variables()
            logger.info("Variables actualizadas")
            time.sleep(60)  # espera 1 minuto

    def run_modbus():
        while True:
            vars_actuales = shared["variables"]
            if vars_actuales is None:
                logger.warning("Variables aún no disponibles")
                time.sleep(5)
                continue

            # `modbus_async_forever` es un loop infinito. Si llega a retornar,
            # reiniciamos luego de una espera corta.
            asyncio.run(modbus_async_forever(intervalo=INTERVALO_MODBUS_SEGUNDOS, variables=vars_actuales))
            time.sleep(2)

    # Lanzar hilo para Modbus
    threading.Thread(target=run_modbus, name="Modbus-Async", daemon=True).start()
    logger.info("Modbus ASÍNCRONO lanzado")

    # Lanzar hilo para Variables
    threading.Thread(target=run_variables, name="Variables-Reader", daemon=True).start()
    logger.info("Lectura de variables cada 1 minuto lanzada")

