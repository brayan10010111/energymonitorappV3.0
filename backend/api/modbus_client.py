import time
import threading
import logging
import struct
from datetime import datetime, timezone
from pyModbusTCP.client import ModbusClient
from django.db import connection
from .influx_tools import registrar_medicion
from api.opc_datos import get_equipos_desde_db

logger = logging.getLogger(__name__)

def read_float32(client, address):
    regs = client.read_holding_registers(address - 1, 2)
    if regs is None:
        return 0.0
    raw = struct.pack(">HH", regs[0], regs[1])
    return struct.unpack(">f", raw)[0]
from zoneinfo import ZoneInfo
def ciclo_modbus(nombre, ip):
    client = ModbusClient(host=ip, port=502, unit_id=1, auto_open=True)
    while True:
        voltages = {
            "A-B": read_float32(client, 3020),
            "B-C": read_float32(client, 3022),
            "C-A": read_float32(client, 3024),
            "L-L Avg": read_float32(client, 3026),
            "A-N": read_float32(client, 3028),
            "B-N": read_float32(client, 3030),
            "C-N": read_float32(client, 3032),
            "L-N Avg": read_float32(client, 3036),
        }
        registrar_medicion(
            nombre,
            voltages,
            datetime.now(ZoneInfo("America/Bogota")).isoformat(),
        )
        time.sleep(5)

MAX_THREADS = 4
semaforo = threading.Semaphore(MAX_THREADS)



def ciclo_modbus_con_limite(nombre, ip):
    with semaforo:
        ciclo_modbus(nombre, ip)

def start_modbus_threads():
    equipos = get_equipos_desde_db()
    # print("Equipos obtenidos:", equipos)
    for equipo in equipos:
        t = threading.Thread(
            target=ciclo_modbus_con_limite,
            args=(equipo.nombre, equipo.ip),
            daemon=True
        )
        t.start()
