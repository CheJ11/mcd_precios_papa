import sqlite3
from pathlib import Path
import pandas as pd

PARQUET_PATH = Path("data/interim/precios_papa_raw.parquet")
PROCESSED_DIR = Path("data/processed")
DB_PATH = PROCESSED_DIR / "precios_papa.db"

# Mercados del alcance: nombre en el SIPA - nombre recortado
MERCADOS = {
    "Quito MMQ-EP": "Quito",
    "Guayaquil - TTV": "Guayaquil",
    "Cuenca - El Arenal": "Cuenca",
    "Ambato EP-EMA": "Ambato",
    "Riobamba - EP-EMMPA": "Riobamba",
    "Latacunga": "Latacunga",
}
LIBRA_KG = 0.45359237

# Lectura de datos
df = pd.read_parquet(PARQUET_PATH)
print(f"Filas iniciales: {len(df):,}")
print("\nNulos por columna:")
print(df.isna().sum().to_string())

# Espacios repetidos en los nombres de mercado ('Ambato  EP-EMA')
df["mercado"] = df["mercado"].str.split().str.join(" ")

print("\nRegistros por presentación:")
print(df["presentacion"].value_counts().to_string())

# Limpieza de datos
print("\n--- Limpieza ---")

# [1] Duplicados exactos: filas idénticas en todas las columnas
n = len(df)
df = df.drop_duplicates()
print(f"[1] Duplicados exactos eliminados:          {n - len(df):>6,}")

# [2] Presentaciones distintas del quintal de 100 lb (sacos de 120, 140 y 150 lb)
n = len(df)
df = df[df["presentacion"].str.startswith("Quintal")]
print(f"[2] Presentaciones en saco eliminadas:      {n - len(df):>6,}")

# [3] Mercados fuera del alcance
n = len(df)
df = df[df["mercado"].isin(MERCADOS)]
print(f"[3] Registros de otros mercados eliminados: {n - len(df):>6,}")

# Formato y tipos
df["mercado"] = df["mercado"].map(MERCADOS)

# Precio por kg recalculado: la columna original está redondeada a 2 decimales
precio_kg = df["precio"] / (100 * LIBRA_KG)
print(f"\nDiferencia máxima con precio_kg original: {(precio_kg - df['precio_kg']).abs().max():.4f} USD/kg")
df["precio_kg"] = precio_kg

# Columnas constantes tras el filtrado: no aportan información
df = df.drop(columns=["categoria", "producto", "presentacion", "unidad_precio_kg"])
df = df.sort_values(["mercado", "fecha"]).reset_index(drop=True)

# Verificación del estado final
print(f"\nFilas finales: {len(df):,}")
print(f"Duplicados por mercado y fecha: {df.duplicated(['mercado', 'fecha']).sum()}")
print("\nRegistros por mercado:")
print(df.groupby("mercado")["fecha"].agg(["count", "min", "max"]).to_string())

# Carga en SQLite
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(DB_PATH)
df.to_sql("precios", conn, if_exists="replace", index=False)
n_db = pd.read_sql("SELECT COUNT(*) AS n FROM precios", conn)["n"][0]
conn.close()
print(f"\nTabla 'precios' guardada en {DB_PATH}: {n_db:,} filas")