import sqlite3
from pathlib import Path
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit, cross_val_score

DB_PATH = Path("data/processed/precios_papa.db")

VARIABLES = ["lag_0", "lag_1", "lag_2", "lag_3", "media_4", "lag_estacional", "mes"]

# Mallas de hiperparámetros a probar
MALLAS = {
    "Random Forest": (
        RandomForestRegressor(random_state=42),
        {
            "n_estimators": [100, 300],          # número de árboles
            "max_depth": [None, 5, 10],          # profundidad máxima de cada árbol
            "min_samples_leaf": [1, 5, 20],      # mínimo de filas por hoja
            "max_features": [1.0, "sqrt"],       # variables consideradas en cada división
        },
    ),
    "Gradient Boosting": (
        GradientBoostingRegressor(random_state=42),
        {
            "n_estimators": [100, 300, 500],     # número de árboles
            "learning_rate": [0.03, 0.1],        # cuánto corrige cada árbol al anterior
            "max_depth": [2, 3, 4],              # profundidad máxima de cada árbol
        },
    ),
}

# Lectura desde db SQLite
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM variables", conn, parse_dates=["semana", "semana_objetivo"])
base = pd.read_sql("SELECT * FROM metricas_base", conn)
conn.close()
df["objetivo_interpolado"] = df["objetivo_interpolado"].astype(bool)

# Mercado como columnas 0/1
dummies = pd.get_dummies(df["mercado"], prefix="mercado", dtype=int)
df = pd.concat([df, dummies], axis=1)
VARIABLES += list(dummies.columns)

# División temporal. El entrenamiento se ordena por semana para que
# TimeSeriesSplit corte por periodos y no por mercados
train = df[df["conjunto"] == "entrenamiento"].sort_values(["semana_objetivo", "mercado"])
test = df[(df["conjunto"] == "prueba") & (~df["objetivo_interpolado"])]

# Validación cruzada temporal: 5 particiones, cada una valida con las 96 semanas
# siguientes a su entrenamiento (96 x 6 mercados = 576 filas, sin partir semanas)
tscv = TimeSeriesSplit(n_splits=5, test_size=96 * 6)
print("Particiones de validación cruzada:")
for i, (idx_ent, idx_val) in enumerate(tscv.split(train), 1):
    ent, val = train.iloc[idx_ent], train.iloc[idx_val]
    print(f"  {i}: entrena {ent['semana_objetivo'].min():%Y-%m} a {ent['semana_objetivo'].max():%Y-%m}"
          f" | valida {val['semana_objetivo'].min():%Y-%m} a {val['semana_objetivo'].max():%Y-%m}")

# Referencia: MAE del ingenuo en las mismas particiones de validación
mae_cv_ingenuo = pd.Series([
    (train.iloc[idx_val]["objetivo"] - train.iloc[idx_val]["lag_0"]).abs().mean()
    for _, idx_val in tscv.split(train)
])
print("\nMAE del ingenuo por partición:", mae_cv_ingenuo.round(4).tolist())
print(f"MAE del ingenuo en validación cruzada: {mae_cv_ingenuo.mean():.4f}")

# Búsqueda de hiperparámetros: solo con el entrenamiento (2025 no participa)
resultados, predicciones = [], {}
for nombre, (modelo, malla) in MALLAS.items():
    busqueda = GridSearchCV(modelo, malla, cv=tscv, scoring="neg_mean_absolute_error", n_jobs=-1)
    busqueda.fit(train[VARIABLES], train["objetivo"])

    # MAE en validación cruzada con valores por defecto, para comparar en igualdad de condiciones
    cv_defecto = -cross_val_score(modelo, train[VARIABLES], train["objetivo"], cv=tscv,
                                  scoring="neg_mean_absolute_error", n_jobs=-1).mean()

    print(f"\n--- {nombre} ---")
    print(f"Combinaciones probadas: {len(busqueda.cv_results_['params'])}")
    print(f"Mejores hiperparámetros: {busqueda.best_params_}")
    print(f"MAE en validación cruzada -> por defecto: {cv_defecto:.4f} | optimizado: {-busqueda.best_score_:.4f}")

    # Evaluación en 2025 con el mejor modelo (reentrenado con todo el entrenamiento)
    pred = busqueda.predict(test[VARIABLES])
    predicciones[nombre] = pred
    resultados.append({
        "modelo": nombre,
        "MAE_cv_defecto": cv_defecto,
        "MAE_cv_optimizado": -busqueda.best_score_,
        "MAE_cv_ingenuo": mae_cv_ingenuo.mean(),
        "MAE_defecto": base.loc[base["modelo"] == nombre, "MAE"].iloc[0],
        "MAE_optimizado": mean_absolute_error(test["objetivo"], pred),
        "MAPE_optimizado_%": mean_absolute_percentage_error(test["objetivo"], pred) * 100,
    })

# Comparación: valores por defecto vs optimizados, y mejora sobre el ingenuo
resultados = pd.DataFrame(resultados)
mae_ingenuo = base.loc[base["modelo"] == "Ingenuo", "MAE"].iloc[0]
resultados["cambio_por_optimizacion_%"] = (resultados["MAE_optimizado"] / resultados["MAE_defecto"] - 1) * 100
resultados["mejora_vs_ingenuo_%"] = (1 - resultados["MAE_optimizado"] / mae_ingenuo) * 100
print("\n--- Validación cruzada (2015-2024) y prueba (2025): por defecto vs optimizado ---")
print(resultados.round(4).to_string(index=False))

# El modelo final se elige por el error en validación cruzada, no por el de 2025:
# si se eligiera mirando 2025, la prueba dejaría de ser independiente
mejor = resultados.loc[resultados["MAE_cv_optimizado"].idxmin(), "modelo"]
print(f"\nModelo elegido (menor MAE en validación cruzada): {mejor}")

# Carga de predicciones y métricas en SQLite
salida = test[["mercado", "semana_objetivo", "objetivo", "lag_0"]].copy()
salida = pd.concat([salida.assign(modelo=nombre, prediccion=pred)
                    for nombre, pred in predicciones.items()])
conn = sqlite3.connect(DB_PATH)
salida.to_sql("predicciones_optimizadas", conn, if_exists="replace", index=False)
resultados.assign(elegido=resultados["modelo"] == mejor).to_sql(
    "metricas_optimizadas", conn, if_exists="replace", index=False)
conn.close()
print(f"\nTablas 'predicciones_optimizadas' y 'metricas_optimizadas' guardadas en {DB_PATH}")