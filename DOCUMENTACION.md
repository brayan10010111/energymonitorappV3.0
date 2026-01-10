# EnergyMonitorApp V3.0 — Documentación

## 1) Descripción general
Aplicación web para monitoreo y analítica de consumo de energía.

- **Frontend**: React + Vite (carpeta `frontend/`).
- **Backend**: Django + Django REST Framework (carpeta `backend/`).
- **Base de datos relacional**: Postgres (configurado en `backend/core/settings.py`).
- **Series temporales**: InfluxDB (consultas y escritura desde el backend).
- **Tiempo real**: SSE (Server-Sent Events) desde Django hacia el frontend (endpoints async). En Docker el backend corre con **Daphne/ASGI**.
- **Adquisición**:
  - **Modbus TCP**: lectura asíncrona de equipos (medidores) y escritura a Influx.
  - **OPC UA**: lectura asíncrona de sensores y escritura a Influx.

## 2) Arquitectura (alto nivel)

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

## 3) Variables de entorno relevantes

### Frontend (Vite)
Actualmente el frontend **no** usa `VITE_API_URL`.

- La función `getApiUrl()` (en `frontend/src/db/db.tsx`) construye la URL como `http://{window.location.hostname}:8000`.
  - Ejemplo: si abres el frontend en `http://localhost:3000`, las llamadas irán a `http://localhost:8000`.
  - En Docker funciona igual porque el navegador también ve `localhost` (puerto 8000 publicado por el contenedor backend).

Si en algún momento necesitas apuntar a un backend en otra URL/puerto, hay dos caminos:
- Ajustar `getApiUrl()`.
- O reintroducir `VITE_API_URL` y hacer que `getApiUrl()` la priorice.

### Backend (Django + servicios)
- InfluxDB:
  - `INFLUX_URL`
  - `INFLUX_TOKEN`
  - `INFLUX_ORG`
  - `INFLUX_TIMEOUT_MS` (opcional, default `10000`)

- Postgres (Django ORM):
  - `POSTGRES_DB`
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
  - `POSTGRES_HOST` (en Docker: `dbPostgres`; local: `localhost`)
- Intervalos (segundos):
  - `INTERVALO_REFRESCO` (SSE / actualización de gráficas)
  - `INTERVALO_MODBUS_SEGUNDOS` (loop Modbus)
  - `INTERVALO_OPC_SEGUNDOS` (loop OPC)

- Tareas de background:
  - `ENABLE_BACKGROUND_TASKS` (opcional, default `true`): permite desactivar los loops Modbus/OPC/keepalive en un proceso.

- `POSTGRES_URL` (nombre histórico): en este proyecto se usa como **URL base del backend** para que los hilos de Modbus/OPC consulten catálogos (`variables/` y `sensores/`) vía HTTP.
  - Ejemplo local: `http://localhost:8000/api/`
  - Ejemplo Docker: `http://backend:8000/api/`

## 4) Backend (Django)

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

## 5) Frontend (React)

### API client (frontend/src/db/db.tsx)
- Resuelve URL base con `window.location.hostname` (forma `http://{hostname}:8000`).
- Nota: `VITE_API_URL` no se usa actualmente.
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
- Los hilos de background (Modbus/OPC/keepalive) se ejecutan dentro del proceso Django; si se despliega con múltiples workers, puede iniciar múltiples loops.
  - Para mitigar esto existe `ENABLE_BACKGROUND_TASKS=false` (por ejemplo, para un proceso “solo API”).

## 7) Puesta en marcha

### Opción A — Docker Compose (recomendado)

Requisitos:
- Docker Desktop (Windows).

1) Crea un archivo `.env` en la raíz del repo (misma carpeta que `docker-compose.yml`).

Tip: puedes partir de `.env.example` copiándolo a `.env` y ajustando valores.

Variables mínimas sugeridas (ajusta valores):

```env
# --- Django ---
SECRET_KEY_DJANGO=dev-secret
DEBUG_DJANGO=true

# Listas tipo "a,b,c" o JSON-like según tu configuración (django-environ)
ALLOWED_HOSTS_DEV=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS_DEV=http://localhost:3000
CORS_ORIGIN_WHITELIST_DEV=http://localhost:3000
CSRF_TRUSTED_ORIGINS_DEV=http://localhost:3000
CORS_ALLOW_METHODS_DEV=GET,POST,PUT,PATCH,DELETE,OPTIONS

# --- Postgres (Django ORM) ---
POSTGRES_DB=energymonitor
POSTGRES_USER=energymonitor
POSTGRES_PASSWORD=energymonitor
POSTGRES_HOST=dbPostgres

# --- InfluxDB (servicio) ---
INFLUXDB_ADMIN_USER=admin
INFLUXDB_ADMIN_PASSWORD=adminadmin
INFLUX_ORG=EnergyOrg
INFLUX_BUCKET=Energia

# --- InfluxDB (cliente backend) ---
INFLUX_URL=http://dbInflux:8086
INFLUX_TOKEN=PEGA_AQUI_TU_TOKEN
INFLUX_ORG=EnergyOrg

# --- Loops/tiempo real ---
INTERVALO_REFRESCO=1
INTERVALO_MODBUS_SEGUNDOS=5
INTERVALO_OPC_SEGUNDOS=5
ENABLE_BACKGROUND_TASKS=true

# --- URL base del backend para hilos (nombre histórico) ---
POSTGRES_URL=http://backend:8000/api/
```

2) Levanta servicios:

- `docker compose up --build`

3) Ejecuta migraciones y crea superusuario:

- `docker compose exec backend python manage.py migrate`
- `docker compose exec backend python manage.py createsuperuser`

4) URLs útiles:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000/api/`
- Admin: `http://localhost:8000/admin/`
- Influx UI: `http://localhost:8086`

Notas importantes:
- El contenedor Influx inicializa **un** bucket (el que pongas en `INFLUX_BUCKET`). El código del backend usa **tres** buckets fijos: `Energia`, `Acumuladores`, `Sensores`. Crea los buckets faltantes en la UI de Influx o ajusta el código.
- El backend en Docker corre con `daphne ... core.asgi:application`.

### Opción B — Ejecución local (Windows)

Requisitos sugeridos:
- Python 3.11+.
- Node.js 22+.

Backend:
1) (Opcional) crea venv y activa.
2) Instala dependencias (hay wheels locales en `backend/packages/` para instalación offline):
   - `pip install -r backend/requirements.txt --find-links backend/packages`
3) Define variables de entorno (mínimo Postgres + Django + Influx).
4) Migra y ejecuta:
   - `python backend/manage.py migrate`
   - `python backend/manage.py runserver 0.0.0.0:8000`

Frontend:
1) `cd frontend`
2) `npm install`
3) `npm run dev` (por configuración, corre en `http://localhost:3000`)

## 8) Troubleshooting (rápido)

- Backend no conecta a Postgres: revisa `POSTGRES_HOST`.
  - Docker: `dbPostgres`.
  - Local: `localhost`.
- Influx responde pero no hay datos/buckets: crea `Energia`, `Acumuladores`, `Sensores` en Influx.
- Doble ingesta (valores duplicados): suele ser porque arrancaste múltiples procesos con tareas de background.
  - Solución: en procesos secundarios usa `ENABLE_BACKGROUND_TASKS=false`.
- SSE se corta detrás de proxy: asegúrate de permitir conexiones persistentes, desactivar buffering y aumentar timeouts.

