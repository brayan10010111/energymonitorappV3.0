import os
from influxdb_client import InfluxDBClient
from dotenv import load_dotenv

load_dotenv()  # Carga variables desde .env

def get_influx_client():
    url = os.getenv("INFLUX_URL")
    token = os.getenv("INFLUX_TOKEN")
    org = os.getenv("INFLUX_ORG")

    if not all([url, token, org]):
        raise ValueError("Faltan variables de entorno para conectar a InfluxDB.")

    return InfluxDBClient(url=url, token=token, org=org)