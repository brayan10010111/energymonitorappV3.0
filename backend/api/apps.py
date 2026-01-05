"""Configuración de la app Django `api`.

Este módulo aprovecha `AppConfig.ready()` para iniciar tareas de fondo
(hilos/loops) una sola vez cuando Django termina de cargar la app.

Las tareas de fondo se delegan a `api.signals.iniciar_monitoreo_diferido()`.
"""

from django.apps import AppConfig
import threading
import logging
logger = logging.getLogger("estado_equipos")



class ApiConfig(AppConfig):
    """Configura la app y dispara tareas de background al arrancar."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        """Hook de Django al cargar la app.

        Garantiza que el arranque ocurra:
        - solo una vez por proceso
        - solo en el hilo principal
        """
        # Ejecutar solo una vez, solo en el hilo principal
        if getattr(self, "_ready_called", False):
            return
        self._ready_called = True

        if threading.current_thread() is not threading.main_thread():
            return

        # Importamos aquí para evitar import loops
        try:
            from api.signals import iniciar_monitoreo_diferido
            iniciar_monitoreo_diferido()
        except ImportError as e:
            logger.error(f"No se pudo importar iniciar_monitoreo_diferido: {e}")
        except Exception as e:
            logger.error(f"Error iniciando tareas en segundo plano: {e}")
            import traceback
            traceback.print_exc()