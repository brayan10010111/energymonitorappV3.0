# EnergyMonitorApp V3.0 — Documentación
## Presentación
Este proyecto fue desarrollado por Brayan Rueda Mayorga, Ingeniero Mecatrónico.

En el desarrollo del programa de especialización en Ciencia de Datos de la Universidad Nacional Abierta y a Distancia.

## Esquema de funcionamiento del Sistema
<img width="516" height="517" alt="image" src="https://github.com/user-attachments/assets/2c80d77f-7e08-4376-a6e4-67a2500ecc73" />

## 1) Resumen
Este desarrollo propone una interfaz adaptable y sencilla, capaz de gestionar datos energéticos en tiempo real y de predecir consumos con base a valores de producción. Con ello se busca ofrecer una alternativa más flexible y eficiente frente a las soluciones tradicionales, contribuyendo a la optimización de recursos y a la sostenibilidad industrial.

## 2) Descripción general
Aplicación web para monitoreo y analítica de consumo de energía.

- **Frontend**: React + Vite (carpeta `frontend/`).
- **Backend**: Django + Django REST Framework (carpeta `backend/`).
- **Series temporales**: InfluxDB (consultas y escritura desde el backend).
- **Tiempo real**: SSE (Server-Sent Events) desde Django hacia el frontend.
- **Adquisición**:
  - **Modbus TCP**: lectura asíncrona de equipos (medidores) y escritura a Influx.
  - **OPC UA**: lectura asíncrona de sensores y escritura a Influx.

## 3) Arquitectura (alto nivel)

### Flujo de datos (ingesta)
1. El backend obtiene catálogos desde su propia API:
   - Variables Modbus: `GET /api/variables/`
   - Sensores OPC: `GET /api/sensores/`
2. Procesos de background (hilos) ejecutan bucles:
   - `backend/api/modbus_client.py`: lee Modbus TCP y registra mediciones.
   - `backend/api/opc_datos.py`: lee OPC UA y registra sensores.
   - `backend/api/keepalive.py`: verifica disponibilidad Modbus y actualiza `estado` en DB.
3. Escritura en InfluxDB:
   - Bucket `Energia`: mediciones crudas.
   - Bucket `Acumuladores`: métricas derivadas por minuto/hora.
   - Bucket `Sensores`: mediciones de sensores OPC.

### Flujo de datos (consulta)
- El frontend consume endpoints HTTP del backend para:
  - CRUD de catálogos (equipos, variables, sistemas, etc.).
  - Consultas a Influx (histórico, acumulados, informes).
- Para tiempo real, el frontend abre conexiones SSE a endpoints del backend.

## 4) Variables de entorno relevantes

### Frontend (Vite)
- `VITE_API_URL`: URL base del backend (por defecto `http://localhost:8000`).

### Backend (Django + servicios)
- InfluxDB:
  - `INFLUX_URL`
  - `INFLUX_TOKEN`
  - `INFLUX_ORG`
- Intervalos (segundos):
  - `INTERVALO_REFRESCO` (SSE / actualización de gráficas)
  - `INTERVALO_MODBUS_SEGUNDOS` (loop Modbus)
  - `INTERVALO_OPC_SEGUNDOS` (loop OPC)
- `POSTGRES_URL`: en este proyecto se usa como **URL base del backend** para que los hilos de Modbus/OPC consulten `variables/` y `sensores/` vía HTTP.
  - Ejemplo esperado: `http://localhost:8000/api/`

## 5) Backend (Django)

### Estructura
- `backend/core/`
  - Routing principal y vista que sirve el SPA.
- `backend/api/`
  - Modelos, serializers, viewsets, endpoints, utilidades Influx/Modbus/OPC/predicción.

### Modelos principales (backend/api/models.py)
- **Sistema**: agrupador de equipos/sensores/máquinas.
- **Equipo**: medidor Modbus TCP (unicidad por `ip + id_modbus`).
- **Sensor**: señal OPC UA asociada a un sistema.
- **Variable/Subcategoria**: catálogo de variables Modbus.
- **Maquina**: entidad de negocio asociada a un sistema.

### Endpoints REST (backend/api/views.py + backend/api/urls.py)
CRUD (DRF `ModelViewSet`):
- `GET/POST /api/equipos/`
- `GET/POST /api/variables/`
- `GET/POST /api/subcategorias/`
- `GET/POST /api/maquinas/`
- `GET/POST /api/sistemas/`
- `GET/POST /api/sensores/`

Utilitarios:
- `GET /api/csrf/`: fuerza a setear cookie `csrftoken`.

Influx / reportes:
- `GET /api/get_data_influx?inicio=...&fin=...&medidor=...&variable=...`
- `GET /api/get_acumulados?inicio=...&fin=...&sistema=...`
- `GET /api/get_query_inform?nombreInforme=...&fechaInicio=...&fechaFin=...&equipos=...&variables=...&formato=xlsx|csv`

### Endpoints SSE (tiempo real)
- `GET /api/graficas_update/?medidor=...&variable=...`
  - Emite eventos con `tipo="grafico_actualizado"` y `contenido=[{timestamp, valor}, ...]`.
- `GET /api/graficas_update_sistemas/?sistema=...`
  - Emite `contenido=[{timestamp, valor}]` (valor agregado de sistema).
- `GET /api/stream_predicciones/?sistema=...`
  - Predicciones en tiempo real (actualmente restringido a `AIRE COMPRIMIDO`).
- `GET /api/stream_predicciones_dia/?sistema=...`
  - Emite `total_estimado_kWh` para el día (real + predicción restante).

### Procesos de background
- `backend/api/apps.py` llama a `backend/api/signals.py` en `AppConfig.ready()`.
- `backend/api/signals.py` levanta un hilo daemon que inicia:
  - Modbus (`backend/api/modbus_client.py`)
  - OPC (`backend/api/opc_datos.py`)
  - Keepalive (`backend/api/keepalive.py`)

## 6) Frontend (React)

### API client (frontend/src/db/db.tsx)
- Resuelve URL base con `VITE_API_URL`.
- Maneja CSRF para POST (Django) con cookie `csrftoken`.
- Implementa funciones:
  - CRUD/catálogos: `fetchEquipos`, `fetchVariables`, `fetchSistemas`, etc.
  - Influx: `getInfluxData`, `getAcumulados`
  - SSE: `initSSEConnection`, `initSSEConnectionSistemas`, `initSSEConnectionPredictivo`, `initSSEConnectionPredictivoTodoElDia`

### Páginas
- `Dashboard`: selector de rango de fechas + switch `autorefresh` + gráficas `TimeGraph`.
- `Equipos`: tabla de equipos + modal de creación.
- `Informes`: configuración y descarga de reportes.
- `Predictivo`: selección de sistema + consumo estimado + `GraficoPredictivo`.

### Componentes (frontend/src/components)

Esta sección describe el propósito y comportamiento de los componentes React reutilizables.

- `Grid/Grid.tsx`
  - Contenedor simple de layout responsivo.
  - Renderiza `children` dentro de un `div` con clases CSS para acomodar secciones tipo “cards/gráficas”.

- `Dispositivo/Dispositivo.tsx`
  - Fila de tabla (`<tr>`) para mostrar un **equipo/medidor**.
  - Props principales: `equipo`, `seleccionado`, `onToggle(id)`.
  - Responsabilidad: mostrar atributos del equipo y exponer un checkbox que notifica al padre cuando el usuario selecciona/deselecciona.

- `Modal/Modal.tsx` (ModalFormulario)
  - Modal con formulario controlado para crear un nuevo equipo.
  - Props principales: `onClose()` y `onSubmit({ nombre, modelo, ip, idModbus })`.
  - Flujo: el usuario completa campos → `handleSubmit` llama `onSubmit` → se cierra el modal.
  - El guardado “real” (POST al backend) se hace en el componente padre que reciba `onSubmit`.

- `Sidebar/Sidebar.tsx`
  - Menú lateral de navegación (React Router).
  - Props principales: `collapsed` y `setCollapsed(value)`.
  - Comportamiento responsive:
    - Si `window.innerWidth < BREAKPOINT`, fuerza el colapso.
    - En pantallas grandes permite toggle manual (estado local `isManuallyToggled`).
  - Enlaces: Equipos, Dashboard, Informes, Predictivo.

- `EquiposModal/EquiposModal.tsx`
  - Modal para seleccionar uno o varios equipos/medidores.
  - Props principales: `equipos`, `medidoresSeleccionados`, `toggleMedidor(nombre)`, `toggleTodos()`, `onClose()`.
  - Flujo: el estado de selección vive en el padre; el modal solo renderiza y dispara callbacks.
  - UX: selección por clic en fila o checkbox, contador de seleccionados y acción seleccionar/deseleccionar todos.

- `VariablesModal/VariablesModal.tsx`
  - Modal para seleccionar variables, agrupadas por **subcategoría**.
  - Props principales: `variables`, `subcategorias`, `variablesSeleccionadas`, `toggleVariable(nombre)`, `toggleTodasVariables()`, `onClose()`.
  - Flujo:
    - Agrupa variables por subcategoría (helper `agruparPorSubcategoria`).
    - Maneja expansión/colapso por subcategoría (`subcategoriasAbiertas`).
    - El estado de selección de variables vive en el componente padre.

- `graficoTiempo/TimeGraph.tsx`
  - Gráfica de consumo histórico/tiempo real (Chart.js).
  - Props principales: `rangoFechas` y `autorefresh`.
  - Flujo de datos:
    1) Carga catálogos (equipos y variables) desde el backend.
    2) Consulta histórico a través de `getInfluxData(...)` y normaliza con `procesarDatos(...)`.
    3) Si `autorefresh` está activo, abre SSE (`initSSEConnection`) y mantiene una ventana deslizante de puntos.
    4) Si el usuario apaga `autorefresh`, cierra el `EventSource`.

- `graficoPredictivo/graficoPredictivo.tsx` (GraficoPredictivo)
  - Gráfica predictiva del día completo (1440 puntos: un punto por minuto).
  - Props principales: `estimar` (habilita SSE) y `sistema`.
  - Flujo de datos:
    1) Al cambiar `sistema`, consulta acumulados del día (`getAcumulados`) y los mapea a índice minuto-del-día.
    2) En modo `estimar=true`, abre SSE de predicciones (`initSSEConnectionPredictivo`) para la serie estimada.
    3) También en modo `estimar=true`, abre SSE de sistema (`initSSEConnectionSistemas`) para refrescar la serie real.
    4) Al desactivar `estimar`, cierra el/los `EventSource`.

## 6) Notas operativas
- SSE requiere mantener conexiones HTTP abiertas; revise CORS/headers y proxies.
- Los hilos de background (Modbus/OPC/keepalive) se ejecutan dentro del proceso Django; si se despliega con múltiples workers, puede iniciar múltiples loops. (El código intenta reducir esto ejecutando en el hilo principal, pero depende del modo de despliegue.)

