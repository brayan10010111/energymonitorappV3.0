import os
from influxdb_client import InfluxDBClient

import environ




def get_influx_client():
    env = environ.Env()
    environ.Env.read_env()
    url = env("INFLUX_URL")
    token = env("INFLUX_TOKEN")
    org = env("INFLUX_ORG")

    if not all([url, token, org]):
        raise ValueError("Faltan variables de entorno para conectar a InfluxDB.")

    return InfluxDBClient(url=url, token=token, org=org)