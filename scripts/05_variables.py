import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path("data/processed/precios_papa.db")

HORIZONTE = 4          # semanas hacia adelante que se quiere predecir
ANIO_PRUEBA = 2025     # año reservado para evaluar los modelos

# Lectura desde db SQLite
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM panel_semanal", conn, parse_dates=["semana"])
conn.close()
df["interpolado"] = df["interpolado"].astype(bool)
df = df.sort_values(["mercado", "semana"]).reset_index(drop=True)
print(f"Filas del panel: {len(df):,}")

# Cada fila es una semana t de un mercado: se usa lo conocido hasta t
# para predecir el precio de la semana t + HORIZONTE
g = df.groupby("mercado")["precio_kg"]

# Variable objetivo: precio dentro de HORIZONTE semanas
df["objetivo"] = g.shift(-HORIZONTE)
df["semana_objetivo"] = df["semana"] + pd.Timedelta(weeks=HORIZONTE)
df["objetivo_interpolado"] = df.groupby("mercado")["interpolado"].shift(-HORIZONTE)

# Precios recientes: semana actual y las 3 anteriores
df["lag_0"] = df["precio_kg"]
for k in range(1, 4):
    df[f"lag_{k}"] = g.shift(k)

# Promedio de las últimas 4 semanas (t-3 a t)
df["media_4"] = g.transform(lambda s: s.rolling(4).mean())

# Precio de la misma semana del año anterior a la semana objetivo
df["lag_estacional"] = g.shift(52 - HORIZONTE)

# Mes de la semana objetivo (el calendario se conoce de antemano)
df["mes"] = df["semana_objetivo"].dt.month

# Promedio de los otros 5 mercados en la semana t (para la pregunta M2)
total = df.groupby("semana")["precio_kg"].transform("sum")
df["otros_mercados"] = (total - df["precio_kg"]) / 5

# Filas sin historia suficiente (inicio) o sin objetivo (final)
n = len(df)
df = df.dropna()
df["objetivo_interpolado"] = df["objetivo_interpolado"].astype(bool)
print(f"Filas sin historia u objetivo eliminadas: {n - len(df):,}")

# División temporal según el año de la semana objetivo
df["conjunto"] = "entrenamiento"
df.loc[df["semana_objetivo"].dt.year == ANIO_PRUEBA, "conjunto"] = "prueba"

# Verificación de fuga de información: el objetivo debe ser el precio
# real de la semana objetivo, posterior a todas las variables
check = df.merge(df[["mercado", "semana", "precio_kg"]],
                 left_on=["mercado", "semana_objetivo"], right_on=["mercado", "semana"],
                 suffixes=("", "_real"))
print("\n--- Verificación ---")
print(f"Objetivo = precio real de la semana objetivo: {(check['objetivo'] == check['precio_kg_real']).all()}")
print(f"Distancia entre semana y semana objetivo: {(df['semana_objetivo'] - df['semana']).unique()[0].days // 7} semanas")

columnas = ["mercado", "semana", "semana_objetivo", "lag_0", "lag_1", "lag_2", "lag_3",
            "media_4", "lag_estacional", "mes", "otros_mercados",
            "objetivo", "objetivo_interpolado", "conjunto"]
df = df[columnas]

# Resumen de la tabla final
print(f"\nFilas finales: {len(df):,}")
print(df.groupby("conjunto")["semana_objetivo"].agg(["count", "min", "max"]).to_string())
print(f"\nObjetivos interpolados en prueba: {df.loc[df['conjunto'] == 'prueba', 'objetivo_interpolado'].sum()}")
print("\nPrimeras filas de Quito:")
print(df.loc[df["mercado"] == "Quito", ["semana", "semana_objetivo", "lag_0", "lag_estacional", "objetivo"]]
      .head(3).to_string(index=False))

# Carga en SQLite
conn = sqlite3.connect(DB_PATH)
df.to_sql("variables", conn, if_exists="replace", index=False)
n_db = pd.read_sql("SELECT COUNT(*) AS n FROM variables", conn)["n"][0]
conn.close()
print(f"\nTabla 'variables' guardada en {DB_PATH}: {n_db:,} filas")