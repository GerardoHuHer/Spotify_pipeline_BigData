"""
SILVER LAYER  –  PySpark transformations
─────────────────────────────────────────────────────────────────────────────
Reads all raw JSON files from the bronze bucket, applies every transformation
described in the analysis plan, and writes normalised Parquet partitions to:
    bucket/reproduccion/silver/

Transformations applied
  1. Deduplication
  2. Text normalisation (strip non-UTF-8, remove emojis – except URIs)
  3. Timestamp split  →  año / mes / día / hora
  4. arte dimension   →  keeps only non-null title fields + tipo_arte derivation
  5. pais dimension   →  country code + human-readable name
  6. usuario          →  ip_addr + platform
  7. reproduccion     →  ms_played, reason_end, reason_start, skipped
  8. claves           →  all URI fields (null-filtered)
─────────────────────────────────────────────────────────────────────────────
"""

import re
import unicodedata
from typing import Optional
from pathlib import Path
from datetime import datetime, timezone

# ── PySpark imports ────────────────────────────────────────────────────────────
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField,
    StringType, LongType, BooleanType, IntegerType,
)

# ── Path config ────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent
BRONZE_PATH = BASE_DIR / "bucket" / "reproduccion" / "bronze"
SILVER_PATH = BASE_DIR / "bucket" / "reproduccion" / "silver"

# ── Country code → name dictionary ────────────────────────────────────────────
COUNTRY_MAP: dict[str, str] = {
    "MX": "México",
    "US": "Estados Unidos",
    "ES": "España",
    "CO": "Colombia",
    "AR": "Argentina",
    "BR": "Brasil",
    "CL": "Chile",
    "PE": "Perú",
    "VE": "Venezuela",
    "EC": "Ecuador",
    "GT": "Guatemala",
    "CU": "Cuba",
    "BO": "Bolivia",
    "DO": "República Dominicana",
    "HN": "Honduras",
    "PY": "Paraguay",
    "SV": "El Salvador",
    "NI": "Nicaragua",
    "CR": "Costa Rica",
    "PA": "Panamá",
    "UY": "Uruguay",
    "DE": "Alemania",
    "FR": "Francia",
    "GB": "Reino Unido",
    "IT": "Italia",
    "JP": "Japón",
    "KR": "Corea del Sur",
    "CA": "Canadá",
    "AU": "Australia",
}

# ── Spark UDF: normalise text (strip emoji / non-UTF-8) ───────────────────────
# Note: use @F.udf with explicit returnType to avoid Python 3.12 type-hint
# inference warnings from PySpark's UDF introspection.

@F.udf(returnType=StringType())
def normalise_udf(text):
    """Remove emoji and characters outside the Basic Multilingual Plane."""
    if text is None:
        return None
    cleaned = "".join(
        ch for ch in text
        if unicodedata.category(ch) not in ("So", "Cs")
        and ord(ch) < 0x10000
    )
    return cleaned.strip() or None


# ── Schema for raw records ─────────────────────────────────────────────────────
RAW_SCHEMA = StructType([
    StructField("ts",                                   StringType(),  True),
    StructField("platform",                             StringType(),  True),
    StructField("ms_played",                            LongType(),    True),
    StructField("conn_country",                         StringType(),  True),
    StructField("ip_addr",                              StringType(),  True),
    StructField("master_metadata_track_name",           StringType(),  True),
    StructField("master_metadata_album_artist_name",    StringType(),  True),
    StructField("master_metadata_album_album_name",     StringType(),  True),
    StructField("spotify_track_uri",                    StringType(),  True),
    StructField("episode_name",                         StringType(),  True),
    StructField("episode_show_name",                    StringType(),  True),
    StructField("spotify_episode_uri",                  StringType(),  True),
    StructField("audiobook_title",                      StringType(),  True),
    StructField("audiobook_uri",                        StringType(),  True),
    StructField("audiobook_chapter_uri",                StringType(),  True),
    StructField("audiobook_chapter_title",              StringType(),  True),
    StructField("reason_start",                         StringType(),  True),
    StructField("reason_end",                           StringType(),  True),
    StructField("shuffle",                              BooleanType(), True),
    StructField("skipped",                              BooleanType(), True),
    StructField("offline",                              BooleanType(), True),
    StructField("offline_timestamp",                    StringType(),  True),
    StructField("incognito_mode",                       BooleanType(), True),
])


# ── Build Spark session ────────────────────────────────────────────────────────

def _get_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("Spotify-Silver-Layer")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.legacy.json.allowBackslashEscapingAnyCharacter", "true")
        .getOrCreate()
    )


# ── Transform steps ────────────────────────────────────────────────────────────

def step_1_dedup(df: DataFrame) -> DataFrame:
    """
    Drop duplicate rows using a set of explicit columns as the natural key.

    WHY NOT concat_ws:
      Spark's concat_ws SKIPS null values silently:
        concat_ws("|", "ts", null, null) -> "ts"   (not "ts|null|null")
      So building a single string key with concat_ws collapses ALL rows that
      share a timestamp into one record when content fields are null.

    CORRECT APPROACH — dropDuplicates with explicit column list:
      Spark compares NULLs as equal in dropDuplicates, so two rows are
      considered duplicates only if EVERY listed column matches, including
      nulls. This is exactly the deduplication semantics we want:
        - Same ts + ms_played + same URIs (or both null) = duplicate
        - Different ts or different ms or different URI       = distinct

    Key columns chosen:
      ts                    – exact playback moment
      ms_played             – duration distinguishes partial vs full listen
      spotify_track_uri     – unique ID for tracks  (null for podcasts/books)
      spotify_episode_uri   – unique ID for episodes (null for music/books)
      audiobook_uri         – unique ID for audiobooks (null for music/pods)
      master_metadata_track_name  – fallback when URI missing
      episode_name                – fallback for podcasts without URI
    """
    KEY_COLS = [
        "ts",
        "ms_played",
        "spotify_track_uri",
        "spotify_episode_uri",
        "audiobook_uri",
        "master_metadata_track_name",
        "episode_name",
    ]
    before = df.count()
    df = df.dropDuplicates(KEY_COLS)
    after = df.count()
    print(f"    [1] Dedup (explicit cols):  {before:,} → {after:,}  (removed {before-after:,})")
    return df


def step_2_normalise_text(df: DataFrame) -> DataFrame:
    """Strip emoji / non-BMP chars from text fields (leave URIs untouched)."""
    text_cols = [
        "platform",
        "master_metadata_track_name",
        "master_metadata_album_artist_name",
        "master_metadata_album_album_name",
        "episode_name",
        "episode_show_name",
        "audiobook_title",
        "audiobook_chapter_title",
    ]
    for col in text_cols:
        df = df.withColumn(col, normalise_udf(F.col(col)))
    print(f"    [2] Text normalisation applied to {len(text_cols)} columns")
    return df


def step_3_split_timestamp(df: DataFrame) -> DataFrame:
    """Parse ts → año, mes, día, hora integer columns."""
    df = (
        df.withColumn("ts_parsed", F.to_timestamp("ts", "yyyy-MM-dd'T'HH:mm:ss'Z'"))
          .withColumn("año",  F.year("ts_parsed").cast(IntegerType()))
          .withColumn("mes",  F.month("ts_parsed").cast(IntegerType()))
          .withColumn("dia",  F.dayofmonth("ts_parsed").cast(IntegerType()))
          .withColumn("hora", F.hour("ts_parsed").cast(IntegerType()))
          .withColumn("dia_semana", F.dayofweek("ts_parsed").cast(IntegerType()))
          .drop("ts_parsed")
    )
    print("    [3] Timestamp split into año / mes / día / hora / dia_semana")
    return df


def step_4_arte_tipo(df: DataFrame) -> DataFrame:
    """
    Derive tipo_arte: 'musica' | 'podcast' | 'audiolibro'
    based on which URI / title fields are non-null.
    """
    tipo = (
        F.when(F.col("spotify_track_uri").isNotNull(), "musica")
         .when(F.col("spotify_episode_uri").isNotNull(), "podcast")
         .when(F.col("audiobook_uri").isNotNull(), "audiolibro")
         .otherwise("desconocido")
    )
    df = df.withColumn("tipo_arte", tipo)
    print("    [4] tipo_arte derived")
    return df


def step_5_pais(df: DataFrame) -> DataFrame:
    """Map country code → human-readable name."""
    mapping_expr = F.create_map(
        *[item for pair in
          [(F.lit(k), F.lit(v)) for k, v in COUNTRY_MAP.items()]
          for item in pair]
    )
    df = df.withColumn(
        "nombre_pais",
        F.coalesce(mapping_expr[F.col("conn_country")], F.lit("Desconocido"))
    )
    print("    [5] nombre_pais added")
    return df


def step_6_add_ids(df: DataFrame) -> DataFrame:
    """Add surrogate keys for each dimension."""
    df = df.withColumn("id", F.monotonically_increasing_id())
    print("    [6] Surrogate key 'id' added")
    return df


# ── Dimension extraction (for Gold convenience) ────────────────────────────────

def extract_dim_tiempo(df: DataFrame) -> DataFrame:
    return (
        df.select("id", "año", "mes", "dia", "hora", "dia_semana")
          .dropDuplicates(["año", "mes", "dia", "hora"])
          .withColumnRenamed("id", "id_tiempo")
    )


def extract_dim_arte(df: DataFrame) -> DataFrame:
    cols = [
        "master_metadata_track_name",
        "master_metadata_album_artist_name",
        "master_metadata_album_album_name",
        "episode_name",
        "episode_show_name",
        "audiobook_title",
        "audiobook_chapter_title",
        "tipo_arte",
    ]
    return (
        df.select("id", *cols)
          .withColumnRenamed("id", "id_arte")
    )


def extract_dim_pais(df: DataFrame) -> DataFrame:
    return (
        df.select("id", "conn_country", "nombre_pais")
          .withColumnRenamed("id", "id_location")
    )


def extract_dim_usuario(df: DataFrame) -> DataFrame:
    return (
        df.select("id", "ip_addr", "platform")
          .withColumnRenamed("id", "id_user")
    )


def extract_dim_reproduccion(df: DataFrame) -> DataFrame:
    return (
        df.select("id", "ms_played", "reason_end", "reason_start", "skipped",
                  "shuffle", "offline", "incognito_mode")
          .withColumnRenamed("id", "id_reproduccion")
    )


def extract_dim_claves(df: DataFrame) -> DataFrame:
    uri_cols = [
        "audiobook_chapter_uri",
        "audiobook_uri",
        "spotify_episode_uri",
        "spotify_track_uri",
    ]
    return (
        df.select("id", *uri_cols)
          .withColumnRenamed("id", "id_clave")
    )


# ── Write helpers ──────────────────────────────────────────────────────────────

def _write_parquet(df: DataFrame, name: str, partition_by: list[str] | None = None):
    path = str(SILVER_PATH / name)
    writer = df.write.mode("overwrite")
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.parquet(path)
    print(f"    ✓  Wrote {name}")


# ── Main ───────────────────────────────────────────────────────────────────────

def transform() -> dict:
    spark = _get_spark()
    spark.sparkContext.setLogLevel("WARN")

    SILVER_PATH.mkdir(parents=True, exist_ok=True)

    print(f"\n{'─'*60}")
    print("  SILVER – PySpark transformations")
    print(f"{'─'*60}")

    # ── 1. Load all bronze JSON files ──────────────────────────────────────
    bronze_files = list(BRONZE_PATH.glob("Streaming_History_Audio_*.json"))
    if not bronze_files:
        raise FileNotFoundError("No bronze files found – run bronze layer first.")

    df = (
        spark.read
             .schema(RAW_SCHEMA)
             .option("multiLine", "true")   # each JSON record spans multiple lines
             .option("mode", "PERMISSIVE")  # skip malformed records gracefully
             .json([str(p) for p in bronze_files])
    )
    print(f"\n  Raw records loaded: {df.count():,}")

    # ── 2. Apply transformation steps ─────────────────────────────────────
    print("\n  Applying transformations:")
    df = step_1_dedup(df)
    df = step_2_normalise_text(df)
    df = step_3_split_timestamp(df)
    df = step_4_arte_tipo(df)
    df = step_5_pais(df)
    df = step_6_add_ids(df)

    # Cache the cleaned fact table for dimension extraction
    df.cache()
    total = df.count()

    # ── 3. Write fact table ────────────────────────────────────────────────
    print("\n  Writing Parquet datasets:")
    _write_parquet(df, "fact_streaming", partition_by=["año", "tipo_arte"])

    # ── 4. Write dimension tables ──────────────────────────────────────────
    _write_parquet(extract_dim_tiempo(df),       "dim_tiempo")
    _write_parquet(extract_dim_arte(df),         "dim_arte")
    _write_parquet(extract_dim_pais(df),         "dim_pais")
    _write_parquet(extract_dim_usuario(df),      "dim_usuario")
    _write_parquet(extract_dim_reproduccion(df), "dim_reproduccion")
    _write_parquet(extract_dim_claves(df),       "dim_claves")

    # ── 5. Write metadata ──────────────────────────────────────────────────
    meta = {
        "layer":          "silver",
        "bucket_path":    "bucket/reproduccion/silver",
        "total_records":  total,
        "transformed_at": datetime.now(timezone.utc).isoformat(),
        "tables": [
            "fact_streaming",
            "dim_tiempo", "dim_arte", "dim_pais",
            "dim_usuario", "dim_reproduccion", "dim_claves",
        ],
    }
    (SILVER_PATH / "_meta").mkdir(exist_ok=True)
    import json
    with open(SILVER_PATH / "_meta" / "silver_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n  Total clean records: {total:,}")
    print(f"  Silver path        : {SILVER_PATH}")
    print(f"{'─'*60}\n")

    spark.stop()
    return meta


if __name__ == "__main__":
    transform()
