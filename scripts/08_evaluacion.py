import sqlite3
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

DB_PATH = Path("data/processed/precios_papa.db")
FIG_DIR = Path("reports/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# Lectura desde db SQLite
conn = sqlite3.connect(DB_PATH)
pred = pd.read_sql("SELECT * FROM predicciones_optimizadas", conn, parse_dates=["semana_objetivo"])
metricas = pd.read_sql("SELECT * FROM metricas_optimizadas", conn)
conn.close()

# Modelo elegido en 07. El ingenuo repite el precio conocido 4 semanas antes (lag_0)
elegido = metricas.loc[metricas["elegido"] == 1, "modelo"].iloc[0]
df = pred[pred["modelo"] == elegido].copy()
df["error_modelo"] = (df["objetivo"] - df["prediccion"]).abs()
df["error_ingenuo"] = (df["objetivo"] - df["lag_0"]).abs()
df["mes"] = df["semana_objetivo"].dt.month
print(f"Modelo evaluado: {elegido} | Filas: {len(df):,}")
print(f"Semanas en que el modelo se equivoca menos que el ingenuo: "
      f"{(df['error_modelo'] < df['error_ingenuo']).mean() * 100:.1f} %")

# M3. Serie temporal. Precio real vs predicciones en 2025, un panel por mercado
fig, axes = plt.subplots(2, 3, figsize=(14, 7), sharex=True, sharey=True)
for ax, (mercado, d) in zip(axes.flat, df.groupby("mercado")):
    ax.plot(d["semana_objetivo"], d["objetivo"], color="black", linewidth=1.8, label="Precio real")
    ax.plot(d["semana_objetivo"], d["prediccion"], color="tab:blue", linewidth=1.2, label=elegido)
    ax.plot(d["semana_objetivo"], d["lag_0"], color="gray", linestyle="--", linewidth=1, label="Ingenuo")
    ax.set_title(mercado)
    ax.grid(alpha=0.3)
    ax.tick_params(axis="x", rotation=45)
axes[0, 0].legend(fontsize=8)
fig.supylabel("USD/kg")
fig.suptitle("Precio real vs pronóstico a 4 semanas en 2025")
fig.tight_layout()
fig.savefig(FIG_DIR / "06_prediccion_vs_real.png", dpi=150)
plt.close(fig)

# M3. Barras agrupadas. Error medio por mercado: modelo vs ingenuo
por_mercado = df.groupby("mercado")[["error_modelo", "error_ingenuo"]].mean()
por_mercado["mejora_%"] = (1 - por_mercado["error_modelo"] / por_mercado["error_ingenuo"]) * 100
por_mercado = por_mercado.sort_values("mejora_%", ascending=False)
print("\nMAE por mercado (USD/kg):")
print(por_mercado.round(4).to_string())

fig, ax = plt.subplots(figsize=(10, 5))
por_mercado[["error_modelo", "error_ingenuo"]].plot.bar(
    ax=ax, color=["tab:blue", "gray"], rot=0)
ax.legend([elegido, "Ingenuo"])
ax.set(title="Error medio por mercado en 2025", xlabel="", ylabel="MAE (USD/kg)")
ax.grid(alpha=0.3, axis="y")
fig.tight_layout()
fig.savefig(FIG_DIR / "07_error_por_mercado.png", dpi=150)
plt.close(fig)

# M3. Barras agrupadas + línea. Error medio por mes y precio real promedio
por_mes = df.groupby("mes").agg(error_modelo=("error_modelo", "mean"),
                                error_ingenuo=("error_ingenuo", "mean"),
                                precio=("objetivo", "mean"))
print("\nMAE y precio real promedio por mes de 2025:")
print(por_mes.round(3).to_string())

fig, ax = plt.subplots(figsize=(11, 5))
por_mes[["error_modelo", "error_ingenuo"]].plot.bar(ax=ax, color=["tab:blue", "gray"], rot=0)
ax.set_xticks(range(12), MESES)
ax.set(title="Error medio por mes en 2025 y precio real", xlabel="Mes", ylabel="MAE (USD/kg)")
ax.legend([elegido, "Ingenuo"], loc="upper left")
ax.grid(alpha=0.3, axis="y")
ax2 = ax.twinx()   # segundo eje vertical para el precio
ax2.plot(range(12), por_mes["precio"], color="black", marker="o", label="Precio real")
ax2.set_ylabel("Precio real promedio (USD/kg)")
ax2.legend(loc="upper right")
fig.tight_layout()
fig.savefig(FIG_DIR / "08_error_por_mes.png", dpi=150)
plt.close(fig)

print(f"\nFiguras guardadas en {FIG_DIR}")