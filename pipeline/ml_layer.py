"""
ML LAYER  –  Modelos orientados a decisiones del Analista de Datos
─────────────────────────────────────────────────────────────────────────────
Tres preguntas de negocio → tres modelos accionables:

  ML1 – ¿El algoritmo de Spotify te sirve o te atrapa?
        Clasifica cada reproducción como DESCUBRIMIENTO (tú elegiste)
        vs ALGORITMO (Spotify decidió). Luego mide si lo que el algoritmo
        te pone lo escuchas igual de bien que lo que tú eliges.
        → Decisión: ¿vale la pena pagar Premium solo por el algoritmo?

  ML2 – ¿Cuál es tu perfil de oyente y cómo cambia en el tiempo?
        K-Means sobre vectores semanales: detecta semanas de exploración,
        semanas de repetición, semanas de poco uso, etc.
        → Decisión: ¿estás diversificando o en loop? ¿cuándo eres más activo?

  ML3 – Modelo de fatiga y contexto de skip
        Gradient Boosting que predice skip con features de CONTEXTO:
        posición en la sesión, racha de skips previos, tiempo acumulado,
        hora, día. Revela cuándo y por qué "abandonas" la escucha.
        → Decisión: ¿tus playlists/sesiones son demasiado largas?
                    ¿el shuffle te sirve?

Salidas: bucket/reproduccion/ml/
─────────────────────────────────────────────────────────────────────────────
"""

import json
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

warnings.filterwarnings("ignore")

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.cluster import KMeans
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, f1_score, roc_auc_score, silhouette_score,
)

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent
SILVER_PATH = BASE_DIR / "bucket" / "reproduccion" / "silver"
ML_PATH     = BASE_DIR / "bucket" / "reproduccion" / "ml"

COMPLETE_MS  = 30_000
RANDOM_STATE = 42

# Razones que indican ELECCIÓN ACTIVA del usuario
ACTIVE_CHOICE = {"clickrow", "playbtn", "remote", "backbtn"}
# Razones que indican que el ALGORITMO puso la canción
ALGORITHM     = {"trackdone", "autoplay", "fwdbtn"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_fact() -> pd.DataFrame:
    path = SILVER_PATH / "fact_streaming"
    if not path.exists():
        raise FileNotFoundError("Silver no encontrado. Ejecuta el pipeline primero.")
    df = pd.read_parquet(path)
    for col in ["hora", "dia_semana", "mes", "año", "ms_played"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["shuffle", "skipped", "offline"]:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
    print(f"  Registros cargados: {len(df):,}")
    return df


def _save(obj, name: str):
    ML_PATH.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, pd.DataFrame):
        obj.to_parquet(ML_PATH / f"{name}.parquet", index=False)
    elif isinstance(obj, dict):
        with open(ML_PATH / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
    print(f"    ✓  {name}")


# ══════════════════════════════════════════════════════════════════════════════
# ML1 – Algoritmo vs Elección Activa
# ══════════════════════════════════════════════════════════════════════════════

def ml1_algoritmo_vs_eleccion(df: pd.DataFrame) -> dict:
    """
    PREGUNTA: ¿El algoritmo de Spotify te sirve o te atrapa?

    Clasifica cada reproducción como:
      1 = ACTIVA   (tú elegiste: clickrow, playbtn, backbtn, remote)
      0 = ALGORITMO (Spotify decidió: trackdone, autoplay, fwdbtn)

    Luego compara: ¿escuchas mejor (más completo, menos skip) lo que
    elegiste tú vs lo que el algoritmo te puso?

    Modelo: Random Forest — predice si una escucha fue activa o algorítmica
    basándose en el comportamiento de escucha resultante. Si el modelo no
    puede distinguirlas, significa que te comportas igual con ambas
    (el algoritmo funciona). Si las distingue bien, hay una diferencia real.
    """
    print("\n  ── ML1: Algoritmo vs Elección Activa ──")

    music = df[df["tipo_arte"] == "musica"].copy()
    music = music.dropna(subset=["reason_start", "ms_played"])

    # ── Clasificar origen ─────────────────────────────────────────────────
    music["origen"] = music["reason_start"].apply(
        lambda r: 1 if r in ACTIVE_CHOICE else (0 if r in ALGORITHM else np.nan)
    )
    music = music.dropna(subset=["origen"])
    music["origen"] = music["origen"].astype(int)

    # ── Métricas comparativas (la decisión real del analista) ─────────────
    music["escucha_completa"] = (music["ms_played"] >= COMPLETE_MS).astype(int)
    music["skip_int"]         = music["skipped"].astype(int)

    comparativa = (
        music.groupby("origen")
        .agg(
            total              = ("ms_played", "count"),
            tasa_completa      = ("escucha_completa", "mean"),
            tasa_skip          = ("skip_int", "mean"),
            ms_promedio        = ("ms_played", "mean"),
            horas_totales      = ("ms_played", "sum"),
        )
        .reset_index()
    )
    comparativa["origen_nombre"] = comparativa["origen"].map(
        {0: "Algoritmo (Spotify)", 1: "Elección Activa (Tú)"}
    )
    comparativa["horas_totales"]  = (comparativa["horas_totales"] / 3_600_000).round(2)
    comparativa["ms_promedio"]    = comparativa["ms_promedio"].round(0)
    comparativa["tasa_completa"]  = comparativa["tasa_completa"].round(3)
    comparativa["tasa_skip"]      = comparativa["tasa_skip"].round(3)

    print(f"    Reproducciones activas  : {int(music['origen'].sum()):,}")
    print(f"    Reproducciones algoritmo: {int((music['origen']==0).sum()):,}")

    # ── Repetitividad por origen ───────────────────────────────────────────
    rep_activa = music[music["origen"]==1]["spotify_track_uri"].nunique()
    rep_total_activa = int((music["origen"]==1).sum())
    rep_algo   = music[music["origen"]==0]["spotify_track_uri"].nunique()
    rep_total_algo   = int((music["origen"]==0).sum())

    diversidad = pd.DataFrame([
        {"origen": "Elección Activa",      "canciones_unicas": rep_activa,
         "total_repros": rep_total_activa,
         "ratio_repeticion": round(rep_total_activa / max(rep_activa,1), 2)},
        {"origen": "Algoritmo (Spotify)",  "canciones_unicas": rep_algo,
         "total_repros": rep_total_algo,
         "ratio_repeticion": round(rep_total_algo / max(rep_algo,1), 2)},
    ])

    # ── Modelo RF: ¿el comportamiento posterior diferencia el origen? ──────
    FEATURES = [
        "ms_played", "escucha_completa", "skip_int",
        "hora", "dia_semana", "shuffle",
    ]
    music["shuffle_enc"] = music["shuffle"].astype(int)
    FEATURES_ENC = ["ms_played","escucha_completa","skip_int",
                    "hora","dia_semana","shuffle_enc"]

    X = music[FEATURES_ENC].fillna(0)
    y = music["origen"]

    results = {"modelo": "Random Forest — Algoritmo vs Elección Activa"}

    if len(X) >= 200 and y.nunique() == 2:
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
        )
        model = RandomForestClassifier(
            n_estimators=200, max_depth=6,
            class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1
        )
        model.fit(X_tr, y_tr)
        y_pred = model.predict(X_te)
        acc = accuracy_score(y_te, y_pred)
        f1  = f1_score(y_te, y_pred, average="weighted")
        cv  = cross_val_score(model, X, y, cv=5, scoring="f1_weighted", n_jobs=-1)

        fi = pd.DataFrame({
            "feature": FEATURES_ENC,
            "importance": model.feature_importances_
        }).sort_values("importance", ascending=False)

        print(f"    Accuracy RF : {acc:.3f}")
        print(f"    F1 weighted : {f1:.3f}")
        print(f"    CV F1       : {cv.mean():.3f} ± {cv.std():.3f}")

        # Interpretación clave para el analista
        diferencia_tasa = abs(
            float(comparativa[comparativa["origen"]==1]["tasa_completa"].values[0]) -
            float(comparativa[comparativa["origen"]==0]["tasa_completa"].values[0])
        )
        if acc < 0.58:
            interpretacion = (
                "El modelo no puede distinguir bien entre lo que elegiste tú "
                "y lo que puso el algoritmo → escuchas ambos de forma similar. "
                "El algoritmo te conoce bien."
            )
        elif diferencia_tasa > 0.05:
            interpretacion = (
                "Escuchas más completo lo que elegiste tú. "
                "El algoritmo te pone canciones que no terminás. "
                "Considera usar más playlists propias y menos radio."
            )
        else:
            interpretacion = (
                "El algoritmo acierta en términos de completitud, "
                "pero hay diferencias en el contexto de skip. "
                "Revisá los patrones por hora."
            )

        results.update({
            "accuracy": round(float(acc), 4),
            "f1_weighted": round(float(f1), 4),
            "cv_f1_mean": round(float(cv.mean()), 4),
            "cv_f1_std": round(float(cv.std()), 4),
            "confusion_matrix": confusion_matrix(y_te, y_pred).tolist(),
            "interpretacion_analista": interpretacion,
            "feature_names": FEATURES_ENC,
        })
        _save(fi, "ML1_feature_importance")
    else:
        print("    ⚠  Datos insuficientes para RF, solo análisis comparativo")

    # ── Tendencia temporal: ¿cada vez más algoritmo o más activo? ─────────
    tendencia = (
        music.groupby(["año","mes"])
        .agg(
            pct_activa = ("origen","mean"),
            total      = ("origen","count"),
        )
        .reset_index()
    )
    tendencia["pct_activa"] = tendencia["pct_activa"].round(3)

    # ── Artistas: ¿a quiénes escuchas solo cuando el algoritmo los pone? ──
    art_origen = (
        music.groupby(["master_metadata_album_artist_name","origen"])
        .size().reset_index(name="count")
        .pivot(index="master_metadata_album_artist_name", columns="origen", values="count")
        .fillna(0)
    )
    art_origen.columns = ["via_algoritmo","via_activa"]
    art_origen["total"] = art_origen["via_algoritmo"] + art_origen["via_activa"]
    art_origen["pct_algoritmo"] = (art_origen["via_algoritmo"] / art_origen["total"]).round(3)
    art_origen = (
        art_origen[art_origen["total"] >= 5]
        .sort_values("pct_algoritmo", ascending=False)
        .reset_index()
    )

    results.update({
        "pct_global_activa":   round(float(music["origen"].mean()), 4),
        "pct_global_algoritmo": round(float(1 - music["origen"].mean()), 4),
        "total_reproducciones": int(len(music)),
    })

    _save(comparativa,   "ML1_comparativa_origen")
    _save(diversidad,    "ML1_diversidad_por_origen")
    _save(tendencia,     "ML1_tendencia_temporal")
    _save(art_origen.head(30), "ML1_artistas_por_origen")
    _save(results,       "ML1_resultados")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# ML2 – Perfil de Oyente Semanal (K-Means)
# ══════════════════════════════════════════════════════════════════════════════

def ml2_perfil_oyente_semanal(df: pd.DataFrame) -> dict:
    """
    PREGUNTA: ¿Cuál es tu perfil de oyente y cómo cambia en el tiempo?

    Agrupa semanas (año-semana ISO) en perfiles:
      - Semana exploratoria: muchos artistas únicos, tasa skip alta
      - Semana de loop: pocos artistas, alta repetición
      - Semana intensa: muchas horas
      - Semana pasiva: pocas horas, mucho algoritmo
      - Semana de podcasts: predomina contenido no musical

    Insight accionable: ¿en qué épocas del año sos más exploratorio?
    ¿Hay correlación con días de la semana o meses?
    """
    print("\n  ── ML2: Perfil de Oyente Semanal (K-Means) ──")

    d = df.copy()
    d["semana_iso"] = pd.to_datetime(
        d["año"].astype(str) + "-" + d["mes"].astype(str).str.zfill(2) +
        "-" + d["dia"].astype(str).str.zfill(2),
        errors="coerce"
    ).dt.isocalendar().week.astype(int)
    d["año_semana"] = (
        d["año"].astype(str) + "-W" + d["semana_iso"].astype(str).str.zfill(2)
    )
    d["es_activa"]    = d["reason_start"].apply(lambda r: 1 if r in ACTIVE_CHOICE else 0)
    d["es_skip"]      = d["skipped"].astype(int)
    d["es_completa"]  = (d["ms_played"] >= COMPLETE_MS).astype(int)
    d["es_musica"]    = (d["tipo_arte"] == "musica").astype(int)
    d["es_podcast"]   = (d["tipo_arte"] == "podcast").astype(int)

    semanas = (
        d.groupby(["año","año_semana"])
        .agg(
            horas_semana       = ("ms_played",            lambda x: x.sum()/3_600_000),
            repros_semana      = ("ms_played",             "count"),
            artistas_unicos    = ("master_metadata_album_artist_name", "nunique"),
            canciones_unicas   = ("spotify_track_uri",     "nunique"),
            tasa_skip          = ("es_skip",               "mean"),
            tasa_completa      = ("es_completa",           "mean"),
            pct_activa         = ("es_activa",             "mean"),
            pct_musica         = ("es_musica",             "mean"),
            pct_podcast        = ("es_podcast",            "mean"),
            hora_media         = ("hora",                  "mean"),
        )
        .reset_index()
    )
    semanas = semanas[semanas["repros_semana"] >= 5].copy()

    # Diversidad = canciones únicas / total reproducciones
    semanas["diversidad"] = (
        semanas["canciones_unicas"] / semanas["repros_semana"].clip(lower=1)
    ).round(3)

    FEAT = [
        "horas_semana", "artistas_unicos", "diversidad",
        "tasa_skip", "tasa_completa", "pct_activa",
        "pct_musica", "pct_podcast", "hora_media",
    ]
    X = semanas[FEAT].fillna(0)

    if len(X) < 10:
        print("    ⚠  Semanas insuficientes")
        return {}

    scaler  = StandardScaler()
    X_sc    = scaler.fit_transform(X)

    # Silhouette para elegir K
    k_range = range(2, min(7, len(X)//3))
    sils    = []
    for k in k_range:
        lbl = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=15).fit_predict(X_sc)
        sils.append(silhouette_score(X_sc, lbl))

    best_k = list(k_range)[int(np.argmax(sils))]
    print(f"    K óptimo: {best_k}  (silhouette={max(sils):.3f})")

    km = KMeans(n_clusters=best_k, random_state=RANDOM_STATE, n_init=20)
    semanas["cluster"] = km.fit_predict(X_sc)

    # ── Nombrar clusters automáticamente ─────────────────────────────────
    centros = pd.DataFrame(
        scaler.inverse_transform(km.cluster_centers_), columns=FEAT
    )

    def _nombre(row):
        if row["pct_podcast"] > 0.3:
            return "🎙️ Semana de Podcasts"
        if row["horas_semana"] > centros["horas_semana"].quantile(0.75):
            if row["diversidad"] > centros["diversidad"].median():
                return "🔭 Maratón Exploratorio"
            return "🔁 Maratón en Loop"
        if row["diversidad"] > centros["diversidad"].quantile(0.75):
            return "🆕 Exploración Musical"
        if row["tasa_skip"] > centros["tasa_skip"].quantile(0.75):
            return "⏭️ Modo Shuffle Activo"
        if row["horas_semana"] < centros["horas_semana"].quantile(0.25):
            return "🔇 Semana de Poco Uso"
        if row["pct_activa"] < centros["pct_activa"].median():
            return "🤖 Semana Pasiva (Algoritmo)"
        return "🎧 Escucha Regular"

    centros["cluster"]  = range(best_k)
    centros["nombre"]   = centros.apply(_nombre, axis=1)
    semanas = semanas.merge(centros[["cluster","nombre"]], on="cluster", how="left")

    # ── Distribución por año ───────────────────────────────────────────────
    dist_año = (
        semanas.groupby(["año","cluster","nombre"])
        .size().reset_index(name="semanas_count")
    )

    # ── Distribución por mes ───────────────────────────────────────────────
    semanas_mes = semanas.merge(
        d[["año","año_semana","mes"]].drop_duplicates(), on=["año","año_semana"], how="left"
    )
    dist_mes = (
        semanas_mes.groupby(["mes","cluster","nombre"])
        .size().reset_index(name="semanas_count")
    )

    sil_df = pd.DataFrame({"k": list(k_range), "silhouette": sils})

    results = {
        "modelo":           "K-Means — Perfil de Oyente Semanal",
        "k_optimo":         int(best_k),
        "silhouette_score": round(float(max(sils)), 4),
        "semanas_analizadas": int(len(semanas)),
        "perfiles": centros[["cluster","nombre"] + FEAT].round(3).to_dict(orient="records"),
        "interpretacion_analista": (
            f"Se identificaron {best_k} perfiles de semana de escucha. "
            "Revisá en qué épocas del año dominan los perfiles exploratorios "
            "vs los de loop para entender tus ciclos de descubrimiento musical."
        ),
    }

    _save(semanas[["año","año_semana","cluster","nombre"] + FEAT], "ML2_semanas_con_cluster")
    _save(centros[["cluster","nombre"] + FEAT].round(3),           "ML2_perfil_clusters")
    _save(sil_df,                                                   "ML2_silhouette_scores")
    _save(dist_año,                                                 "ML2_distribucion_por_año")
    _save(dist_mes,                                                 "ML2_distribucion_por_mes")
    _save(results,                                                  "ML2_resultados")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# ML3 – Modelo de Fatiga y Contexto de Skip
# ══════════════════════════════════════════════════════════════════════════════

def ml3_fatiga_y_skip(df: pd.DataFrame) -> dict:
    """
    PREGUNTA: ¿Cuándo y por qué abandonás la escucha?

    Gradient Boosting que predice skip usando features de CONTEXTO DE SESIÓN:
      - posición en la sesión (canción #N de la sesión)
      - racha de skips consecutivos anteriores
      - minutos acumulados en la sesión
      - hora del día, día de la semana
      - shuffle activo
      - si la canción llegó por algoritmo o por elección

    Insight: si "posicion_en_sesion" es el feature más importante,
    tus sesiones son demasiado largas. Si es "shuffle", el modo aleatorio
    te genera más rechazo. Si es "hora", hay franjas en que no querés escuchar.
    """
    print("\n  ── ML3: Fatiga y Contexto de Skip (Gradient Boosting) ──")

    music = df[df["tipo_arte"] == "musica"].copy()
    music = music.dropna(subset=["ms_played","skipped","hora","dia_semana"])
    music["skip_int"]     = music["skipped"].astype(int)
    music["shuffle_enc"]  = music["shuffle"].astype(int)
    music["es_activa"]    = music["reason_start"].apply(
        lambda r: 1 if r in ACTIVE_CHOICE else 0
    )

    # ── Construir features de sesión (gap > 30 min = nueva sesión) ────────
    GAP_MIN = 30
    music = music.sort_values("ts").reset_index(drop=True) if "ts" in music.columns else music.reset_index(drop=True)

    if "ts" in music.columns:
        music["ts_dt"]         = pd.to_datetime(music["ts"], errors="coerce")
        music["ts_prev"]       = music["ts_dt"].shift(1)
        music["gap_min"]       = (music["ts_dt"] - music["ts_prev"]).dt.total_seconds() / 60
        music["nueva_sesion"]  = (music["gap_min"].isna() | (music["gap_min"] > GAP_MIN)).astype(int)
        music["sesion_id"]     = music["nueva_sesion"].cumsum()

        sesion_agg = (
            music.groupby("sesion_id")
            .apply(lambda g: g.assign(
                posicion_en_sesion   = range(len(g)),
                ms_acumulado_sesion  = g["ms_played"].cumsum().shift(1).fillna(0),
                skips_previos        = g["skip_int"].shift(1).fillna(0).cumsum(),
            ))
            .reset_index(drop=True)
        )
        music = sesion_agg
    else:
        music["posicion_en_sesion"]  = 0
        music["ms_acumulado_sesion"] = 0
        music["skips_previos"]       = 0

    music["min_acumulado_sesion"] = music["ms_acumulado_sesion"] / 60_000

    FEATURES = [
        "posicion_en_sesion",
        "min_acumulado_sesion",
        "skips_previos",
        "hora",
        "dia_semana",
        "shuffle_enc",
        "es_activa",
        "mes",
    ]
    TARGET = "skip_int"

    X = music[FEATURES].fillna(0)
    y = music[TARGET]

    if len(X) < 200:
        print("    ⚠  Datos insuficientes")
        return {}

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    model = GradientBoostingClassifier(
        n_estimators=300, max_depth=4,
        learning_rate=0.05, subsample=0.8,
        random_state=RANDOM_STATE,
    )
    model.fit(X_tr, y_tr)

    y_pred = model.predict(X_te)
    acc    = accuracy_score(y_te, y_pred)
    f1     = f1_score(y_te, y_pred, average="weighted")
    cv     = cross_val_score(model, X, y, cv=5, scoring="f1_weighted", n_jobs=-1)

    print(f"    Accuracy  : {acc:.3f}")
    print(f"    F1 weighted: {f1:.3f}")
    print(f"    CV F1     : {cv.mean():.3f} ± {cv.std():.3f}")

    fi = pd.DataFrame({
        "feature":    FEATURES,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False).reset_index(drop=True)

    top_feature = fi.iloc[0]["feature"]

    interpretaciones = {
        "posicion_en_sesion":  "Tus sesiones son demasiado largas — el skip aumenta a medida que avanza la sesión. Considerá playlists más cortas.",
        "min_acumulado_sesion":"La fatiga temporal es el principal driver del skip — definí un tiempo máximo de escucha continua.",
        "skips_previos":       "El skip en cadena es tu patrón dominante — cuando empezás a saltear, no parás. El problema suele ser la playlist entera, no una canción.",
        "hora":                "La hora del día determina más que nada si vas a saltear. Hay franjas en que la escucha no conecta contigo.",
        "shuffle_enc":         "El modo shuffle es el principal predictor de skip — las canciones aleatorias no se adaptan a tu estado de ánimo actual.",
        "es_activa":           "Saltás más lo que el algoritmo pone vs lo que vos elegís — considerá usar más playlists propias.",
        "dia_semana":          "El día de la semana domina el skip — hay días en que simplemente no querés escuchar.",
        "mes":                 "La época del año afecta tu tolerancia — hay meses con mayor rechazo musical.",
    }
    interpretacion = interpretaciones.get(
        top_feature,
        f"El factor más influyente es '{top_feature}'."
    )

    # ── Skip rate por posición en sesión ──────────────────────────────────
    skip_posicion = (
        music.groupby("posicion_en_sesion")["skip_int"]
        .agg(["mean","count"])
        .reset_index()
        .rename(columns={"mean":"tasa_skip","count":"total"})
        .query("total >= 10")
        .head(30)
    )

    # ── Skip rate por minutos acumulados (buckets de 10 min) ──────────────
    music["bucket_min"] = (music["min_acumulado_sesion"] // 10 * 10).astype(int)
    skip_min = (
        music.groupby("bucket_min")["skip_int"]
        .agg(["mean","count"])
        .reset_index()
        .rename(columns={"mean":"tasa_skip","count":"total"})
        .query("total >= 10")
    )

    # ── Skip rate por hora ────────────────────────────────────────────────
    skip_hora = (
        music.groupby("hora")["skip_int"]
        .agg(["mean","count"])
        .reset_index()
        .rename(columns={"mean":"tasa_skip","count":"total"})
    )

    # ── Skip: shuffle vs no shuffle ───────────────────────────────────────
    skip_shuffle = (
        music.groupby("shuffle_enc")["skip_int"]
        .agg(["mean","count"])
        .reset_index()
        .rename(columns={"mean":"tasa_skip","count":"total"})
    )
    skip_shuffle["modo"] = skip_shuffle["shuffle_enc"].map({0:"Orden fijo",1:"Shuffle"})

    # ── Skip: activa vs algoritmo ─────────────────────────────────────────
    skip_origen = (
        music.groupby("es_activa")["skip_int"]
        .agg(["mean","count"])
        .reset_index()
        .rename(columns={"mean":"tasa_skip","count":"total"})
    )
    skip_origen["origen"] = skip_origen["es_activa"].map(
        {0:"Algoritmo (Spotify)",1:"Elección Activa (Tú)"}
    )

    results = {
        "modelo":                  "Gradient Boosting — Fatiga y Contexto de Skip",
        "objetivo":                "Predecir skip usando contexto de sesión",
        "accuracy":                round(float(acc), 4),
        "f1_weighted":             round(float(f1), 4),
        "cv_f1_mean":              round(float(cv.mean()), 4),
        "cv_f1_std":               round(float(cv.std()), 4),
        "confusion_matrix":        confusion_matrix(y_te, y_pred).tolist(),
        "feature_names":           FEATURES,
        "top_feature":             top_feature,
        "interpretacion_analista": interpretacion,
        "tasa_skip_global":        round(float(y.mean()), 4),
        "tasa_skip_shuffle_on":    round(float(music[music["shuffle_enc"]==1]["skip_int"].mean()), 4),
        "tasa_skip_shuffle_off":   round(float(music[music["shuffle_enc"]==0]["skip_int"].mean()), 4),
        "tasa_skip_activa":        round(float(music[music["es_activa"]==1]["skip_int"].mean()), 4),
        "tasa_skip_algoritmo":     round(float(music[music["es_activa"]==0]["skip_int"].mean()), 4),
    }

    _save(fi,             "ML3_feature_importance")
    _save(skip_posicion,  "ML3_skip_por_posicion")
    _save(skip_min,       "ML3_skip_por_minutos")
    _save(skip_hora,      "ML3_skip_por_hora")
    _save(skip_shuffle,   "ML3_skip_shuffle_vs_orden")
    _save(skip_origen,    "ML3_skip_activa_vs_algoritmo")
    _save(results,        "ML3_resultados")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# Orquestador
# ══════════════════════════════════════════════════════════════════════════════

def run_ml() -> dict:
    ML_PATH.mkdir(parents=True, exist_ok=True)
    print(f"\n{'─'*60}")
    print("  ML LAYER – Machine Learning para Analista de Datos")
    print(f"{'─'*60}")

    df = _load_fact()

    r1 = ml1_algoritmo_vs_eleccion(df)
    r2 = ml2_perfil_oyente_semanal(df)
    r3 = ml3_fatiga_y_skip(df)

    summary = {
        "ml_layer_run_at": datetime.now(timezone.utc).isoformat(),
        "models": {"ML1": r1, "ML2": r2, "ML3": r3},
    }
    _save(summary, "ML_summary")

    print(f"\n  ML path : {ML_PATH}")
    print(f"{'─'*60}\n")
    return summary


if __name__ == "__main__":
    run_ml()