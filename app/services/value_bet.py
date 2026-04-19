import math
import pandas as pd


# Umbrales de value bet realistas
# Value = (prob * cuota) - 1
# Un edge del 5%+ ya es muy bueno en apuestas deportivas
UMBRAL_NO_RENTABLE    = 0.0
UMBRAL_VALE_LA_PENA   = 0.03   # 3%+ edge minimo
UMBRAL_RENTABLE       = 0.08   # 8%+ edge bueno
UMBRAL_FIRMARLA       = 0.15   # 15%+ edge excelente


def clasificar(value):
    """Clasifica el value bet segun el edge calculado."""
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "⚠️ SIN DATOS"
        value = float(value)
        if value <= UMBRAL_NO_RENTABLE:
            return "❌ NO RENTABLE"
        elif value <= UMBRAL_VALE_LA_PENA:
            return "⚖️ MARGINAL"
        elif value <= UMBRAL_RENTABLE:
            return "💰 RENTABLE"
        else:
            return "🔥 FIRMAR"
    except (TypeError, ValueError):
        return "⚠️ SIN DATOS"


def calcular_value(prob, cuota):
    """
    Calcula el value bet.
    Value = (probabilidad_real * cuota) - 1
    Positivo = apuesta con valor
    Negativo = apuesta sin valor
    """
    try:
        prob = float(prob)
        cuota = float(cuota)

        # Validaciones
        if prob <= 0 or prob > 1:
            return 0.0
        if cuota <= 1.0:
            # Cuota menor o igual a 1 no tiene sentido en apuestas
            return 0.0

        return round((prob * cuota) - 1, 4)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def normalizar_std(std, minimo=0.35):
    """
    Normaliza la desviacion estandar asegurando un minimo realista.
    Default 0.35 alineado con football_model.py y simulator.py
    """
    try:
        if std is None or pd.isna(std) or not isinstance(std, (int, float)):
            return minimo
        std = float(std)
        if std <= 0 or math.isnan(std) or math.isinf(std):
            return minimo
        return max(std, minimo)
    except (TypeError, ValueError):
        return minimo


def calcular_probabilidad_implicita(cuota):
    """
    Calcula la probabilidad implicita de una cuota.
    Prob = 1 / cuota
    """
    try:
        cuota = float(cuota)
        if cuota <= 0:
            return 0.0
        return round(1 / cuota, 4)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def edge_porcentual(prob_real, cuota):
    """
    Calcula el edge en porcentaje entre la probabilidad real
    y la probabilidad implicita de la cuota.
    Edge positivo = ventaja sobre la casa.
    """
    try:
        prob_implicita = calcular_probabilidad_implicita(cuota)
        if prob_implicita <= 0:
            return 0.0
        return round((float(prob_real) - prob_implicita) * 100, 2)
    except (TypeError, ValueError):
        return 0.0
