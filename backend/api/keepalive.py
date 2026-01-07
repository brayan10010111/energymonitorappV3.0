"""
Keepalive/monitoreo de equipos Modbus.

Este módulo mantiene actualizado el campo `estado` de los equipos en la DB:
- Verifica conectividad Modbus TCP contra (IP, id_modbus).
- Ejecuta chequeos en paralelo con `ThreadPoolExecutor`.
- Aplica cambios en lote usando `bulk_update` para eficiencia.

Usualmente se ejecuta como tarea de background (ver `api.signals`).
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import List, Tuple
from datetime import datetime, timezone

import django
import os
from django.db import transaction, OperationalError

# Configuración Django (descomenta cuando lo ejecutes fuera de Django)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from api.opc_datos import listar_equipos_desde_db
from .models import Equipo
from pymodbus.client import ModbusTcpClient

# ===================== CONFIGURACIÓN =====================
INTERVALO_SEGUNDOS = 8        # Cada cuánto tiempo chequear
MAX_THREADS = 20               # Menos threads, más estabilidad Modbus
MODBUS_TIMEOUT = 5             # Timeout por conexión Modbus
CACHE_TIEMPO_ESTADO = {}       # Cache opcional para evitar spam en logs
# =========================================================

import logging
logger = logging.getLogger("estado_equipos")

# Pool global reutilizable
executor = ThreadPoolExecutor(max_workers=MAX_THREADS)


# Pool global de conexiones Modbus reutilizables
CONEXIONES_MODBUS = {}

def obtener_cliente_modbus(ip: str) -> ModbusTcpClient:
    """
    Devuelve un cliente Modbus reutilizable por IP.
    Si la conexión está rota, la reconstruye.
    """
    client = CONEXIONES_MODBUS.get(ip)

    # Si no existe o está cerrado, crear uno nuevo
    if client is None or not client.connected:
        client = ModbusTcpClient(ip, port=502, timeout=MODBUS_TIMEOUT)
        CONEXIONES_MODBUS[ip] = client

    return client


def verificar_equipo_modbus(equipo_id: int, ip: str, id_modbus: int) -> Tuple[int, str]:
    """
    Verifica el estado de un equipo usando Modbus TCP con:
    - Pool de conexiones
    - Reconexión automática
    - Tolerancia a suspensión de red
    """
    estado = "Offline"

    try:
        client = obtener_cliente_modbus(ip)

        # Si Windows suspendió la red, connect() fallará
        if not client.connect():
            return equipo_id, "Offline"

        # Intento principal
        result = client.read_holding_registers(
            address=0, count=1, device_id=id_modbus
        )

        # Si Windows cerró el socket → result = None
        if result is None:
            return equipo_id, "Offline"

        if result.isError():
            # Intento alterno
            result = client.read_coils(
                address=0, count=1, device_id=id_modbus
            )

            if result is None or result.isError():
                estado = "Offline"
            else:
                estado = "Online"
        else:
            estado = "Online"

    except (ConnectionResetError, OSError) as e:
        # Windows suspendió la NIC o cerró sockets
        logger.warning(
            f"Conexión perdida para {equipo_id} ({ip}). "
            f"Windows pudo haber suspendido la red: {e}"
        )

        # Invalida la conexión para que se reconstruya en el próximo ciclo
        if ip in CONEXIONES_MODBUS:
            try:
                CONEXIONES_MODBUS[ip].close()
            except:
                pass
            CONEXIONES_MODBUS[ip] = None

        estado = "Offline"

    except Exception as e:
        logger.error(
            f"Error verificando equipo {equipo_id} (IP: {ip}, Modbus ID: {id_modbus}): {e}"
        )
        estado = "Error"

    return equipo_id, estado


@transaction.atomic
def actualizar_estados_en_db(resultados: List[Tuple[int, str]]):
    """Actualiza estados usando el ID del equipo (no por IP)."""
    if not resultados:
        return

    equipo_ids = [equipo_id for equipo_id, _ in resultados]
    existentes = Equipo.objects.filter(id__in=equipo_ids).in_bulk()  # {id: objeto}

    a_actualizar = []
    ahora = datetime.now(timezone.utc)

    for equipo_id, estado in resultados:
        equipo = existentes.get(equipo_id)
        if not equipo:
            continue

        if equipo.estado != estado:
            equipo.estado = estado
            equipo.ultima_actualizacion = ahora
            a_actualizar.append(equipo)

    if a_actualizar:
        Equipo.objects.bulk_update(a_actualizar, ['estado', 'ultima_actualizacion'])

    logger.info(f"DB actualizada: {len(a_actualizar)} equipos modificados")


from concurrent.futures import wait, ALL_COMPLETED

def escanear_y_actualizar(equipos: List[Equipo]):
    if not equipos:
        return

    inicio = time.time()
    actualizaciones: List[Tuple[int, str]] = []

    futures = {
        executor.submit(verificar_equipo_modbus, eq.id, eq.ip, eq.id_modbus): eq
        for eq in equipos
        if eq.ip
    }

    if not futures:
        logger.info("No hay equipos con IP configurada para verificar.")
        return

    # Timeout global (20 segundos por equipo)
    TIMEOUT_GLOBAL = len(futures) * 20

    # Esperar a que TODOS terminen o expiren
    done, not_done = wait(
        futures.keys(),
        timeout=TIMEOUT_GLOBAL,
        return_when=ALL_COMPLETED
    )

    # Procesar los que terminaron
    for future in done:
        equipo = futures[future]
        try:
            equipo_id, estado = future.result()
        except Exception as e:
            logger.error(f"Future fallido para equipo {equipo.id}: {e}")
            equipo_id, estado = equipo.id, "Error"

        actualizaciones.append((equipo_id, estado))
        CACHE_TIEMPO_ESTADO[f"{equipo.ip}:{equipo.id_modbus}"] = estado

    # Cancelar los que no terminaron
    for future in not_done:
        equipo = futures[future]
        future.cancel()
        logger.error(f"Timeout para equipo {equipo.id} ({equipo.ip}). Cancelado.")
        actualizaciones.append((equipo.id, "Timeout"))
        CACHE_TIEMPO_ESTADO[f"{equipo.ip}:{equipo.id_modbus}"] = "Timeout"

    # Actualizar DB
    if actualizaciones:
        try:
            actualizar_estados_en_db(actualizaciones)
        except OperationalError:
            time.sleep(1)
            actualizar_estados_en_db(actualizaciones)

        vivos = sum(1 for _, estado in actualizaciones if estado == "Online")
        logger.info(
            f"[{time.strftime('%H:%M:%S')}] Verificados {len(actualizaciones)} equipos Modbus | "
            f"{vivos} Online | {time.time() - inicio:.2f}s"
        )
    else:
        logger.warning("No se obtuvo ninguna actualización de estado en este ciclo.")


def monitoreo_continuo():
    """Bucle principal optimizado (estado por Modbus, no por IP)."""
    logger.info("Iniciando monitoreo de equipos Modbus cada %s segundos...", INTERVALO_SEGUNDOS)

    while True:
        ciclo_inicio = time.time()
        try:
            equipos = list(listar_equipos_desde_db())  # forzamos evaluación
            if equipos:
                escanear_y_actualizar(equipos)
            else:
                logger.info("No hay equipos configurados en la DB")

            duracion = time.time() - ciclo_inicio
            sleep_time = max(0.1, INTERVALO_SEGUNDOS - duracion)
            time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Deteniendo monitoreo...")
            break
        except Exception as e:
            logger.error(f"Error en bucle principal: {e}")
            time.sleep(5)