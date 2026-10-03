import sqlite3
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

DB_PATH = Path("data/processed/precios_papa.db")
FIG_DIR = Path("reports/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Función de cada mercado: consumo o zona productora
TIPO = {"Quito": "Consumo", "Guayaquil": "Consumo", "Cuenca": "Consumo",
        "Ambato": "Productor", "Riobamba": "Productor", "Latacunga": "Productor"}
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# Lectura desde db SQLite
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM panel_semanal", conn, parse_dates=["semana"])
conn.close()

# Formato ancho: una columna por mercado
precios = df.pivot(index="semana", columns="mercado", values="precio_kg")

# Variación semanal: diferencia de logaritmos (aprox. variación porcentual)
variacion = np.log(precios).diff().dropna()

# P1. Serie temporal. Precio promedio de los 6 mercados
promedio = precios.mean(axis=1)
tendencia = promedio.rolling(52, center=True).mean()   # media móvil de un año
print("Precio promedio anual (USD/kg):")
print(promedio.groupby(promedio.index.year).mean().round(3).to_string())

fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(promedio.index, promedio, color="gray", linewidth=0.8, label="Promedio semanal")
ax.plot(tendencia.index, tendencia, color="black", linewidth=2, label="Media móvil de 52 semanas")
eventos = {"Paro oct. 2019": "2019-10-03", "Inicio pandemia": "2020-03-16", "Paro jun. 2022": "2022-06-13"}
for nombre, fecha in eventos.items():
    ax.axvline(pd.Timestamp(fecha), color="red", linestyle="--", linewidth=1)
    ax.text(pd.Timestamp(fecha), promedio.max(), nombre, rotation=90,
            va="top", ha="right", fontsize=9, color="red")
ax.set(title="Precio mayorista de la papa superchola, promedio de 6 mercados",
       xlabel="Semana", ylabel="USD/kg")
ax.legend(loc="upper left")
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(FIG_DIR / "01_serie_precio.png", dpi=150)
plt.close(fig)

# P2. Diagrama de cajas. Estacionalidad: precio relativo al promedio de su año
indice = precios / precios.groupby(precios.index.year).transform("mean")
indice = indice.stack().rename("indice").reset_index()
indice["mes"] = indice["semana"].dt.month
print("\nÍndice estacional por mes (mediana, 1 = promedio del año):")
print(indice.groupby("mes")["indice"].median().round(3).to_string())

fig, ax = plt.subplots(figsize=(10, 5))
sns.boxplot(data=indice, x="mes", y="indice", color="skyblue", fliersize=2, ax=ax)
ax.axhline(1, color="black", linestyle="--", linewidth=1)
ax.set_xticks(range(12), MESES)
ax.set(title="Estacionalidad del precio (6 mercados, 2013-2025)",
       xlabel="Mes", ylabel="Precio / promedio del año")
ax.grid(alpha=0.3, axis="y")
fig.tight_layout()
fig.savefig(FIG_DIR / "02_estacionalidad.png", dpi=150)
plt.close(fig)

# P3. Diagrama de cajas. Diferencia de cada mercado respecto al promedio de la semana
dif = (precios.div(promedio, axis=0) - 1) * 100
dif = dif.stack().rename("dif_pct").reset_index()
dif["tipo"] = dif["mercado"].map(TIPO)
orden = dif.groupby("mercado")["dif_pct"].median().sort_values(ascending=False)
print("\nDiferencia mediana respecto al promedio semanal (%):")
print(orden.round(1).to_string())

fig, ax = plt.subplots(figsize=(10, 5))
sns.boxplot(data=dif, x="mercado", y="dif_pct", hue="tipo", order=orden.index,
            palette={"Consumo": "tab:orange", "Productor": "tab:green"}, fliersize=2, ax=ax)
ax.axhline(0, color="black", linestyle="--", linewidth=1)
ax.set(title="Diferencia de precio respecto al promedio de los 6 mercados",
       xlabel="", ylabel="Diferencia (%)")
ax.legend(title="Mercado")
ax.grid(alpha=0.3, axis="y")
fig.tight_layout()
fig.savefig(FIG_DIR / "03_diferencia_mercados.png", dpi=150)
plt.close(fig)

# P4. Mapa de calor. Correlación de las variaciones semanales
print(f"\nCorrelación media entre mercados -> niveles: "
      f"{precios.corr().values[np.triu_indices(6, 1)].mean():.2f} | "
      f"variaciones: {variacion.corr().values[np.triu_indices(6, 1)].mean():.2f}")
print("\nCorrelación de Quito con la variación de otros mercados k semanas antes:")
rezagos = pd.DataFrame({k: variacion.drop(columns="Quito").shift(k).corrwith(variacion["Quito"])
                        for k in range(4)})
print(rezagos.round(2).to_string())

fig, ax = plt.subplots(figsize=(7, 6))
sns.heatmap(variacion.corr(), cmap="Blues", vmin=0, vmax=1, annot=True, fmt=".2f",
            linewidths=0.5, cbar_kws={"label": "Correlación"}, ax=ax)
ax.set(title="Correlación de las variaciones semanales de precio", xlabel="", ylabel="")
fig.tight_layout()
fig.savefig(FIG_DIR / "04_correlacion_mercados.png", dpi=150)
plt.close(fig)

# P5. Serie temporal. Volatilidad: desviación estándar móvil de 52 semanas
volatilidad = variacion.rolling(52).std() * 100
print("\nVolatilidad media por año (% semanal):")
print(volatilidad.mean(axis=1).groupby(volatilidad.index.year).mean().round(2).to_string())

fig, ax = plt.subplots(figsize=(11, 5))
for mercado in volatilidad.columns:
    ax.plot(volatilidad.index, volatilidad[mercado], linewidth=0.8, alpha=0.6, label=mercado)
ax.plot(volatilidad.index, volatilidad.mean(axis=1), color="black", linewidth=2, label="Promedio")
ax.set(title="Volatilidad del precio (desviación estándar móvil de 52 semanas)",
       xlabel="Semana", ylabel="Variación semanal (%)")
ax.legend(ncol=4)
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(FIG_DIR / "05_volatilidad.png", dpi=150)
plt.close(fig)

print(f"\nFiguras guardadas en {FIG_DIR}")