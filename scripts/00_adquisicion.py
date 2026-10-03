from pathlib import Path
import pandas as pd

RAW_PATH = Path("data/raw/Rep_Pre_Prod_X_MercCGINA.csv")
INTERIM_DIR = Path("data/interim")
PARQUET_PATH = INTERIM_DIR / "precios_papa_raw.parquet"

# Nombres de columna del reporte SIPA y nombres descriptivos
COLUMNAS = {
    "NOMBRE_MERCADO_1": "mercado",
    "NOMBRE_CATE_PROD_1": "categoria",
    "textbox6": "producto",
    "FECHA_TOMA": "fecha",
    "textbox4": "precio",
    "textbox10": "presentacion",
    "PRECIO_KILO": "precio_kg",
    "PRESENTACION": "unidad_precio_kg",
}

# Leer el original en UTF-16 y coma decimal
print("Leyendo CSV...")
df = pd.read_csv(RAW_PATH, encoding="utf-16", decimal=",")
df = df.rename(columns=COLUMNAS)

# Fecha en formato dd/mm/aaaa
df["fecha"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y %H:%M:%S")

# Guardar copia en parquet
INTERIM_DIR.mkdir(parents=True, exist_ok=True)
df.to_parquet(PARQUET_PATH, index=False)

print(f"Copia de trabajo guardada en {PARQUET_PATH}")
print(f"Shape: {df.shape}")
print(f"Periodo: {df['fecha'].min():%Y-%m-%d} -> {df['fecha'].max():%Y-%m-%d}")
print(df.dtypes)