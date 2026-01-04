import threading
import time

from django.db import close_old_connections

import logging
logger = logging.getLogger("estado_equipos")


def iniciar_monitoreo_diferido():
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
    thread = threading.Thread(target=worker, name="Monitoreo-KeepAlive", daemon=True)
    thread.start()
    logger.info("Hilo de monitoreo iniciado correctamente (daemon)")
    return thread