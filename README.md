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

## Estructura del JSON de Spotify

El pipeline espera archivos con el formato del historial extendido de Spotify. Cada registro tiene esta estructura:

```json
{
  "ts":                                  "2020-06-21T19:33:14Z",
  "platform":                            "Android",
  "ms_played":                           4522,
  "conn_country":                        "MX",
  "ip_addr":                             "189.xx.xx.xx",
  "master_metadata_track_name":          "Count on Me",
  "master_metadata_album_artist_name":   "Bruno Mars",
  "master_metadata_album_album_name":    "Doo-Wops & Hooligans",
  "spotify_track_uri":                   "spotify:track:7l1qvxWjxcKpB9PCtBuTbU",
  "episode_name":                        null,
  "episode_show_name":                   null,
  "spotify_episode_uri":                 null,
  "audiobook_title":                     null,
  "audiobook_uri":                       null,
  "audiobook_chapter_uri":               null,
  "audiobook_chapter_title":             null,
  "reason_start":                        "fwdbtn",
  "reason_end":                          "fwdbtn",
  "shuffle":                             true,
  "skipped":                             false,
  "offline":                             false,
  "offline_timestamp":                   null,
  "incognito_mode":                      false
}
```

| Campo | Descripción |
|---|---|
| `ts` | Timestamp de la reproducción (UTC) |
| `ms_played` | Milisegundos que se reprodujo el contenido |
| `platform` | Dispositivo y sistema operativo |
| `conn_country` | País de conexión (código ISO) |
| `ip_addr` | IP del dispositivo ⚠️ dato sensible |
| `master_metadata_track_name` | Nombre de la canción (null si es podcast/audiolibro) |
| `master_metadata_album_artist_name` | Artista |
| `spotify_track_uri` | ID único de la canción en Spotify |
| `episode_name` / `episode_show_name` | Nombre del episodio y podcast (null si es música) |
| `audiobook_title` / `audiobook_uri` | Datos del audiolibro (null si es música/podcast) |
| `reason_start` | Por qué inició: `clickrow`, `playbtn`, `trackdone`, `autoplay`, `fwdbtn`, `backbtn` |
| `reason_end` | Por qué terminó: `trackdone`, `fwdbtn`, `endplay`, `logout` |
| `shuffle` | Si el modo aleatorio estaba activo |
| `skipped` | Si el usuario saltó la canción |
| `offline` | Si se reprodujo sin conexión |
| `incognito_mode` | Si estaba en modo privado |

> **Nota:** Los campos de música, podcast y audiolibro son mutuamente excluyentes — cuando uno tiene valor, los otros son `null`. El pipeline deriva automáticamente el campo `tipo_arte` (`musica`, `podcast`, `audiolibro`) basándose en cuál URI es no nulo.

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