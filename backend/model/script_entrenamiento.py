import pandas as pd

#==============================================================
#CARGAR DATOS DE ENERGIA Y SENSORES
#==============================================================

df_energia  = pd.read_csv('backend\model\db_energia3.csv')
df_sensores = pd.read_csv('backend\model\db_sensores3.csv')

df_e = df_energia.copy()
df_e['timestamp'] = pd.to_datetime(df_e['_time'], format='ISO8601').dt.tz_localize(None)

medidores = [
    'consumo_MedidorAtlas7_minuto', 'consumo_MedidorAtlas8_minuto',
    'consumo_MedidorCentac_minuto', 'consumo_MedidorKaeser1_minuto',
    'consumo_MedidorKaeser2_minuto'
]

df_consumo = df_e[df_e['_field'].isin(medidores)].pivot_table(
    index='timestamp', columns='_field', values='_value'
).reindex(columns=medidores).fillna(0)

df_consumo['consumo_total_kW'] = df_consumo.sum(axis=1)
df_consumo = df_consumo[['consumo_total_kW']].reset_index()

df_s = df_sensores.copy()
df_s['timestamp'] = pd.to_datetime(df_s['_time'], format='ISO8601').dt.tz_localize(None)

# Filtrar solo los dos campos que tienes
df_flujo = df_s[df_s['_field'] == 'FLUJO_INSTANTANEO_SCFM'][['timestamp', '_value']].rename(columns={'_value': 'SCFM_total'})
df_presion = df_s[df_s['_field'] == 'PRESION_AIRE_GENERAL'][['timestamp', '_value']].rename(columns={'_value': 'presion_bar'})
df_flujo = df_flujo.set_index('timestamp').resample('1min').mean()
df_presion = df_presion.set_index('timestamp').resample('1min').mean()
df_consumo_1min = df_consumo.set_index('timestamp').resample('1min').mean()

df_trabajo = df_flujo.join(df_presion, how='inner').join(df_consumo_1min, how='inner')
df_trabajo = df_trabajo.dropna()

print(f"Dataset final: {len(df_trabajo)} puntos → desde {df_trabajo.index[0]} hasta {df_trabajo.index[-1]}")

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

#==============================================================
#IDENTIFICACIÓN DE MODELOS DE MACHINE LEARNING
#==============================================================

import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

# import xgboost as xgb

# ============================
# 1. Cargar dataset final
# ============================

df = df_trabajo.copy()  # ya contiene todas tus nuevas features

# Eliminamos filas con NaN generadas por lags
df = df.dropna()

# ============================
# 2. Separar variables
# ============================

target = "consumo_total_kW"

X = df.drop(columns=[target])
y = df[target]

# ============================
# 3. Train/Test sin mezclar tiempo
# ============================

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, shuffle=False
)

# ============================
# 4. Escalado (solo para modelos sensibles)
# ============================

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# # ============================
# # 5. Definir modelos
# # ============================

# modelos = {
#     "LinearRegression": LinearRegression(),
#     "RandomForest": RandomForestRegressor(
#         n_estimators=400, random_state=42, n_jobs=-1
#     ),
#     "GradientBoosting": GradientBoostingRegressor(
#         n_estimators=300, learning_rate=0.05, random_state=42
#     ),
#     "XGBoost": xgb.XGBRegressor(
#         n_estimators=500,
#         learning_rate=0.05,
#         max_depth=6,
#         subsample=0.8,
#         colsample_bytree=0.8,
#         random_state=42,
#         n_jobs=-1
#     )
# }

# # ============================
# # 6. Entrenar y evaluar
# # ============================

# resultados = []

# for nombre, modelo in modelos.items():

#     # Modelos que requieren escalado
#     if nombre in ["LinearRegression"]:
#         modelo.fit(X_train_scaled, y_train)
#         pred = modelo.predict(X_test_scaled)
#     else:
#         modelo.fit(X_train, y_train)
#         pred = modelo.predict(X_test)

#     mae = mean_absolute_error(y_test, pred)
#     rmse = np.sqrt(mean_squared_error(y_test, pred))
#     r2 = r2_score(y_test, pred)

#     resultados.append([nombre, mae, rmse, r2])

# # ============================
# # 7. Mostrar resultados
# # ============================

# df_resultados = pd.DataFrame(
#     resultados,
#     columns=["Modelo", "MAE", "RMSE", "R²"]
# )

# print("\n===== RESULTADOS DE MODELOS =====\n")
# print(df_resultados.sort_values("MAE"))

#================================================================
# AJUSTE DE HIPERPARÁMETROS PARA GRADIENT BOOSTING ESCOGIDO POR LOS MEJORES RESULTADOS
#================================================================

from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import GradientBoostingRegressor

param_grid = {
    "n_estimators": [200, 300, 400],
    "learning_rate": [0.05, 0.03, 0.01],
    "max_depth": [2, 3, 4],
    "subsample": [0.8, 1.0],
    "min_samples_split": [2, 5, 10]
}

gb = GradientBoostingRegressor(random_state=42)

grid = GridSearchCV(
    gb,
    param_grid,
    scoring="neg_mean_absolute_error",
    cv=3,
    n_jobs=-1
)

grid.fit(X_train, y_train)

print("Mejores parámetros:", grid.best_params_)
print("MAE:", -grid.best_score_)

best_gb = GradientBoostingRegressor(
    **grid.best_params_,
    random_state=42
)

best_gb.fit(X_train, y_train)

y_pred = best_gb.predict(X_test)

print("MAE:", mean_absolute_error(y_test, y_pred))
print("RMSE:", np.sqrt(mean_squared_error(y_test, y_pred)))
print("R²:", r2_score(y_test, y_pred))

# import matplotlib.pyplot as plt

# plt.figure(figsize=(14,6))
# plt.plot(y_test.values, label="Real", linewidth=2)
# plt.plot(y_pred, label="Predicho", linewidth=2)
# plt.legend()
# plt.title("Consumo energético: Real vs Predicho")
# plt.show()

#==============================================================
#GUARDAR MODELO ENTRENADO
#==============================================================

import joblib

joblib.dump(best_gb, "backend\model\modelo_sistema_aire_03012026.pkl")
joblib.dump(scaler, "backend\model\features_sistema_aire_03012026.pkl")