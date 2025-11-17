import threading
import time

def iniciar_monitoreo_diferido():
    def delayed_start():
        time.sleep(2)  # Espera a que Django esté completamente listo
        try:
            from api.modbus_client import start_modbus_threads
            from api.keepalive import equipos_alive
            from api.opc_datos import listar_equipos_desde_db

            print("Iniciando monitoreo...")
            start_modbus_threads()
            equipos = listar_equipos_desde_db()
            if equipos:
                print("Equipos detectados, iniciando keepalive...")
                equipos_alive(equipos)
            else:
                print("No hay equipos online.")
        except Exception as e:
            import traceback
            print(f"Error en monitoreo diferido: {e}")
            traceback.print_exc()

    threading.Thread(target=delayed_start, daemon=True).start()