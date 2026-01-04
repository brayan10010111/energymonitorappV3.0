import time

from concurrent.futures import ThreadPoolExecutor, as_completed
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
INTERVALO_SEGUNDOS = 5
MAX_THREADS = 100                  # Threads para chequeo paralelo
MODBUS_TIMEOUT = 2                 # 2 segundos máximo por conexión Modbus
CACHE_TIEMPO_ESTADO = {}           # Cache opcional para evitar spam en logs
# =========================================================

import logging
logger = logging.getLogger("estado_equipos")


# Pool global reutilizable (¡lo más importante!)
executor = ThreadPoolExecutor(max_workers=MAX_THREADS)

def verificar_equipo_modbus(equipo_id: int, ip: str, id_modbus: int) -> Tuple[int, str]:
    """
    Verifica el estado de un equipo usando comunicación Modbus TCP.
    Intenta leer un registro para confirmar que el dispositivo responde.
    
    Args:
        equipo_id: ID del equipo en la base de datos
        ip: Dirección IP del equipo
        id_modbus: ID Modbus del equipo (slave/unit ID)
    
    Returns:
        Tuple con (equipo_id, estado) donde estado es "Online", "Offline" o "Error"
    """
    
    client = ModbusTcpClient(ip, port=502, timeout=MODBUS_TIMEOUT, retries=1)
    try:
        # Intentar conectar al dispositivo
        if not client.connect():
            return equipo_id, "Offline"
        
        # Intentar leer un registro (dirección 0, 1 registro) con el ID Modbus específico
        # Esto confirmará que el dispositivo con ese ID está respondiendo
        result = client.read_holding_registers(address=0, count=1, device_id=id_modbus)
        
        if result.isError():
            # El dispositivo respondió pero hubo un error (posiblemente registro inválido)
            # Intentamos con otro método: leer coils
            result = client.read_coils(address=0, count=1, device_id=id_modbus)
            
            if result.isError():
                # Si ambos fallan, consideramos offline
                estado = "Offline"
            else:
                # Si al menos uno funciona, está online
                estado = "Online"
        else:
            # Lectura exitosa
            estado = "Online"
            
    except Exception as e:
        logging.debug(f"Error verificando equipo {equipo_id} (IP: {ip}, Modbus ID: {id_modbus}): {e}")
        estado = "Error"
    finally:
        try:
            client.close() 
        except:
            pass
    
    return equipo_id, estado


@transaction.atomic
def actualizar_estados_en_db(resultados: List[Tuple[int, str]]):
    """Actualiza estados usando el ID del equipo (no por IP)."""
    equipo_ids = [equipo_id for equipo_id, _ in resultados]
    existentes = Equipo.objects.filter(id__in=equipo_ids).in_bulk()  # {id: objeto}

    a_actualizar = []
    for equipo_id, estado in resultados:
        equipo = existentes.get(equipo_id)
        if not equipo:
            continue

        if equipo.estado != estado:
            equipo.estado = estado
            equipo.ultima_actualizacion = datetime.now()
            a_actualizar.append(equipo)

    if a_actualizar:
        Equipo.objects.bulk_update(a_actualizar, ['estado', 'ultima_actualizacion'])

    logging.info(f"DB actualizada: {len(a_actualizar)} equipos modificados")


def escanear_y_actualizar(equipos: List[Equipo]):
    """Chequeo paralelo por Modbus (IP + id_modbus) + actualización masiva en DB."""
    if not equipos:
        return

    inicio = time.time()
    actualizaciones: List[Tuple[int, str]] = []

    futures = {
        executor.submit(verificar_equipo_modbus, eq.id, eq.ip, eq.id_modbus): eq
        for eq in equipos
        if eq.ip
    }

    for future in as_completed(futures, timeout=len(futures) * 0.5 + 10):
        equipo = futures[future]
        equipo_id, estado = future.result()
        actualizaciones.append((equipo_id, estado))

        cache_key = f"{equipo.ip}:{equipo.id_modbus}"
        if CACHE_TIEMPO_ESTADO.get(cache_key) != estado:
            # logging.info(f"{equipo.nombre} ({equipo.ip}:{equipo.id_modbus}) | {estado}")
            CACHE_TIEMPO_ESTADO[cache_key] = estado

    try:
        actualizar_estados_en_db(actualizaciones)
    except OperationalError:
        time.sleep(1)
        actualizar_estados_en_db(actualizaciones)

    vivos = sum(1 for _, estado in actualizaciones if estado == "Online")
    logger.info(
        f"[{time.strftime('%H:%M:%S')}] Verificados {len(futures)} equipos Modbus | "
        f"{vivos} Online | {time.time() - inicio:.2f}s"
    )


def monitoreo_continuo():
    """Bucle principal optimizado (estado por Modbus, no por IP)."""
    logger.info("Iniciando monitoreo de equipos Modbus cada %s segundos...", INTERVALO_SEGUNDOS)
    
    while True:
        try:
            equipos = listar_equipos_desde_db()  # Refresca la lista cada vez
            if equipos:
                escanear_y_actualizar(list(equipos))
            else:
                logger.info("No hay equipos configurados en la DB")

            # Sleep preciso (compensa tiempo de ejecución)
            time.sleep(max(0.1, INTERVALO_SEGUNDOS - 0.5))

        except KeyboardInterrupt:
            logger.info("Deteniendo monitoreo...")
            break
        except Exception as e:
            logger.error(f"Error en bucle principal: {e}")
            time.sleep(5)


