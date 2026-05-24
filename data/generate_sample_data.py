"""
Generate realistic sample Spotify streaming data for testing the pipeline.
Creates JSON files mimicking Spotify's export format.
"""

import json
import random
from datetime import datetime, timedelta
import os

# ─── Sample data pools ────────────────────────────────────────────────────────

TRACKS = [
    ("Blinding Lights", "The Weeknd", "After Hours"),
    ("Shape of You", "Ed Sheeran", "÷ (Divide)"),
    ("Bohemian Rhapsody", "Queen", "A Night at the Opera"),
    ("Levitating", "Dua Lipa", "Future Nostalgia"),
    ("drivers license", "Olivia Rodrigo", "SOUR"),
    ("Stay", "The Kid LAROI", "F*CK LOVE 3"),
    ("Bad Guy", "Billie Eilish", "WHEN WE ALL FALL ASLEEP"),
    ("Watermelon Sugar", "Harry Styles", "Fine Line"),
    ("Dynamite", "BTS", "BE"),
    ("Peaches", "Justin Bieber", "Justice"),
    ("Montero", "Lil Nas X", "MONTERO"),
    ("Good 4 U", "Olivia Rodrigo", "SOUR"),
    ("Leave The Door Open", "Bruno Mars", "An Evening with Silk Sonic"),
    ("Butter", "BTS", "Butter"),
    ("Kiss Me More", "Doja Cat", "Planet Her"),
    ("Save Your Tears", "The Weeknd", "After Hours"),
    ("Positions", "Ariana Grande", "Positions"),
    ("Therefore I Am", "Billie Eilish", "Therefore I Am"),
    ("34+35", "Ariana Grande", "Positions"),
    ("Heat Waves", "Glass Animals", "Dreamland"),
    ("Industry Baby", "Lil Nas X", "MONTERO"),
    ("Happier Than Ever", "Billie Eilish", "Happier Than Ever"),
    ("Traitor", "Olivia Rodrigo", "SOUR"),
    ("Shivers", "Ed Sheeran", "="),
    ("Easy On Me", "Adele", "30"),
    ("Count on Me", "Bruno Mars", "Doo-Wops & Hooligans"),
    ("Just the Way You Are", "Bruno Mars", "Doo-Wops & Hooligans"),
    ("Thunder", "Imagine Dragons", "Evolve"),
    ("Believer", "Imagine Dragons", "Evolve"),
    ("Natural", "Imagine Dragons", "Origins"),
    ("Demons", "Imagine Dragons", "Night Visions"),
    ("Radioactive", "Imagine Dragons", "Night Visions"),
    ("Shallow", "Lady Gaga", "A Star Is Born"),
    ("Bad Romance", "Lady Gaga", "The Fame Monster"),
    ("Poker Face", "Lady Gaga", "The Fame"),
]

PODCASTS = [
    ("How I Built This", "How I Built This with Guy Raz"),
    ("The Daily", "The New York Times"),
    ("Serial", "Serial Productions"),
    ("Stuff You Should Know", "iHeartPodcasts"),
    ("Crime Junkie", "audiochuck"),
    ("Hidden Brain", "NPR"),
    ("Freakonomics Radio", "Freakonomics Radio + Stitcher"),
    ("Conan O'Brien Needs a Friend", "Team Coco"),
]

AUDIOBOOKS = [
    ("Atomic Habits", "James Clear", "Chapter 1: The Surprising Power of Atomic Habits"),
    ("The Psychology of Money", "Morgan Housel", "Chapter 3: Never Enough"),
    ("Sapiens", "Yuval Noah Harari", "Chapter 5: History's Biggest Fraud"),
    ("Deep Work", "Cal Newport", "Chapter 2: The Deep Work Hypothesis"),
]

PLATFORMS = [
    "Android OS 9 API 28 (HUAWEI, MRD-LX3)",
    "iOS 15.4 (iPhone 13, iPhone)",
    "Windows 10 (10.0.19041)",
    "macOS Monterey (12.3)",
    "Cast to device",
    "Android OS 12 API 31 (Samsung, SM-G998B)",
]

COUNTRIES = ["MX", "MX", "MX", "MX", "US", "ES", "CO", "AR"]

REASON_START = ["trackdone", "fwdbtn", "backbtn", "clickrow", "playbtn", "remote", "autoplay"]
REASON_END   = ["trackdone", "fwdbtn", "backbtn", "endplay", "logout", "remote"]


def random_ts(start: datetime, end: datetime) -> str:
    delta = end - start
    rand_seconds = random.randint(0, int(delta.total_seconds()))
    dt = start + timedelta(seconds=rand_seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_music_record(ts: str) -> dict:
    track, artist, album = random.choice(TRACKS)
    ms = random.choice([
        random.randint(100, 5000),          # skip
        random.randint(150000, 300000),     # full listen
        random.randint(30000, 150000),      # partial
    ])
    skipped = ms < 30000
    return {
        "ts": ts,
        "platform": random.choice(PLATFORMS),
        "ms_played": ms,
        "conn_country": random.choice(COUNTRIES),
        "ip_addr": f"189.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "master_metadata_track_name": track,
        "master_metadata_album_artist_name": artist,
        "master_metadata_album_album_name": album,
        "spotify_track_uri": f"spotify:track:{random.randint(100000,999999)}",
        "episode_name": None,
        "episode_show_name": None,
        "spotify_episode_uri": None,
        "audiobook_title": None,
        "audiobook_uri": None,
        "audiobook_chapter_uri": None,
        "audiobook_chapter_title": None,
        "reason_start": random.choice(REASON_START),
        "reason_end": random.choice(REASON_END),
        "shuffle": random.choice([True, False]),
        "skipped": skipped,
        "offline": random.choice([False, False, False, True]),
        "offline_timestamp": None,
        "incognito_mode": random.choice([False, False, False, True]),
    }


def make_podcast_record(ts: str) -> dict:
    ep_name, show = random.choice(PODCASTS)
    return {
        "ts": ts,
        "platform": random.choice(PLATFORMS),
        "ms_played": random.randint(600000, 3600000),
        "conn_country": random.choice(COUNTRIES),
        "ip_addr": f"189.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "master_metadata_track_name": None,
        "master_metadata_album_artist_name": None,
        "master_metadata_album_album_name": None,
        "spotify_track_uri": None,
        "episode_name": f"{ep_name} - Episode {random.randint(1,200)}",
        "episode_show_name": show,
        "spotify_episode_uri": f"spotify:episode:{random.randint(100000,999999)}",
        "audiobook_title": None,
        "audiobook_uri": None,
        "audiobook_chapter_uri": None,
        "audiobook_chapter_title": None,
        "reason_start": random.choice(REASON_START),
        "reason_end": random.choice(REASON_END),
        "shuffle": False,
        "skipped": False,
        "offline": False,
        "offline_timestamp": None,
        "incognito_mode": False,
    }


def make_audiobook_record(ts: str) -> dict:
    title, _, chapter = random.choice(AUDIOBOOKS)
    ab_title = title
    _, _, ch_title = random.choice(AUDIOBOOKS)
    return {
        "ts": ts,
        "platform": random.choice(PLATFORMS),
        "ms_played": random.randint(1200000, 5400000),
        "conn_country": random.choice(COUNTRIES),
        "ip_addr": f"189.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "master_metadata_track_name": None,
        "master_metadata_album_artist_name": None,
        "master_metadata_album_album_name": None,
        "spotify_track_uri": None,
        "episode_name": None,
        "episode_show_name": None,
        "spotify_episode_uri": None,
        "audiobook_title": ab_title,
        "audiobook_uri": f"spotify:audiobook:{random.randint(100000,999999)}",
        "audiobook_chapter_uri": f"spotify:audiobook_chapter:{random.randint(100000,999999)}",
        "audiobook_chapter_title": chapter,
        "reason_start": random.choice(REASON_START),
        "reason_end": random.choice(REASON_END),
        "shuffle": False,
        "skipped": False,
        "offline": False,
        "offline_timestamp": None,
        "incognito_mode": False,
    }


def generate_year_data(start: datetime, end: datetime, n: int) -> list:
    records = []
    for _ in range(n):
        ts = random_ts(start, end)
        r = random.random()
        if r < 0.80:
            records.append(make_music_record(ts))
        elif r < 0.95:
            records.append(make_podcast_record(ts))
        else:
            records.append(make_audiobook_record(ts))
    # inject a few duplicates
    dupes = random.sample(records, min(5, len(records)))
    records.extend(dupes)
    return records


def main():
    out_dir = os.path.dirname(__file__)
    random.seed(42)

    ranges = [
        ("2020-2021", datetime(2020, 6, 1), datetime(2021, 5, 31), 800),
        ("2021-2023", datetime(2021, 6, 1), datetime(2023, 5, 31), 1500),
        ("2023-2024", datetime(2023, 6, 1), datetime(2024, 5, 31), 1200),
        ("2024-2026", datetime(2024, 6, 1), datetime(2026, 3, 1),  900),
    ]

    for label, start, end, n in ranges:
        records = generate_year_data(start, end, n)
        fname = os.path.join(out_dir, f"Streaming_History_Audio_{label}.json")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"  ✓  {fname}  ({len(records)} records)")


if __name__ == "__main__":
    main()
