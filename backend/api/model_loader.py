"""Carga de artefactos de Machine Learning.

Este módulo carga (una sola vez por proceso) el modelo y scaler usados
para predicción del sistema de aire comprimido.

Nota: al importarse, realiza IO en disco (`joblib.load`).
"""

import os
import joblib
from django.conf import settings

MODEL_DIR = os.path.join(settings.BASE_DIR,  "model")

# Cargar una sola vez al iniciar Django
modelo_aire = joblib.load(os.path.join(MODEL_DIR, "modelo_sistema_aire_03012026.pkl"))
scaler_aire = joblib.load(os.path.join(MODEL_DIR, "features_sistema_aire_03012026.pkl"))