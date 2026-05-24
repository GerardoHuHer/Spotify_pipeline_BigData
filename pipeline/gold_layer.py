"""
GOLD LAYER  –  Analytical aggregations with PySpark
─────────────────────────────────────────────────────────────────────────────
Reads the cleaned Parquet tables from the Silver layer and produces every
insight described in the analysis plan.

Output tables (Parquet) are written to:
    bucket/reproduccion/gold/<metric_name>/

Insights computed
  G01  – tiempo_total_por_año          Total ms played per year
  G02  – distribucion_tipo_arte        % music / podcast / audiobook
  G03  – tasa_salto                    Skip rate overall & per artist
  G04  – canciones_completas_top       Top tracks by complete listen count
  G05  – actividad_por_hora            Plays & ms by hour of day
  G06  – actividad_por_mes             Plays & ms by month
  G07  – actividad_por_dia_semana      Plays & ms by day of week
  G08  – artistas_top                  Most-played artists (complete listens)
  G09  – sesiones                      Session analysis (gap > 30 min = new)
  G10  – plan_recomendacion            Monthly vs annual plan recommendation
  G11  – top_por_pais                  Top tracks per country
  G12  – generos_por_hora              Artist plays split by hour bucket
  G13  – promedio_sesiones             Avg sessions per day / week / month
  G14  – podcasts_top                  Top podcast shows by time listened
  G15  – audiolibros_top               Top audiobooks by time listened
─────────────────────────────────────────────────────────────────────────────
"""

import json
from pathlib import Path
from datetime import datetime, timezone

from pyspark.sql import SparkSession, DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import LongType

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent
SILVER_PATH = BASE_DIR / "bucket" / "reproduccion" / "silver"
GOLD_PATH   = BASE_DIR / "bucket" / "reproduccion" / "gold"

COMPLETE_LISTEN_MS = 30_000   # > 30 s = "complete" listen


def _get_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("Spotify-Gold-Layer")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", "2g")
        .getOrCreate()
    )


def _write(df: DataFrame, name: str):
    path = str(GOLD_PATH / name)
    df.write.mode("overwrite").parquet(path)
    print(f"    ✓  {name}")


# ── G01 Tiempo total por año ───────────────────────────────────────────────────
def g01_tiempo_total_por_año(fact: DataFrame) -> DataFrame:
    df = (
        fact.groupBy("año")
            .agg(
                F.sum("ms_played").alias("ms_total"),
                F.count("*").alias("reproducciones"),
            )
            .withColumn("horas_total", F.round(F.col("ms_total") / 3_600_000, 2))
            .orderBy("año")
    )
    _write(df, "G01_tiempo_total_por_año")
    return df


# ── G02 Distribución por tipo de arte ─────────────────────────────────────────
def g02_distribucion_tipo_arte(fact: DataFrame) -> DataFrame:
    total = fact.count()
    df = (
        fact.groupBy("tipo_arte")
            .agg(
                F.count("*").alias("reproducciones"),
                F.sum("ms_played").alias("ms_total"),
            )
            .withColumn("pct_reproducciones",
                        F.round(F.col("reproducciones") / total * 100, 2))
            .withColumn("horas_total",
                        F.round(F.col("ms_total") / 3_600_000, 2))
            .orderBy(F.desc("reproducciones"))
    )
    _write(df, "G02_distribucion_tipo_arte")
    return df


# ── G03 Tasa de salto ─────────────────────────────────────────────────────────
def g03_tasa_salto(fact: DataFrame) -> DataFrame:
    musica = fact.filter(F.col("tipo_arte") == "musica")
    total_m = musica.count()

    # overall
    skip_df = (
        musica.agg(
            F.sum(F.col("skipped").cast(LongType())).alias("saltadas"),
            F.count("*").alias("total"),
        )
        .withColumn("tasa_salto_pct", F.round(F.col("saltadas") / F.col("total") * 100, 2))
    )

    # by artist
    by_artist = (
        musica.groupBy("master_metadata_album_artist_name")
              .agg(
                  F.sum(F.col("skipped").cast(LongType())).alias("saltadas"),
                  F.count("*").alias("total"),
              )
              .withColumn("tasa_salto_pct",
                          F.round(F.col("saltadas") / F.col("total") * 100, 2))
              .filter(F.col("total") >= 5)
              .orderBy(F.desc("tasa_salto_pct"))
    )

    _write(skip_df,   "G03_tasa_salto_global")
    _write(by_artist, "G03_tasa_salto_por_artista")
    return by_artist


# ── G04 Canciones más escuchadas completas ────────────────────────────────────
def g04_canciones_completas_top(fact: DataFrame) -> DataFrame:
    df = (
        fact.filter(
            (F.col("tipo_arte") == "musica") &
            (F.col("ms_played") >= COMPLETE_LISTEN_MS) &
            (F.col("skipped") == False)
        )
        .groupBy(
            "master_metadata_track_name",
            "master_metadata_album_artist_name",
            "master_metadata_album_album_name",
        )
        .agg(
            F.count("*").alias("escuchas_completas"),
            F.sum("ms_played").alias("ms_total"),
        )
        .withColumn("minutos_total", F.round(F.col("ms_total") / 60_000, 1))
        .orderBy(F.desc("escuchas_completas"))
        .limit(50)
    )
    _write(df, "G04_canciones_completas_top50")
    return df


# ── G05 Actividad por hora ────────────────────────────────────────────────────
def g05_actividad_por_hora(fact: DataFrame) -> DataFrame:
    df = (
        fact.groupBy("hora")
            .agg(
                F.count("*").alias("reproducciones"),
                F.sum("ms_played").alias("ms_total"),
            )
            .withColumn("horas_escuchadas", F.round(F.col("ms_total") / 3_600_000, 2))
            .orderBy("hora")
    )
    _write(df, "G05_actividad_por_hora")
    return df


# ── G06 Actividad por mes ─────────────────────────────────────────────────────
def g06_actividad_por_mes(fact: DataFrame) -> DataFrame:
    df = (
        fact.groupBy("año", "mes")
            .agg(
                F.count("*").alias("reproducciones"),
                F.sum("ms_played").alias("ms_total"),
            )
            .withColumn("horas_escuchadas", F.round(F.col("ms_total") / 3_600_000, 2))
            .orderBy("año", "mes")
    )
    _write(df, "G06_actividad_por_mes")
    return df


# ── G07 Actividad por día de la semana ────────────────────────────────────────
def g07_actividad_dia_semana(fact: DataFrame) -> DataFrame:
    # Spark dayofweek: 1=Sun … 7=Sat
    nombre_dia = F.create_map(
        F.lit(1), F.lit("Domingo"),
        F.lit(2), F.lit("Lunes"),
        F.lit(3), F.lit("Martes"),
        F.lit(4), F.lit("Miércoles"),
        F.lit(5), F.lit("Jueves"),
        F.lit(6), F.lit("Viernes"),
        F.lit(7), F.lit("Sábado"),
    )
    df = (
        fact.groupBy("dia_semana")
            .agg(
                F.count("*").alias("reproducciones"),
                F.sum("ms_played").alias("ms_total"),
            )
            .withColumn("dia_nombre", nombre_dia[F.col("dia_semana")])
            .withColumn("horas_escuchadas", F.round(F.col("ms_total") / 3_600_000, 2))
            .orderBy("dia_semana")
    )
    _write(df, "G07_actividad_dia_semana")
    return df


# ── G08 Artistas top ──────────────────────────────────────────────────────────
def g08_artistas_top(fact: DataFrame) -> DataFrame:
    df = (
        fact.filter(F.col("tipo_arte") == "musica")
            .groupBy("master_metadata_album_artist_name")
            .agg(
                F.count("*").alias("reproducciones"),
                F.sum(
                    (F.col("ms_played") >= COMPLETE_LISTEN_MS).cast(LongType())
                ).alias("escuchas_completas"),
                F.sum("ms_played").alias("ms_total"),
            )
            .withColumn("horas_total", F.round(F.col("ms_total") / 3_600_000, 2))
            .orderBy(F.desc("reproducciones"))
            .limit(30)
    )
    _write(df, "G08_artistas_top30")
    return df


# ── G09 Sesiones de escucha ───────────────────────────────────────────────────
# A session ends when there is a gap > 30 min between consecutive plays.
def g09_sesiones(fact: DataFrame) -> DataFrame:
    GAP_MS = 30 * 60 * 1000   # 30 min in ms

    w = Window.orderBy("ts")
    df = (
        fact.select("id", "ts", "ms_played", "tipo_arte")
            .withColumn("ts_epoch",
                        F.unix_timestamp("ts", "yyyy-MM-dd'T'HH:mm:ss'Z'") * 1000)
            .withColumn("prev_end",
                        F.lag(F.col("ts_epoch") + F.col("ms_played")).over(w))
            .withColumn("gap_ms",
                        F.col("ts_epoch") - F.col("prev_end"))
            .withColumn("new_session",
                        (F.col("gap_ms").isNull() | (F.col("gap_ms") > GAP_MS))
                        .cast(LongType()))
            .withColumn("session_id", F.sum("new_session").over(w))
    )

    sesiones = (
        df.groupBy("session_id")
          .agg(
              F.count("*").alias("tracks_en_sesion"),
              F.sum("ms_played").alias("duracion_ms"),
          )
          .withColumn("duracion_min", F.round(F.col("duracion_ms") / 60_000, 1))
          .orderBy(F.desc("duracion_ms"))
    )

    stats = sesiones.agg(
        F.count("*").alias("total_sesiones"),
        F.avg("duracion_min").alias("duracion_media_min"),
        F.avg("tracks_en_sesion").alias("tracks_media"),
        F.max("duracion_min").alias("sesion_mas_larga_min"),
    )

    _write(sesiones, "G09_sesiones_detalle")
    _write(stats,    "G09_sesiones_estadisticas")
    return stats


# ── G10 Plan mensual vs anual ─────────────────────────────────────────────────
PLAN_MENSUAL_MXN  = 99.0
PLAN_ANUAL_MXN    = 990.0

def g10_plan_recomendacion(fact: DataFrame) -> DataFrame:
    ms_por_mes = (
        fact.groupBy("año", "mes")
            .agg(F.sum("ms_played").alias("ms_total"))
            .withColumn("horas", F.round(F.col("ms_total") / 3_600_000, 2))
    )
    stats = ms_por_mes.agg(
        F.avg("horas").alias("horas_promedio_mes"),
        F.count("*").alias("meses_activos"),
    )
    row = stats.first()
    horas_prom = round(row["horas_promedio_mes"] or 0, 2)
    meses_activos = row["meses_activos"] or 0

    costo_mensual_año  = PLAN_MENSUAL_MXN * 12
    ahorro             = round(costo_mensual_año - PLAN_ANUAL_MXN, 2)
    recomendacion      = "anual" if meses_activos >= 10 else "mensual"

    result = fact.sparkSession.createDataFrame([{
        "horas_promedio_mes":   horas_prom,
        "meses_activos":        meses_activos,
        "costo_mensual_mxn":    PLAN_MENSUAL_MXN,
        "costo_anual_mxn":      PLAN_ANUAL_MXN,
        "costo_mensual_x12":    costo_mensual_año,
        "ahorro_anual_mxn":     ahorro,
        "recomendacion_plan":   recomendacion,
    }])
    _write(result, "G10_plan_recomendacion")
    return result


# ── G11 Top tracks por país ───────────────────────────────────────────────────
def g11_top_por_pais(fact: DataFrame) -> DataFrame:
    w = Window.partitionBy("conn_country").orderBy(F.desc("reproducciones"))
    df = (
        fact.filter(F.col("tipo_arte") == "musica")
            .groupBy(
                "conn_country", "nombre_pais",
                "master_metadata_track_name",
                "master_metadata_album_artist_name",
            )
            .agg(F.count("*").alias("reproducciones"))
            .withColumn("rank", F.rank().over(w))
            .filter(F.col("rank") <= 10)
            .orderBy("conn_country", "rank")
    )
    _write(df, "G11_top_tracks_por_pais")
    return df


# ── G12 Actividad por franja horaria ─────────────────────────────────────────
def g12_franja_horaria(fact: DataFrame) -> DataFrame:
    franja = (
        F.when((F.col("hora") >= 0)  & (F.col("hora") < 6),  "Madrugada (0-5h)")
         .when((F.col("hora") >= 6)  & (F.col("hora") < 12), "Mañana (6-11h)")
         .when((F.col("hora") >= 12) & (F.col("hora") < 18), "Tarde (12-17h)")
         .otherwise("Noche (18-23h)")
    )
    df = (
        fact.withColumn("franja", franja)
            .groupBy("franja", "tipo_arte")
            .agg(
                F.count("*").alias("reproducciones"),
                F.sum("ms_played").alias("ms_total"),
            )
            .withColumn("horas_escuchadas", F.round(F.col("ms_total") / 3_600_000, 2))
            .orderBy("franja", "tipo_arte")
    )
    _write(df, "G12_franja_horaria")
    return df


# ── G13 Promedio de sesiones ──────────────────────────────────────────────────
def g13_promedio_sesiones(fact: DataFrame) -> DataFrame:
    by_day = (
        fact.groupBy("año", "mes", "dia")
            .agg(F.count("*").alias("reproducciones"))
    )
    stats = by_day.agg(
        F.avg("reproducciones").alias("avg_reproducciones_dia"),
        F.sum("reproducciones").alias("total_reproducciones"),
        F.count("*").alias("dias_activos"),
    )
    _write(stats, "G13_promedio_sesiones")
    return stats


# ── G14 Podcasts top ──────────────────────────────────────────────────────────
def g14_podcasts_top(fact: DataFrame) -> DataFrame:
    df = (
        fact.filter(F.col("tipo_arte") == "podcast")
            .groupBy("episode_show_name")
            .agg(
                F.count("*").alias("episodios_escuchados"),
                F.sum("ms_played").alias("ms_total"),
            )
            .withColumn("horas_total", F.round(F.col("ms_total") / 3_600_000, 2))
            .orderBy(F.desc("ms_total"))
            .limit(20)
    )
    _write(df, "G14_podcasts_top20")
    return df


# ── G15 Audiolibros top ───────────────────────────────────────────────────────
def g15_audiolibros_top(fact: DataFrame) -> DataFrame:
    df = (
        fact.filter(F.col("tipo_arte") == "audiolibro")
            .groupBy("audiobook_title")
            .agg(
                F.count("*").alias("sesiones"),
                F.sum("ms_played").alias("ms_total"),
            )
            .withColumn("horas_total", F.round(F.col("ms_total") / 3_600_000, 2))
            .orderBy(F.desc("ms_total"))
            .limit(10)
    )
    _write(df, "G15_audiolibros_top10")
    return df


# ── Main ───────────────────────────────────────────────────────────────────────

def aggregate() -> dict:
    spark = _get_spark()
    spark.sparkContext.setLogLevel("WARN")

    GOLD_PATH.mkdir(parents=True, exist_ok=True)

    print(f"\n{'─'*60}")
    print("  GOLD – Analytical aggregations")
    print(f"{'─'*60}\n")

    # Load Silver fact table
    fact = spark.read.parquet(str(SILVER_PATH / "fact_streaming"))

    # Enrich with nombre_pais if not present
    if "nombre_pais" not in fact.columns:
        pais = spark.read.parquet(str(SILVER_PATH / "dim_pais"))
        fact = fact.join(pais.select("id_location", "nombre_pais"),
                         fact["id"] == pais["id_location"], "left")

    fact.cache()
    total = fact.count()
    print(f"  Fact records available: {total:,}\n  Computing insights:")

    g01_tiempo_total_por_año(fact)
    g02_distribucion_tipo_arte(fact)
    g03_tasa_salto(fact)
    g04_canciones_completas_top(fact)
    g05_actividad_por_hora(fact)
    g06_actividad_por_mes(fact)
    g07_actividad_dia_semana(fact)
    g08_artistas_top(fact)
    g09_sesiones(fact)
    g10_plan_recomendacion(fact)
    g11_top_por_pais(fact)
    g12_franja_horaria(fact)
    g13_promedio_sesiones(fact)
    g14_podcasts_top(fact)
    g15_audiolibros_top(fact)

    meta = {
        "layer":          "gold",
        "bucket_path":    "bucket/reproduccion/gold",
        "total_records":  total,
        "aggregated_at":  datetime.now(timezone.utc).isoformat(),
        "insights": [
            "G01_tiempo_total_por_año",
            "G02_distribucion_tipo_arte",
            "G03_tasa_salto_global",
            "G03_tasa_salto_por_artista",
            "G04_canciones_completas_top50",
            "G05_actividad_por_hora",
            "G06_actividad_por_mes",
            "G07_actividad_dia_semana",
            "G08_artistas_top30",
            "G09_sesiones_detalle",
            "G09_sesiones_estadisticas",
            "G10_plan_recomendacion",
            "G11_top_tracks_por_pais",
            "G12_franja_horaria",
            "G13_promedio_sesiones",
            "G14_podcasts_top20",
            "G15_audiolibros_top10",
        ],
    }
    (GOLD_PATH / "_meta").mkdir(exist_ok=True)
    with open(GOLD_PATH / "_meta" / "gold_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n  Gold path : {GOLD_PATH}")
    print(f"{'─'*60}\n")

    spark.stop()
    return meta


if __name__ == "__main__":
    aggregate()
