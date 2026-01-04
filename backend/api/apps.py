# api/apps.py
from django.apps import AppConfig
import threading
import logging
logger = logging.getLogger("estado_equipos")



class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
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