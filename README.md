# Papa superchola: precios mayoristas en Ecuador

Adquisición, limpieza, almacenamiento en una db SQLite, análisis exploratorio, visualización y pronóstico de los precios mayoristas de la papa superchola en seis mercados del Ecuador, con datos del Sistema de Información Pública Agropecuaria (SIPA).

El proyecto tiene dos fases. La fase 1 (partes 1 a 3) limpia, explora y visualiza los datos. La fase 2 (parte 4) usa esos resultados para pronosticar el precio con 4 semanas de anticipación.

## 1. Datos

| Característica | Valor |
|---|---|
| Fuente | SIPA, Ministerio de Agricultura y Ganadería (MAG), módulo *Consulta Personalizada* de precios en mercados mayoristas |
| Parámetros de la consulta | Producto: Papa Súper Chola · Lugar: todos los mercados · Fechas: 01/01/2012 – 31/08/2026 |
| Fecha de descarga | 29/09/2026 |
| Contenido | Precio mayorista registrado en los días de feria de cada mercado |
| Periodo | 02/01/2012 – 28/08/2026 |
| Registros | 17,012 originales - 10,643 tras la limpieza - 4,068 en el panel semanal |
| Archivo original | `Rep_Pre_Prod_X_MercCGINA.csv` (4.06 MB) |

Cada fila del dataset es un precio registrado en un mercado en un día. Los mercados registran entre 2 y 4 precios por semana, en días distintos.

El CSV original viene en codificación UTF-16. La codificación es la regla con la que un archivo guarda cada carácter como bytes. UTF-16 usa 2 bytes por carácter, sin embargo pandas lee por defecto en UTF-8, ya que es la codificación mas común, así que si no se le indica otra al momento de leer el archivo da error o muestra caracteres ilegibles. Por eso el archivo se lee con encoding="utf-16". El original no se convierte ya que la copia en Parquet ya no depende de esa codificación.

**Elección del producto.** Se revisó la cobertura de los productos disponibles en el SIPA. La papa superchola es el producto con más mercados (19) y con series completas en los mercados de Quito, Guayaquil y Cuenca. También se consideró el banano, pero tiene solo 7 mercados y casi no presenta estacionalidad.

## 2. Estructura del repositorio

```
├── data/
│   ├── raw/          # CSV original, solo lectura
│   ├── interim/      # copia de trabajo en .parquet
│   └── processed/    # db SQLite con datos limpios, panel semanal, variables y predicciones
├── scripts/
│   ├── 00_adquisicion.py          # lee el CSV original y crea la copia de trabajo
│   ├── 01_limpieza.py             # limpieza y carga en la db
│   ├── 02_agregacion_semanal.py   # panel mercado x semana
│   ├── 03_eda.py                  # análisis exploratorio
│   ├── 04_visualizacion.py        # genera las gráficas de la fase 1
│   ├── 05_variables.py            # variables para el modelado
│   ├── 06_modelos.py              # modelos con valores por defecto
│   ├── 07_optimizacion.py         # búsqueda de hiperparámetros
│   └── 08_evaluacion.py           # evaluación del modelo elegido
├── reports/
│   └── figures/                   # gráficas en .png
├── requirements.txt
└── README.md
```

En este caso el CSV original sí se sube al repositorio debido a que se descarga a mano desde el SIPA y no se puede obtener con un script.

## 3. Ejecución

Los scripts se ejecutan en orden desde el directorio raíz del proyecto:

```bash
pip install -r requirements.txt
python scripts/00_adquisicion.py
python scripts/01_limpieza.py
python scripts/02_agregacion_semanal.py
python scripts/03_eda.py
python scripts/04_visualizacion.py
python scripts/05_variables.py
python scripts/06_modelos.py
python scripts/07_optimizacion.py
python scripts/08_evaluacion.py
```

Las dependencias son: pandas, numpy, pyarrow (para leer y guardar Parquet), matplotlib, seaborn y scikit-learn (modelos). La db se maneja con `sqlite3` que viene incluido en Python. `07_optimizacion.py` tarda unos 3 minutos; los demás scripts, segundos.

## 4. Proceso

```
CSV original  →  copia .parquet  →  limpieza  →  db SQLite  →  panel semanal  →  EDA y gráficas
   (raw)           (interim)                     (processed)    (processed)

panel semanal  →  variables  →  modelos  →  optimización  →  evaluación
```

1. **Adquisición** 
`00_adquisicion.py` lee el CSV indicando su codificación (UTF-16) y la coma decimal, y da nombres descriptivos a las columnas. Luego guarda una copia en Parquet para conservar los tipos de datos.
2. **Limpieza** 
`01_limpieza.py` aplica los criterios de limpieza y guarda el resultado en la db `precios_papa.db`, en una tabla `precios`.
3. **Agregación semanal** 
`02_agregacion_semanal.py` calcula el precio promedio de cada mercado por semana y guarda la tabla `panel_semanal` en la misma db.
4. **EDA** 
`03_eda.py` lee el panel desde la db, genera la metadata y describe cada campo.
5. **Gráficas** 
`04_visualizacion.py` genera una gráfica por pregunta con Matplotlib y Seaborn.
6. **Variables** 
`05_variables.py` construye, para cada semana y mercado, las variables conocidas en esa semana y el precio de 4 semanas después. Guarda la tabla `variables` en la db.
7. **Modelos** 
`06_modelos.py` entrena y evalúa cinco modelos con sus valores por defecto. Guarda predicciones y métricas en la db.
8. **Optimización** 
`07_optimizacion.py` busca los mejores hiperparámetros del Random Forest y del Gradient Boosting, y elige el modelo final.
9. **Evaluación** 
`08_evaluacion.py` analiza los errores del modelo elegido por mercado y por mes, y genera las gráficas de la fase 2.

## 5. Parte 1: Limpieza de datos

El objetivo es obtener series de precio comparables en el tiempo y entre mercados. Un mismo producto en una misma presentación en mercados con registros ininterrumpidos. Se aplica un criterio de limpieza solo si afecta el objetivo planteado.

| # | Criterio | Filas eliminadas | ¿Por qué? |
|---|---|---:|---|
| 1 | Duplicados exactos | 0 | Se verificó que no existen. |
| 2 | Presentaciones en saco (120, 140 y 150 lb) | 1,862 | El quintal de 100 lb representa el 89% de los registros. En Cuenca el saco de 140 lb cuesta alrededor de 19% más por kg que el quintal. |
| 3 | Mercados fuera del alcance | 4,507 | Se trabaja con los 6 mercados con series continuas en 2012-2026. |

**Resultado:** 17,012 - 10,643 filas.

**Mercados seleccionados**

| Mercado | Función | Registros |
|---|---|---:|
| Quito (MMQ-EP) | Consumo | 1,429 |
| Guayaquil (TTV) | Consumo | 1,926 |
| Cuenca (El Arenal) | Consumo | 1,398 |
| Ambato (EP-EMA) | Zona productora | 2,292 |
| Riobamba (EP-EMMPA) | Zona productora | 2,269 |
| Latacunga | Zona productora | 1,329 |


- **Precios extremos:** coinciden con eventos reales como el paro nacional de octubre de 2019 (Guayaquil llegó a 1.54 USD/kg) y el de junio de 2022. Son variaciones reales del mercado.

### Agregación semanal

Cada mercado registra precios en días distintos y con distinta frecuencia, así que se calcula el precio promedio por semana en cada mercado.

| Decisión | ¿Por qué? |
|---|---|
| Periodo 2013-2025 | En 2012 hay huecos de hasta 17 semanas seguidas (Guayaquil, de agosto a diciembre). Al trabajar con años completos cada mes aparece el mismo número de veces. |
| Interpolación lineal | En 2013-2025 la racha más larga sin datos es de 4 semanas (Ambato, inicio de la pandemia en 2020). Solo 33 de 4,068 valores (0.81%) son interpolados. |
| Columna `interpolado` | Marca los valores interpolados para poder excluirlos al evaluar los modelos. |

6 mercados × 678 semanas = 4,068 filas

## 6. Parte 2: Análisis exploratorio

El panel se lee desde la db con `pd.read_sql`. SQLite no guarda fechas ni booleanos, así que `semana` e `interpolado` se restauran a su tipo al leer.

### Metadata por campo

| Campo | Tipo | Nulos (%) | Valores únicos |
|---|---|---:|---:|
| semana | fecha | 0 | 678 semanas |
| mercado | texto | 0 | 6 mercados |
| precio_kg | decimal | 0 | 864 |
| interpolado | booleano | 0 | 2 |

### Precio por mercado (USD/kg, 2013-2025)

| Mercado | Media | Mediana | Mín | Máx | Coef. de variación |
|---|---:|---:|---:|---:|---:|
| Cuenca | 0.534 | 0.529 | 0.243 | 0.992 | 0.252 |
| Guayaquil | 0.484 | 0.470 | 0.240 | 1.304 | 0.287 |
| Ambato | 0.450 | 0.441 | 0.225 | 0.841 | 0.287 |
| Quito | 0.410 | 0.397 | 0.198 | 0.889 | 0.311 |
| Latacunga | 0.396 | 0.375 | 0.198 | 0.757 | 0.303 |
| Riobamba | 0.386 | 0.365 | 0.186 | 0.750 | 0.306 |

Quito es un mercado de consumo, pero su precio es menor que el de Ambato y cercano al de Riobamba y Latacunga. Esto llevó a reformular la pregunta 3.

**Ciclo entre años:** los seis mercados suben y bajan en los mismos años. 2024 tiene el precio más alto (0.64 USD/kg en promedio) y 2020 el más bajo (0.32).

## 7. Parte 3: Visualización

Se generan cinco gráficas, una por pregunta:

| Figura | Técnica | Opción avanzada |
|---|---|---|
| 01 | Serie temporal | Media móvil de 52 semanas y eventos anotados |
| 02 | Diagrama de cajas | Precio relativo al promedio de su año, para separar la estacionalidad del ciclo entre años |
| 03 | Diagrama de cajas | Color según la función del mercado y orden por mediana |
| 04 | Mapa de calor | Correlación de las variaciones semanales, no de los precios |
| 05 | Serie temporal | Desviación estándar móvil por mercado y promedio |

### Pregunta 1: ¿Cómo ha evolucionado el precio entre 2013 y 2025?

![Serie del precio](reports/figures/01_serie_precio.png)

**Respuesta**

- El precio oscila entre 0.32 USD/kg (promedio de 2020) y 0.64 (2024), sin una tendencia sostenida de subida o bajada.
- La media móvil muestra ciclos de 2 a 3 años, con máximos en 2014, 2019, 2022 y 2024.
- Tras el inicio de la pandemia el precio cayó al mínimo del periodo, a mediados de 2020.
- El ciclo es compatible con la respuesta de los productores al precio: siembran más cuando el precio es alto, y la mayor oferta lo hace bajar.

### Pregunta 2: ¿Existe un patrón estacional?

![Estacionalidad](reports/figures/02_estacionalidad.png)

**Respuesta**

- Sí. El precio es más bajo de abril a junio, alrededor de 15% bajo el promedio del año.
- Es más alto de noviembre a enero, entre 12% y 15% sobre el promedio.
- El patrón se repite en los seis mercados.
- Cada precio se divide para el promedio de su año para poder comparar un año caro (2024) con uno barato (2020) en la misma escala, 1.10 significa 10% sobre el promedio de ese año.

### Pregunta 3: ¿Qué determina la diferencia de precio entre mercados?

![Diferencia entre mercados](reports/figures/03_diferencia_mercados.png)

**Respuesta**

- Tomando como referencia el promedio de los 6 mercados, Cuenca está 21% sobre el promedio y Guayaquil 8%, mientras que Riobamba está 13% por debajo.
- Quito está 8% bajo el promedio, al nivel de los mercados productores.
- Los dos mercados más caros son los más alejados de la zona productora de la Sierra centro. La ubicación parece explicar la diferencia mejor que la función del mercado.

### Pregunta 4: ¿Los precios de los mercados se mueven juntos de una semana a otra? ¿Un cambio de precio en un mercado se repite después en otro?

![Correlación entre mercados](reports/figures/04_correlacion_mercados.png)

**Respuesta**

- La correlación media entre los precios es de 0.91, pero entre las variaciones semanales es de solo 0.34. La primera es alta porque todos los precios comparten el mismo ciclo de años; la segunda mide si los mercados suben o bajan juntos en la misma semana.
- Quito y Guayaquil son los que más se mueven juntos (0.56). Cuenca es el que menos se mueve con los demás (0.18 a 0.29).
- Se comparó la variación de Quito con la de los otros mercados 1 a 3 semanas antes. La correlación es prácticamente nula. Los cambios ocurren en la misma semana.

### Pregunta 5: ¿Qué tan volátil es el precio y ha cambiado en el tiempo?

![Volatilidad](reports/figures/05_volatilidad.png)

**Respuesta**

- La variación semanal típica pasó de 7-9% (2014-2019) a 10-11.5% (2020-2025): la volatilidad aumentó alrededor de un tercio.
- Cuenca es el mercado más estable (coeficiente de variación 0.25).
- El salto de Guayaquil en octubre de 2019 dura exactamente 52 semanas, es el efecto del paro.

## 8. Parte 4: Modelado

El objetivo es responder tres preguntas:

| # | Pregunta |
|---|---|
| M1 | ¿Se puede predecir el precio de dentro de 4 semanas mejor que repitiendo el precio de esta semana? |
| M2 | ¿Ayuda conocer los precios recientes de los otros mercados? |
| M3 | ¿En qué mercados y en qué momentos se equivoca más el modelo? |

### Horizonte de 4 semanas

El modelo de referencia es el **ingenuo**: predice que el precio será igual al de esta semana. Mientras más lejos se predice, peor le va:

| Horizonte | Correlación del precio con el de *h* semanas antes | Error del ingenuo en 2025 |
|---|---:|---:|
| 1 semana | 0.94 | 10.3% |
| 4 semanas | 0.81 | 20.5% |

A 1 semana el ingenuo es casi imposible de superar y el pronóstico tiene poca utilidad práctica. A 4 semanas hay margen para mejorar, y un mes de anticipación sirve para decidir cuándo vender o cuánto almacenar.

### Variables

Cada fila es una semana *t* de un mercado. Con lo que se conoce en esa semana se predice el precio de la semana *t + 4*.

| Variable | Qué representa | Relación con la fase 1 |
|---|---|---|
| `lag_0` a `lag_3` | Precio de esta semana y de las 3 anteriores | P1: el precio cambia poco de una semana a otra |
| `media_4` | Promedio de las últimas 4 semanas | Suaviza las variaciones semanales |
| `lag_estacional` | Precio de la misma semana del año anterior | P2: estacionalidad |
| `mes` | Mes de la semana que se predice | P2: estacionalidad |
| `mercado` | Una columna 0/1 por mercado | P3: cada mercado tiene su propio nivel |
| `otros_mercados` | Precio promedio de los otros 5 mercados | Solo para M2 (P4) |

El script verifica que el valor a predecir sea el precio real de 4 semanas después, para asegurar que ninguna variable use información del futuro.

### División de los datos

| Conjunto | Periodo | Filas |
|---|---|---:|
| Entrenamiento | 2014-2024 | 3,444 |
| Prueba | 2025 | 312 |

La división no es aleatoria: si el modelo entrenara con semanas de 2025, usaría el futuro para predecir el pasado. Se pierde 2013 porque `lag_estacional` necesita un año previo.

### Modelos

| Modelo | Cómo predice |
|---|---|
| Ingenuo | Repite el precio de esta semana |
| Ingenuo estacional | Repite el precio de la misma semana del año anterior |
| Regresión lineal | Combinación lineal de las variables |
| Random Forest | Promedio de muchos árboles de decisión, cada uno entrenado con una muestra distinta de los datos |
| Gradient Boosting | Árboles en secuencia, cada uno corrige los errores del anterior |

**Métricas:** MAE (error medio en USD/kg), MAPE (error medio en %) y mejora sobre el ingenuo.

### Pregunta M1: ¿Se puede predecir el precio de dentro de 4 semanas mejor que repitiendo el precio de esta semana?

Error en 2025 con los valores por defecto de cada modelo:

| Modelo | MAE (USD/kg) | MAPE | Mejora sobre el ingenuo |
|---|---:|---:|---:|
| Ingenuo | 0.090 | 20.5% | — |
| Ingenuo estacional | 0.198 | 54.7% | -120.6% |
| Regresión lineal | 0.082 | 18.4% | 9.4% |
| Random Forest | 0.078 | 17.7% | 12.8% |
| Gradient Boosting | 0.080 | 18.1% | 11.5% |

El precio de esta semana (`lag_0`) concentra el 73% de la importancia de las variables del Random Forest. La estacionalidad (`lag_estacional` y `mes`) aporta un 11%.

**Respuesta** (se completa con la optimización)

- En 2025 los tres modelos superan al ingenuo entre 9% y 13%.
- El ingenuo estacional es el peor: repite los precios de 2024, el año más caro del periodo.

### Pregunta M2: ¿Ayuda conocer los precios recientes de los otros mercados?

| Modelo | MAE sin otros mercados | MAE con otros mercados | Cambio |
|---|---:|---:|---:|
| Regresión lineal | 0.0815 | 0.0808 | -0.9% |
| Random Forest | 0.0784 | 0.0800 | +2.0% |
| Gradient Boosting | 0.0796 | 0.0781 | -1.9% |

**Respuesta**

- No. Los cambios son menores al 2% y van en ambas direcciones.
- Confirma lo que mostró la pregunta 4: un cambio de precio en un mercado no se repite después en otro. El precio actual de cada mercado ya contiene esa información.

### Optimización de hiperparámetros

Se buscan los mejores hiperparámetros del Random Forest (36 combinaciones) y del Gradient Boosting (18 combinaciones) con `GridSearchCV`.

**Validación cruzada temporal.** La validación cruzada normal mezcla las semanas sin respetar el orden, y el modelo entrenaría con el futuro para validar con el pasado. `TimeSeriesSplit` entrena siempre con el pasado y valida con el periodo siguiente:

| Partición | Entrena | Valida |
|---|---|---|
| 1 | 2014-01 a 2015-10 | 2015-10 a 2017-08 |
| 2 | 2014-01 a 2017-08 | 2017-08 a 2019-06 |
| 3 | 2014-01 a 2019-06 | 2019-06 a 2021-04 |
| 4 | 2014-01 a 2021-04 | 2021-05 a 2023-02 |
| 5 | 2014-01 a 2023-02 | 2023-03 a 2024-12 |

2025 no participa en la búsqueda.

**Mejores hiperparámetros**

| Modelo | Hiperparámetros |
|---|---|
| Random Forest | 300 árboles, profundidad máxima 5, mínimo 20 filas por hoja |
| Gradient Boosting | 100 árboles, profundidad máxima 2, tasa de aprendizaje 0.1 |

Ambos eligieron árboles poco profundos: con datos ruidosos, los modelos más simples funcionan mejor con datos nuevos.

**Resultados (MAE en USD/kg)**

| Modelo | Valid. cruzada, por defecto | Valid. cruzada, optimizado | Valid. cruzada, ingenuo | 2025, por defecto | 2025, optimizado |
|---|---:|---:|---:|---:|---:|
| Random Forest | 0.0647 | 0.0594 | 0.0547 | 0.0784 | 0.0812 |
| Gradient Boosting | 0.0638 | 0.0606 | 0.0547 | 0.0796 | 0.0785 |

**Elección del modelo:** se elige por el error en validación cruzada (Random Forest, 0.0594), no por el error en 2025, para que el año de prueba no influya en la elección. En 2025 el Gradient Boosting fue algo mejor (0.0785 frente a 0.0812), pero las predicciones de ambos modelos son casi idénticas (correlación de 0.993), así que las conclusiones no cambian.

**Respuesta a M1**

- No de forma consistente.
- La optimización redujo el error en validación cruzada un 8% (Random Forest) y un 5% (Gradient Boosting), pero en 2025 los cambios fueron pequeños (+3.5% y -1.4%).
- En 2025 el modelo elegido supera al ingenuo en un 9.7%. Pero en la validación cruzada (2015-2024) el ingenuo tiene menos error que todos los modelos (0.0547 frente a 0.0594).
- Con solo precios pasados, es difícil predecir a 4 semanas mejor que repitiendo el precio actual. Tres modelos muy distintos llegan casi al mismo error, lo que indica que el límite está en la información disponible y no en el modelo.

### Pregunta M3: ¿En qué mercados y en qué momentos se equivoca más el modelo?

Se evalúa el modelo elegido (Random Forest optimizado) frente al ingenuo en 2025.

![Predicción vs precio real](reports/figures/06_prediccion_vs_real.png)

![Error por mercado](reports/figures/07_error_por_mercado.png)

![Error por mes](reports/figures/08_error_por_mes.png)

**Respuesta**

- El modelo se equivoca menos que el ingenuo en el 64% de las semanas de 2025 y en los seis mercados. La mejora va de 13% en Guayaquil a 5% en Cuenca.
- Los errores más grandes ocurren cuando el precio cambia bruscamente: la caída de febrero y las subidas de julio y septiembre. Ahí el modelo y el ingenuo fallan de forma parecida.
- La mayor ventaja del modelo está en los picos de precio (enero y octubre). Por la estacionalidad, el modelo predice que esos precios altos no se mantendrán.
- La predicción del modelo es casi la del ingenuo, algo suavizada: ambas van unas 4 semanas detrás del precio real cuando este cambia de dirección. El modelo no anticipa los cambios, solo los modera.
- 2025 siguió casi exactamente el patrón estacional de la pregunta 2, lo que ayuda a explicar por qué el modelo funcionó mejor ese año que en la validación cruzada.

## 9. Evolución de las preguntas

Las preguntas se definieron antes de empezar, pero los resultados de cada etapa obligaron a ajustar algunas.

**Fase 1: pregunta 3**

| | |
|---|---|
| Pregunta original | ¿Los mercados de consumo pagan más que los productores? |
| Qué se observó | En el EDA el precio medio de Quito (0.410 USD/kg) resultó menor que el de Ambato (0.450) y cercano al de Riobamba (0.386) y Latacunga (0.396). Cuenca y Guayaquil sí eran los más caros, pero la clasificación consumo/productor no parecía definir los precios. |
| Nueva pregunta | ¿Qué determina la diferencia de precio entre mercados: su función (consumo o producción) o su ubicación? |

**Fase 2**

| Tema | Plan inicial | Decisión final | ¿Por qué? |
|---|---|---|---|
| Redacción de M1-M3 | Términos técnicos (referencia ingenua, rezagos) | Lenguaje llano | Mismo criterio que la pregunta 4 |
| Horizonte | 1 a 4 semanas | 4 semanas | A 1 semana el ingenuo es casi imposible de superar |
| Modelos | SARIMA y LightGBM | Regresión lineal, Random Forest y Gradient Boosting | SARIMA con estacionalidad semanal es lento e inestable. Todos los modelos están en scikit-learn |
| M2 | Probar si los otros mercados mejoran el pronóstico | Se mantuvo, esperando un resultado negativo | La pregunta 4 mostró que los cambios no se transmiten con rezago. Se confirmó |
| Hipótesis de M3 | La ventaja del modelo en 2025 se concentra en la caída del precio | Parcialmente cierta | La ventaja está en los picos de precio: enero (antes de la caída) y octubre |

## 10. Limitaciones

- El CSV se descarga a mano desde el SIPA así que una nueva descarga podría diferir si el SIPA corrige registros.
- El dataset solo tiene precios, no incluye volúmenes vendidos ni variables como clima o costos de producción.
- Con seis mercados no se puede separar el efecto de la ubicación y el de la función del mercado.
- Una parte del error no se puede predecir: eventos como los paros de 2019 y 2022 no se pueden anticipar con 4 semanas.
- La prueba es un solo año (2025), que siguió el patrón estacional de forma muy marcada. En la validación cruzada el ingenuo fue mejor.

**Trabajo futuro:** los modelos solo usan precios pasados. Las variables externas con más potencial son la superficie sembrada, porque la papa tarda meses en cosecharse y define la oferta futura, y el clima en las zonas productoras (lluvias, heladas). El precio del combustible tendría poco efecto, porque en Ecuador el diésel tiene un precio regulado que cambia pocas veces.
