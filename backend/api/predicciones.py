"""Lógica de predicción de consumo.

Este módulo implementa el pipeline para el sistema "AIRE COMPRIMIDO":
- Consulta de datos (energía + sensores) desde Influx (vía `api.influx_tools`).
- Transformación a features (lags, variables temporales, eficiencia, etc.).
- Predicción autoregresiva de minutos futuros usando un modelo + scaler (joblib).
- Cálculo del total estimado del día (real + predicho).

Se usa desde endpoints SSE en `api.views`.
"""

from api.influx_tools import get_equipos_aire_comprimido_online, get_influx_data_for_air_compressor_prediction, get_influx_data_for_air_compressor_prediction_all_day, sumar_acumulador_calculo_total 
import logging
logger = logging.getLogger("estado_equipos")

import time
import threading

_pred_cache_lock = threading.Lock()
_pred_cache_value = None
_pred_cache_ts = 0.0
_pred_cache_ttl_s = 10.0
async def get_datos_para_prediccion():
    """
    Obtiene datos de InfluxDB necesarios para la predicción del consumo del compresor de aire.
    """
    datos = await get_influx_data_for_air_compressor_prediction()
    return datos


def crear_features_para_modelo(df_trabajo):
    """Agrega features derivadas a un dataframe por minuto.

    Incluye:
    - variables temporales (hora/minuto/día_semana)
    - detección heurística de equipos Atlas activos
    - features de eficiencia y lags
    """
    #==============================================================
    #CREAR FEATURES ADICIONALES
    #==============================================================

    df_trabajo['hora'] = df_trabajo.index.hour
    df_trabajo['minuto'] = df_trabajo.index.minute
    df_trabajo['dia_semana'] = df_trabajo.index.dayofweek
    df_trabajo['es_laborable'] = (df_trabajo.index.weekday < 5).astype(int)

    df_trabajo = df_trabajo.dropna().copy()

    # 1. DETECCIÓN EXACTA DE CUÁNTOS ATLAS ESTÁN ENCENDIDOS
    # Usamos saltos de ~1450–1550 SCFM (valor real que me has dado: 1500)
    df_trabajo['SCFM_diff_2min'] = df_trabajo['SCFM_total'].diff(2)
    # Detección de encendido Atlas7 (primer salto grande)
    df_trabajo['atlas7_on']  = ((df_trabajo['SCFM_diff_2min'] > 1300) & (df_trabajo['SCFM_diff_2min'] < 1700) & 
                        (df_trabajo['SCFM_total'].shift(1) < 1800)).astype(int)

    # Detección de encendido Atlas8 (segundo salto grande)
    df_trabajo['atlas8_on']  = ((df_trabajo['SCFM_diff_2min'] > 1300) & (df_trabajo['SCFM_diff_2min'] < 1700) & 
                        (df_trabajo['SCFM_total'].shift(1) > 1800)).astype(int)
    # Estado persistente (una vez encendido, sigue encendido hasta que baje mucho)
    df_trabajo['atlas7_activo'] = df_trabajo['atlas7_on'].cumsum().clip(upper=1)
    df_trabajo['atlas8_activo'] = df_trabajo['atlas8_on'].cumsum().clip(upper=1)

    # Reinicio cuando el flujo baja mucho (apagado)
    df_trabajo.loc[df_trabajo['SCFM_total'] < 800, ['atlas7_activo', 'atlas8_activo']] = 0
    # Número exacto de Atlas activos
    df_trabajo['n_atlas_activos'] = df_trabajo['atlas7_activo'] + df_trabajo['atlas8_activo']

    # 2. CONSUMO TEÓRICO DE LOS ATLAS (física pura)
    # Atlas típicos: 0.17–0.19 kW/SCFM en carga plena
    df_trabajo['consumo_atlas_teorico'] = df_trabajo['SCFM_total'].clip(upper=3000) * 0.185
    # 3. LAGS REALISTAS (el consumo eléctrico tarda en reaccionar)
    for lag in [1,2,3,4,5,6,8,10,15]:
        df_trabajo[f'SCFM_lag_{lag}'] = df_trabajo['SCFM_total'].shift(lag)
        df_trabajo[f'presion_lag_{lag}'] = df_trabajo['presion_bar'].shift(lag)
        df_trabajo[f'atlas_activos_lag_{lag}'] = df_trabajo['n_atlas_activos'].shift(lag)

    # 4. FEATURES DE EFICIENCIA 
    df_trabajo['kW_por_SCFM'] = df_trabajo['consumo_total_kW'] / (df_trabajo['SCFM_total'] + 1)
    df_trabajo['eficiencia_vs_teorico'] = df_trabajo['consumo_total_kW'] / (df_trabajo['consumo_atlas_teorico'] + 1)
    # 5. Variables temporales
    df_trabajo['hora'] = df_trabajo.index.hour
    df_trabajo['minuto'] = df_trabajo.index.minute
    df_trabajo['dia_semana'] = df_trabajo.index.dayofweek
    df_trabajo['es_laborable'] = (df_trabajo.index.weekday < 5).astype(int)

    df_trabajo = df_trabajo.dropna()

    return df_trabajo



async def preparar_datos_para_modelo(datos):
    """
    Prepara y transforma los datos obtenidos para que sean compatibles con el modelo de predicción.
    """
    import pandas as pd

    
    datos_energia, datos_sensores = datos
    df_energia = pd.DataFrame(datos_energia)
    df_sensores = pd.DataFrame(datos_sensores)
    if df_energia.empty     or df_sensores.empty:
        logger.warning("No hay datos suficientes para preparar el modelo")
        return None

    columnas_necesarias = {"_time", "_value", "_measurement", "_field"}
    if not columnas_necesarias.issubset(df_energia.columns):
        logger.warning("df_energia no tiene columnas necesarias: %s", df_energia.columns)
        return None

    if not columnas_necesarias.issubset(df_sensores.columns):
        logger.warning("df_sensores no tiene columnas necesarias: %s", df_sensores.columns)
        return None
    
    Equipos_aire_comprimido_online = await get_equipos_aire_comprimido_online()
    
    df_energia["timestamp"] = pd.to_datetime(df_energia["_time"], format="ISO8601").dt.tz_localize(None)
    df_energia.set_index("timestamp", inplace=True)

    # Crear nombre único por equipo
    # Ejemplo: CASA_Energia_activa_consumida_minuto
    df_energia["equipo"] = df_energia["_field"].str.split("_").str[0]

    # Crear campo_equipo
    df_energia["campo_equipo"] = df_energia["_measurement"] + "_" + df_energia["_field"]

    # Filtrar solo equipos online
    df = df_energia[df_energia["equipo"].isin(Equipos_aire_comprimido_online)]
    
    # Pivotear: columnas = cada equipo
    df_pivot = df.pivot_table(
        index=df.index,
        columns="campo_equipo",
        values="_value",
        aggfunc="sum"
    ).fillna(0)

    # Sumar consumos por timestamp
    df_pivot["consumo_total_kW"] = df_pivot.sum(axis=1)
    df_consumo = df_pivot[['consumo_total_kW']].reset_index()
    
    df_sensores["timestamp"] = pd.to_datetime(df_sensores["_time"], format="ISO8601").dt.tz_localize(None)
    
    df_flujo = df_sensores[df_sensores['_measurement'] == 'FLUJO_INSTANTANEO_SCFM'][['timestamp', '_value']].rename(columns={'_value': 'SCFM_total'})
    df_presion = df_sensores[df_sensores['_measurement'] == 'PRESION_AIRE_GENERAL'][['timestamp', '_value']].rename(columns={'_value': 'presion_bar'})
    df_flujo = df_flujo.set_index('timestamp').resample('1min').mean()
    df_flujo = df_flujo.fillna(0)
    df_presion = df_presion.set_index('timestamp').resample('1min').mean()
    df_presion = df_presion.fillna(0)
    df_consumo_1min = df_consumo.set_index('timestamp').resample('1min').mean()
    df_trabajo = df_flujo.join(df_presion, how='inner').join(df_consumo_1min, how='inner')
    df_trabajo = df_trabajo.dropna()

    df_trabajo = crear_features_para_modelo(df_trabajo)
    
    return df_trabajo

def predecir_minutos_futuros(df_trabajo, modelo, scaler, minutos=30):
    """
    df_trabajo: DataFrame con features reales (últimos 30 min)
    modelo: modelo cargado con joblib
    scaler: scaler cargado con joblib
    minutos: cuántos minutos hacia adelante predecir
    """

    import pandas as pd
    from datetime import timedelta

    predicciones = []

    df_pred = df_trabajo.copy()

    for _ in range(minutos):

        # 1. Tomar la última fila con features
        ultima = df_pred.tail(1)

        # 2. Ordenar columnas según el scaler
        columnas = scaler.feature_names_in_
        X = ultima[columnas]

        # 3. Escalar
        X_scaled = scaler.transform(X)

        # 4. Predecir
        y_pred = modelo.predict(X_scaled)[0]

        # 5. Crear nuevo timestamp
        nuevo_ts = ultima.index[0] + timedelta(minutes=1)

        # 6. Crear nueva fila con valores futuros
        nueva_fila = ultima.copy()
        nueva_fila.index = [nuevo_ts]

        # Reemplazar el consumo real por la predicción
        nueva_fila["consumo_total_kW"] = y_pred

        # 7. Recalcular features (lags, eficiencia, etc.)
        nueva_fila = crear_features_para_modelo(
            pd.concat([df_pred, nueva_fila]).tail(20)  # suficiente para lags
        ).tail(1)

        # 8. Agregar al DF acumulado
        df_pred = pd.concat([df_pred, nueva_fila])

        # 9. Guardar predicción
        predicciones.append({
            "timestamp": nuevo_ts,
            "prediccion_kW": float(y_pred)
        })

    return predicciones, df_pred


def predecir_consumo_compresor(df_trabajo):
    """Predice los próximos 30 minutos para el compresor usando artefactos cargados."""
    from api.model_loader import modelo_aire, scaler_aire
    if df_trabajo is None or df_trabajo.empty:
        raise ValueError("df_trabajo está vacío. No se puede predecir.")

    predicciones, _ = predecir_minutos_futuros(
        df_trabajo, modelo_aire, scaler_aire, minutos=30
    )

    return predicciones

import asyncio
async def prediccion_en_tiempo_real(intervalo=10):
    """Genera una predicción *una vez* (para usar desde SSE).

    Nota: este endpoint se llama potencialmente por múltiples clientes SSE.
    Para evitar picos de CPU, se cachea el resultado por unos segundos.
    El parámetro `intervalo` se conserva por compatibilidad.
    """
    global _pred_cache_value, _pred_cache_ts

    from django.utils import timezone
    from api.model_loader import modelo_aire, scaler_aire

    # Cache (evita recalcular pandas+modelo para cada conexión SSE)
    now = time.monotonic()
    with _pred_cache_lock:
        if _pred_cache_value is not None and (now - _pred_cache_ts) < _pred_cache_ttl_s:
            return _pred_cache_value

    try:
        datos = await get_datos_para_prediccion()
        df_trabajo = await preparar_datos_para_modelo(datos)
        if df_trabajo is None or getattr(df_trabajo, "empty", False):
            logger.warning("No hay datos suficientes para predecir")
            return []

        predicciones, _ = predecir_minutos_futuros(
            df_trabajo=df_trabajo,
            modelo=modelo_aire,
            scaler=scaler_aire,
            minutos=30
        )

        logger.info(
            "Predicción generada a las %s (%s puntos)",
            timezone.localtime(timezone.now()).isoformat(),
            len(predicciones),
        )
        with _pred_cache_lock:
            _pred_cache_value = predicciones
            _pred_cache_ts = now
        return predicciones

    except Exception as e:
        logger.error("Error en predicción en tiempo real: %s", e, exc_info=True)
        return []




def predecir_consumo_restante_del_dia(df_trabajo, modelo, scaler):
    """
    Predice el consumo desde la hora actual hasta las 23:59.
    """

    from django.utils import timezone

    # 1. Calcular minutos restantes del día
    ahora = timezone.localtime(timezone.now())
    fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)
    minutos_faltantes = max(int((fin_dia - ahora).total_seconds() // 60), 0)

    # Si ya es medianoche, no hay nada que predecir
    if minutos_faltantes == 0:
        return [], df_trabajo

    # 2. Usar tu función autoregresiva
    predicciones, df_pred = predecir_minutos_futuros(
        df_trabajo=df_trabajo,
        modelo=modelo,
        scaler=scaler,
        minutos=minutos_faltantes
    )

    return predicciones, df_pred

def calcular_consumo_total_dia(consumo_real_minuto, predicciones):
    # Real: Wh → kWh
    real_kW = (sum(consumo_real_minuto)/60) / 1000

    # Predicción: kW → kWh
    pred_kW = sum(p["prediccion_kW"] for p in predicciones) / 60

    return {
        "real_kWh": real_kW,
        "pred_kWh": pred_kW,
        "total_estimado_kWh": (real_kW + pred_kW)/1000.0
    }


async def calcular_prediccion_consumo_dia(sistema: str, intervalo=60):
    """Calcula el total estimado del día (real acumulado + predicción restante).

    Retorna un payload listo para SSE con la forma:
    - `{"tipo": "grafico_actualizado", "contenido": {real_kWh, pred_kWh, total_estimado_kWh}}`
    """
    from api.model_loader import modelo_aire, scaler_aire

    try:
        # 1. Datos reales del día
        datos_reales, datos_sensores = await get_influx_data_for_air_compressor_prediction_all_day()

        if not datos_reales:
            return {
                "tipo": "sin_datos",
                "contenido": "No hay datos reales para el día"
            }

        # 2. Consumo real por minuto
        consumo_real_minuto = [d["_value"] for d in datos_reales]
        
        # 3. Preparar features
        df_trabajo = await preparar_datos_para_modelo((datos_reales, datos_sensores))
        if df_trabajo is None or getattr(df_trabajo, "empty", False):
            return {
                "tipo": "sin_datos",
                "contenido": "No hay suficientes datos para generar features"
            }

        # 4. Predicción restante del día
        predicciones, _ = predecir_consumo_restante_del_dia(
            df_trabajo=df_trabajo,
            modelo=modelo_aire,
            scaler=scaler_aire
        )

        # 5. Cálculo total del día
        resultado = calcular_consumo_total_dia(consumo_real_minuto, predicciones)

        return {
            "tipo": "grafico_actualizado",
            "contenido": {
                "real_kWh": resultado["real_kWh"],
                "pred_kWh": resultado["pred_kWh"],
                "total_estimado_kWh": resultado["total_estimado_kWh"],
            }
        }

    except Exception as e:
        logger.error("Error en calcular_prediccion_consumo_dia: %s", e, exc_info=True)
        return {
            "tipo": "error",
            "contenido": str(e)
        }
