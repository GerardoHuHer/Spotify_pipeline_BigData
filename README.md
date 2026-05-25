# Spotify Medallion Pipeline 🎧

Pipeline de análisis de datos de Spotify con arquitectura **Bronze → Silver → Gold → ML**,
construido con **PySpark** y visualizado con **Streamlit + Plotly**.

---

## Estructura del proyecto

```
spotify_pipeline/
├── data/
│   └── generate_sample_data.py     # Genera JSONs de prueba estilo Spotify
│
├── pipeline/
│   ├── bronze_layer.py             # Ingesta raw → bucket/reproduccion/bronze/
│   ├── silver_layer.py             # Transformaciones PySpark → .../silver/ (Parquet)
│   ├── gold_layer.py               # Agregaciones analíticas → .../gold/ (Parquet)
│   └── ml_layer.py                 # 3 modelos ML → .../ml/ (Parquet + JSON)
│
├── dashboard/
│   └── app.py                      # Streamlit dashboard (8 pestañas, Plotly)
│
├── bucket/                         # Simulación local de MinIO
│   └── reproduccion/
│       ├── bronze/                 # JSONs crudos + _meta/
│       ├── silver/                 # Parquet por dimensión + fact table
│       ├── gold/                   # Parquet por insight (G01–G15)
│       └── ml/                     # Resultados de modelos ML (Parquet + JSON)
│
├── run_pipeline.py                 # Orquestador principal
└── requirements.txt
```

---

## Instalación

```bash
cd spotify_pipeline
pip install -r requirements.txt
```

> **Java requerido** para PySpark. En macOS/Linux: `brew install openjdk` o `sudo apt install default-jdk`.

---

## Ejecución rápida (pipeline completo + datos de prueba)

```bash
python run_pipeline.py --generate-data
```

Esto ejecuta en orden:
1. **Genera** 4 archivos JSON con ~4 500 registros (2020-2026)
2. **Bronze**: copia los JSON a `bucket/reproduccion/bronze/` + metadata SHA256
3. **Silver**: PySpark limpia, transforma y escribe Parquet (fact + 6 dimensiones)
4. **Gold**: PySpark computa los 15 insights y escribe Parquet por insight
5. **ML**: entrena los 3 modelos y escribe resultados en `bucket/reproduccion/ml/`

---

## Ejecución por capas

```bash
python run_pipeline.py --layer bronze
python run_pipeline.py --layer silver
python run_pipeline.py --layer gold
python run_pipeline.py --layer ml      # solo ML, sin re-correr todo el pipeline
```

---

## Dashboard Streamlit

```bash
streamlit run dashboard/app.py
```

Abre http://localhost:8501 en tu navegador.

### Pestañas disponibles

| Pestaña | Contenido |
|---|---|
| 📊 Resumen General | KPIs globales, distribución por tipo de contenido |
| ⏱️ Actividad Temporal | Por hora, día, mes, año, franja horaria |
| 🎵 Música & Artistas | Top artistas, canciones completas, tasa de salto, sesiones |
| 📻 Podcasts | Top 20 shows por horas escuchadas |
| 📚 Audiolibros | Top 10 audiolibros |
| 🌍 Por País | Top 10 canciones por país |
| 💡 Recomendación de Plan | Mensual vs anual con análisis de costo en MXN |
| 🤖 Machine Learning | 3 modelos orientados a decisiones del analista |

---

## Modelos de Machine Learning

| Modelo | Algoritmo | Pregunta que responde |
|---|---|---|
| ML1 | Random Forest | ¿El algoritmo de Spotify te sirve o te atrapa? |
| ML2 | K-Means | ¿Cuál es tu perfil de oyente y cómo cambia en el tiempo? |
| ML3 | Gradient Boosting | ¿Cuándo y por qué abandonas la escucha? |

---

## Usar tus propios datos de Spotify

1. Solicita tus datos en **Spotify → Configuración → Privacidad → Descargar mis datos**
2. Coloca los archivos `Streaming_History_Audio_*.json` en la carpeta `data/`
3. Ejecuta el pipeline:

```bash
python run_pipeline.py
```

> Si ya tienes Bronze/Silver/Gold y solo quieres correr el ML:
> ```bash
> python run_pipeline.py --layer ml
> ```

---

## Flujo de datos (Medallion Architecture)

```
JSONs crudos (Spotify export)
        │
        ▼
 ┌─────────────┐
 │   BRONZE    │  Ingesta tal cual + checksum SHA256
 │  /bronze/   │  Sin transformaciones
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │   SILVER    │  PySpark transformations:
 │  /silver/   │  - Deduplicación por clave natural
 │             │  - Normalización texto (sin emojis)
 │             │  - Split timestamp → año/mes/día/hora
 │             │  - Derivación tipo_arte
 │             │  - Mapeo código → nombre país
 │             │  - Esquema estrella (fact + 6 dims)
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │    GOLD     │  15 insights analíticos (Parquet)
 │   /gold/    │  Listos para consumo en dashboard
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │     ML      │  3 modelos scikit-learn:
 │    /ml/     │  - ML1: Random Forest (algoritmo vs elección)
 │             │  - ML2: K-Means (perfil semanal de oyente)
 │             │  - ML3: Gradient Boosting (fatiga y skip)
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │  STREAMLIT  │  Dashboard interactivo (8 pestañas)
 │  Dashboard  │  Plotly charts, KPIs, visualizaciones ML
 └─────────────┘
```

---

## Consideraciones éticas

- La **IP** está disponible en el dataset pero **no se usa en ningún insight** del Gold layer ni en los modelos ML
- Se recomienda **anonimizarla** antes de compartir los datos (hash MD5/SHA256)
- El país se normaliza a nombre legible pero no se combina con IP para evitar geolocalización precisa
- El modo incógnito se respeta: puede filtrarse en Silver antes de pasar a Gold