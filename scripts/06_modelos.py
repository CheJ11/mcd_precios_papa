import sqlite3
from pathlib import Path

import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error

DB_PATH = Path("data/processed/precios_papa.db")

# Variables de entrada del modelo base y del experimento M2
VARIABLES = ["lag_0", "lag_1", "lag_2", "lag_3", "media_4", "lag_estacional", "mes"]
VARIABLES_M2 = VARIABLES + ["otros_mercados"]

# Lectura desde db SQLite
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM variables", conn, parse_dates=["semana", "semana_objetivo"])
conn.close()
df["objetivo_interpolado"] = df["objetivo_interpolado"].astype(bool)

# Mercado como columnas 0/1 (los modelos solo aceptan números)
dummies = pd.get_dummies(df["mercado"], prefix="mercado", dtype=int)
df = pd.concat([df, dummies], axis=1)
VARIABLES += list(dummies.columns)
VARIABLES_M2 += list(dummies.columns)

# División temporal
train = df[df["conjunto"] == "entrenamiento"]
test = df[(df["conjunto"] == "prueba") & (~df["objetivo_interpolado"])]
print(f"Entrenamiento: {len(train):,} filas | Prueba: {len(test):,} filas")
print(f"Variables del modelo base: {len(VARIABLES)}")

# Modelos con aprendizaje: valores por defecto (se optimizan en 07)
modelos = {
    "Regresión lineal": LinearRegression(),
    "Random Forest": RandomForestRegressor(random_state=42, n_jobs=-1),
    "Gradient Boosting": GradientBoostingRegressor(random_state=42),
}

# Predicciones en 2025: referencias + modelos entrenados
predicciones = {
    "Ingenuo": test["lag_0"],                       # repite el precio de esta semana
    "Ingenuo estacional": test["lag_estacional"],   # repite el precio de hace un año
}
for nombre, modelo in modelos.items():
    modelo.fit(train[VARIABLES], train["objetivo"])
    predicciones[nombre] = modelo.predict(test[VARIABLES])

# M1. Métricas en el conjunto de prueba
mae_ingenuo = mean_absolute_error(test["objetivo"], predicciones["Ingenuo"])
resultados = []
for nombre, pred in predicciones.items():
    mae = mean_absolute_error(test["objetivo"], pred)
    resultados.append({
        "modelo": nombre,
        "MAE": mae,
        "MAPE_%": mean_absolute_percentage_error(test["objetivo"], pred) * 100,
        "mejora_vs_ingenuo_%": (1 - mae / mae_ingenuo) * 100,
    })
resultados = pd.DataFrame(resultados)
print("\n--- M1. Error en 2025 (horizonte de 4 semanas) ---")
print(resultados.round(3).to_string(index=False))

# Importancia de las variables según el Random Forest
importancia = pd.Series(modelos["Random Forest"].feature_importances_, index=VARIABLES)
print("\nImportancia de las variables (Random Forest):")
print(importancia.sort_values(ascending=False).round(3).to_string())

# M2. Mismos modelos agregando el precio promedio de los otros mercados
print("\n--- M2. MAE sin y con 'otros_mercados' ---")
m2 = []
for nombre, modelo in modelos.items():
    modelo.fit(train[VARIABLES_M2], train["objetivo"])
    mae_m2 = mean_absolute_error(test["objetivo"], modelo.predict(test[VARIABLES_M2]))
    mae_base = resultados.loc[resultados["modelo"] == nombre, "MAE"].iloc[0]
    m2.append({"modelo": nombre, "MAE_base": mae_base, "MAE_con_otros": mae_m2,
               "cambio_%": (mae_m2 / mae_base - 1) * 100})
print(pd.DataFrame(m2).round(4).to_string(index=False))

# Carga de predicciones y métricas en SQLite (formato largo)
salida = test[["mercado", "semana_objetivo", "objetivo"]].copy()
salida = pd.concat([salida.assign(modelo=nombre, prediccion=pred)
                    for nombre, pred in predicciones.items()])
conn = sqlite3.connect(DB_PATH)
salida.to_sql("predicciones_base", conn, if_exists="replace", index=False)
resultados.to_sql("metricas_base", conn, if_exists="replace", index=False)
conn.close()
print(f"\nTablas 'predicciones_base' ({len(salida):,} filas) y 'metricas_base' guardadas en {DB_PATH}")