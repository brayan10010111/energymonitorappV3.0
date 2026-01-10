"""Configuración de conexión a InfluxDB.

Centraliza la construcción del `InfluxDBClient` leyendo variables del `.env`:
- `INFLUX_URL`
- `INFLUX_TOKEN`
- `INFLUX_ORG`
"""

from influxdb_client import InfluxDBClient

import environ

_env = environ.Env()
environ.Env.read_env()

_client: InfluxDBClient | None = None


def get_influx_client() -> InfluxDBClient:
    """Devuelve un cliente InfluxDB singleton.

    Evita crear un nuevo `InfluxDBClient` por request/consulta (costoso y puede
    degradar el rendimiento cuando hay SSE + loops en background).
    """
    global _client
    if _client is not None:
        return _client

    url = _env("INFLUX_URL")
    token = _env("INFLUX_TOKEN")
    org = _env("INFLUX_ORG")
    timeout_ms = _env.int("INFLUX_TIMEOUT_MS", default=10_000)

    if not all([url, token, org]):
        raise ValueError("Faltan variables de entorno para conectar a InfluxDB.")

    _client = InfluxDBClient(
        url=url,
        token=token,
        org=org,
        timeout=timeout_ms,
        enable_gzip=True,
    )
    return _client


def close_influx_client() -> None:
    """Cierra el cliente singleton (si existe)."""
    global _client
    if _client is None:
        return
    try:
        _client.close()
    finally:
        _client = None