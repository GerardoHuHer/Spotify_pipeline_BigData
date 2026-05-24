# Spotify Medallion Pipeline 🎧

Pipeline de análisis de datos de Spotify con arquitectura **Bronze → Silver → Gold**,
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
│   └── gold_layer.py               # Agregaciones analíticas → .../gold/ (Parquet)
│
├── dashboard/
│   └── app.py                      # Streamlit dashboard (7 pestañas, Plotly)
│
├── bucket/                         # Simulación local de MinIO
│   └── reproduccion/
│       ├── bronze/                 # JSONs crudos + _meta/
│       ├── silver/                 # Parquet por dimensión + fact table
│       └── gold/                   # Parquet por insight (G01–G15)
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

---

## Ejecución por capas

```bash
python run_pipeline.py --layer bronze
python run_pipeline.py --layer silver
python run_pipeline.py --layer gold
```

---

## Dashboard Streamlit

```bash
streamlit run dashboard/app.py
```

Abre http://localhost:8501 en tu navegador.

### Pestañas disponibles

| Pestaña | Insights |
|---|---|
| 📊 Resumen General | KPIs globales, distribución por tipo |
| ⏱️ Actividad Temporal | Por hora, día, mes, año, franja horaria |
| 🎵 Música & Artistas | Top artistas, canciones completas, tasa de salto, sesiones |
| 📻 Podcasts | Top 20 shows por horas |
| 📚 Audiolibros | Top 10 audiolibros |
| 🌍 Por País | Top 10 canciones por país |
| 💡 Recomendación de Plan | Mensual vs anual con análisis de costo |

---

## Usar tus propios datos de Spotify

1. Solicita tus datos en **Spotify → Configuración → Privacidad → Descargar mis datos**
2. Coloca los archivos `Streaming_History_Audio_*.json` en la carpeta `data/`
3. Ejecuta el pipeline sin `--generate-data`:

```bash
python run_pipeline.py
```

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
 │  /silver/   │  - Deduplicación
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
 └─────────────┘
        │
        ▼
 ┌─────────────┐
 │  STREAMLIT  │  Dashboard interactivo (7 pestañas)
 │  Dashboard  │  Plotly charts, filtros, KPIs
 └─────────────┘
```

---

## Consideraciones éticas (del plan original)

- La **IP** está disponible en el dataset pero **no se usa en ningún insight** del Gold layer
- Se recomienda **anonimizarla** antes de compartir los datos (hash MD5/SHA256)
- El país se normaliza a nombre legible pero no se combina con IP para evitar geolocalización precisa
- El modo incógnito se respeta: puede filtrarse en Silver antes de pasar a Gold
