import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path("data/processed/precios_papa.db")

# Periodo de análisis: años completos, sin los huecos largos de 2012 ni el 2026 parcial
INICIO, FIN = "2013-01-01", "2025-12-31"

# Lectura desde db SQLite
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM precios", conn, parse_dates=["fecha"])
conn.close()
print(f"Registros diarios: {len(df):,}")

# Promedio semanal por mercado (semanas de lunes a domingo)
semanal = (
    df.pivot_table(index="fecha", columns="mercado", values="precio_kg")
    .resample("W")
    .mean()
)

# Semanas sin dato antes de recortar el periodo
print("\n--- Semanas sin dato (2012-2026) ---")
print(semanal.isna().sum().to_string())
print("\nSemanas sin dato por año:")
print(semanal.isna().groupby(semanal.index.year).sum().to_string())

# Recorte al periodo de análisis
semanal = semanal.loc[INICIO:FIN]
faltantes = semanal.isna()
print(f"\n--- Periodo {INICIO[:4]}-{FIN[:4]}: {len(semanal)} semanas ---")
print("Semanas sin dato:")
print(faltantes.sum().to_string())

# Racha más larga de semanas consecutivas sin dato por mercado
racha = faltantes.apply(lambda s: s.groupby((~s).cumsum()).sum().max())
print("\nRacha máxima sin dato (semanas):")
print(racha.to_string())

# Interpolación lineal de las semanas faltantes
semanal = semanal.interpolate(method="linear")

# Formato largo: una fila por mercado y semana, con marca de valor interpolado
panel = semanal.stack().rename("precio_kg").reset_index()
panel.columns = ["semana", "mercado", "precio_kg"]
panel["interpolado"] = faltantes.stack().values

# Verificación del estado final
print(f"\nFilas del panel: {len(panel):,} ({panel['mercado'].nunique()} mercados x {panel['semana'].nunique()} semanas)")
print(f"Valores interpolados: {panel['interpolado'].sum()} ({panel['interpolado'].mean() * 100:.2f} %)")
print(f"Nulos: {panel['precio_kg'].isna().sum()}")

# Carga en SQLite
conn = sqlite3.connect(DB_PATH)
panel.to_sql("panel_semanal", conn, if_exists="replace", index=False)
n_db = pd.read_sql("SELECT COUNT(*) AS n FROM panel_semanal", conn)["n"][0]
conn.close()
print(f"\nTabla 'panel_semanal' guardada en {DB_PATH}: {n_db:,} filas")