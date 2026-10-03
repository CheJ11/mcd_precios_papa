import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path("data/processed/precios_papa.db")

# Lectura desde db SQLite
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM panel_semanal", conn, parse_dates=["semana"])
conn.close()

# SQLite guarda los booleanos como 0/1, se restaura el tipo
df["interpolado"] = df["interpolado"].astype(bool)
print(f"Filas: {len(df):,} | Columnas: {df.shape[1]}")

# Metadata por campo
metadata = pd.DataFrame({
    "tipo": df.dtypes.astype(str),
    "nulos": df.isna().sum(),
    "pct_nulos": (df.isna().mean() * 100).round(2),
    "valores_unicos": df.nunique(),
})
print("\n--- Metadata por campo ---")
print(metadata.to_string())

# Campo numérico: distribución del precio por mercado (USD/kg)
print("\n--- precio_kg por mercado ---")
print(df.groupby("mercado")["precio_kg"].describe().round(3).to_string())

# Coeficiente de variación: dispersión relativa del precio en todo el periodo
cv = df.groupby("mercado")["precio_kg"].agg(lambda s: s.std() / s.mean())
print("\nCoeficiente de variación por mercado:")
print(cv.round(3).sort_values(ascending=False).to_string())

# Campo temporal: cobertura
print("\n--- semana ---")
print(f"Rango: {df['semana'].min():%Y-%m-%d} -> {df['semana'].max():%Y-%m-%d}")
print("Valores interpolados por mercado:")
print(df.groupby("mercado")["interpolado"].sum().to_string())

# Precio medio anual por mercado (USD/kg)
print("\n--- Precio medio anual por mercado ---")
anual = df.pivot_table(index=df["semana"].dt.year, columns="mercado", values="precio_kg")
print(anual.round(3).to_string())