"""Arranque diferido de tareas de background.

Este módulo se invoca desde `api.apps.ApiConfig.ready()` para iniciar
procesos/hilos de larga duración una vez Django está inicializado.

Tareas que se levantan:
- Lectura Modbus asíncrona (threads + asyncio) para registrar mediciones.
- Lectura OPC UA asíncrona para registrar sensores.
- Keepalive / monitoreo de equipos (actualiza `estado` en DB).
"""

import threading
import time
import os

from django.db import close_old_connections

import logging
logger = logging.getLogger("estado_equipos")


_start_lock = threading.Lock()
_started = False


def iniciar_monitoreo_diferido():
    """Inicia un hilo daemon que arranca tareas de monitoreo tras un retardo.

    El retardo evita errores típicos cuando Django aún está cargando apps/ORM.
    Retorna el objeto `Thread` para observabilidad/testing.
    """
    def worker():
        logger.info("Iniciando hilo de monitoreo en segundo plano...")
        time.sleep(3)  # Espera a que Django termine de inicializarse

        # Importamos aquí DENTRO del hilo para evitar problemas de inicialización
        try:
            from api.modbus_client import start_modbus_async
            from api.keepalive import monitoreo_continuo
            from api.opc_datos import start_opc_async
            logger.info("Módulos importados correctamente en el hilo")
        except Exception as e:
            logger.error(f"Error importando módulos en hilo: {e}")
            return

        # Iniciamos Modbus una sola vez
        try:
            start_modbus_async()
            logger.info("Modbus threads iniciados")
        except Exception as e:
            logger.error(f"Error iniciando Modbus: {e}")

        try:
            start_opc_async()
            logger.info("OPC threads iniciados")
        except Exception as e:
            logger.error(f"Error iniciando OPC: {e}")

        # Bucle principal: reintenta cada 60s si falla
        while True:
            try:
                logger.info("Iniciando ciclo de monitoreo_continuo()...")
                
                # ¡IMPORTANTE! Cerramos conexiones viejas antes de usar ORM en hilo largo
                close_old_connections()
                
                monitoreo_continuo()  # Esta función YA tiene su propio while True con sleep
                
                # Si llegas aquí → monitoreo_continuo() terminó (raro, solo si lo modificaste)
                logger.warning("monitoreo_continuo() terminó inesperadamente. Reiniciando en 10s...")
                time.sleep(10)

            except Exception as e:
                logger.error(f"Error crítico en monitoreo continuo: {e}")
                import traceback
                traceback.print_exc()
                
                # No mueras nunca: reintenta cada minuto
                logger.info("Reintentando monitoreo en 60 segundos...")
                time.sleep(60)

            finally:
                close_old_connections()  # Siempre cerrar conexiones

    # Hilo daemon + nombre para debug
    # Permite desactivar explícitamente tareas de background en procesos web.
    # Útil cuando se corre con múltiples workers (gunicorn/daphne/uvicorn) para evitar duplicados.
    if os.environ.get("ENABLE_BACKGROUND_TASKS", "true").lower() not in ("1", "true", "yes", "on"):
        logger.info("ENABLE_BACKGROUND_TASKS desactivado; no se inician tareas en segundo plano")
        return None

    # En `runserver` Django crea 2 procesos (reloader + proceso real).
    if os.environ.get("RUN_MAIN") not in (None, "true"):
        logger.info("Saltando iniciar_monitoreo_diferido() en proceso de autoreload")
        return None

    global _started
    with _start_lock:
        if _started:
            logger.info("iniciar_monitoreo_diferido() ya fue ejecutado; no se crean más hilos")
            return None
        _started = True

    thread = threading.Thread(target=worker, name="Monitoreo-KeepAlive", daemon=True)
    thread.start()
    logger.info("Hilo de monitoreo iniciado correctamente (daemon)")
    return thread