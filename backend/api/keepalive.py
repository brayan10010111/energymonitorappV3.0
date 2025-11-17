import subprocess
import platform
import time
import logging
import os
import django
from concurrent.futures import ThreadPoolExecutor

from api.opc_datos import listar_equipos_desde_db
from .models import Equipo


# Inicializa Django
#os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tu_proyecto.settings")
#django.setup()


# Configuración
INTERVALO_SEGUNDOS = 2
MAX_THREADS = 2

# Logging
logging.basicConfig(filename="estado_equipos.log", level=logging.INFO)

def ping_equipo(ip):
    sistema = platform.system().lower()
    
    if sistema == "windows":
        comando = ["ping", "-n", "1", "-w", "1000", ip]
    else:
        # Usa solo opciones compatibles sin requerir privilegios
        comando = ["ping", "-c", "1", ip]

    # print("Ejecutando:", " ".join(comando))
    
    try:
        resultado = subprocess.run(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        estado = "Online" if resultado.returncode == 0 else "Offline"
    except Exception as e:
        # print("Error al ejecutar ping:", e)
        estado = "Error"


    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"{timestamp} | {ip} | {estado}")

    # Actualiza o crea registro en PostgreSQL vía Django ORM
    Equipo.objects.update_or_create(
        ip=ip,
        defaults={"estado": estado}
    )

    return ip, estado

def escanear_equipos(equipos):
    ips = [equipo.ip for equipo in equipos]  # extrae las IPs
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        resultados = list(executor.map(ping_equipo, ips))
    # print("Estado actual:", resultados)


def equipos_alive(equipos):
    while True:
        equipo = equipos
        escanear_equipos(equipo)
        time.sleep(INTERVALO_SEGUNDOS)
