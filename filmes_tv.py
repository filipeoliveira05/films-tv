#!/usr/bin/env python3
"""
Filmes na TV ordenados por rating IMDb.

Fluxo:
  1. tudonumclick.com -> grelha de cada canal, para cada dia disponível -> SQLite
  2. Filtra programas longos (>= MIN_MINUTES), provavelmente filmes
  3. TMDB (pesquisa em pt-PT + validação pela duração) -> imdb_id
  4. Dataset oficial title.ratings do IMDb -> rating
  5. Gera filmes.html ordenado por rating

Uso:
  pip install requests beautifulsoup4
  export TMDB_API_KEY=...        # chave v3, gratuita em themoviedb.org
  python filmes_tv.py

Correr todos os dias acumula histórico na base de dados (dias passados).
"""
import gzip
import html
import os
import re
import sqlite3
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta
from datetime import time as dtime
from difflib import SequenceMatcher
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://tudonumclick.com"
DB_PATH = "filmes.db"
OUT_PATH = "filmes.html"
RATINGS_GZ = Path("title.ratings.tsv.gz")
RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
MIN_MINUTES = 75          # abaixo disto não é tratado como filme
REQUEST_DELAY = 1.0       # segundos entre pedidos ao site


def load_dotenv(path=".env"):
    """Lê KEY=valor de um .env local, sem sobrepor variáveis já definidas."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


load_dotenv()
TMDB_KEY = os.environ.get("TMDB_API_KEY")

CHANNELS = [
    "Hollywood", "AXN", "AXN Movies", "AXN White", "STAR Channel", "STAR Life",
    "STAR Movies", "STAR Crime", "STAR Comedy", "SyFy", "AMC", "NOS Studios",
    "TVCine Top", "TVCine Edition", "TVCine Emotion", "TVCine Action",
]
# Slugs já conhecidos; os restantes são descobertos na página "mais canais".
KNOWN_SLUGS = {
    "Hollywood": "hollywood",
    "AXN": "axn",
    "AXN Movies": "axn-black",
    "AXN White": "axn-white",
    "STAR Channel": "fox",
    "STAR Life": "fox-life",
    "STAR Movies": "fox-movies",
    "STAR Crime": "fox-crime",
    "STAR Comedy": "fox-comedy",
    "SyFy": "syfy",
    "AMC": "amc",
    "NOS Studios": "nos-studios",
    "TVCine Top": "tvc1",
    "TVCine Edition": "tvc2",
    "TVCine Emotion": "tvc3",
    "TVCine Action": "tvc4",
}

session = requests.Session()
session.headers["User-Agent"] = "filmes-tv-pessoal/0.1"


def get(url):
    time.sleep(REQUEST_DELAY)
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ---------------------------------------------------------------- scraping
def discover_slugs():
    soup = BeautifulSoup(get(f"{BASE}/programacao-tv/mais-canais/"), "html.parser")
    found = {}
    for a in soup.find_all("a", href=True):
        m = re.fullmatch(rf"(?:{re.escape(BASE)})?/programacao-tv/([a-z0-9-]+)/", a["href"])
        if not m:
            continue
        for label in (a.get_text(" ", strip=True), a.get("title", "")):
            if label:
                found.setdefault(norm(label), m.group(1))
    slugs = {}
    for name in CHANNELS:
        slug = KNOWN_SLUGS.get(name) or found.get(norm(name))
        if slug:
            slugs[name] = slug
        else:
            print(f"! sem slug para '{name}' (acrescenta a KNOWN_SLUGS)", file=sys.stderr)
    return slugs


TIME_RE = re.compile(r"(\d{2}):(\d{2})\s*às\s*(\d{2}):(\d{2})")


def parse_programs(page_html, day):
    """Lê o texto da página: linha 'HH:MM às HH:MM' seguida do título."""
    text = BeautifulSoup(page_html, "html.parser").get_text("\n")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = []
    for i, line in enumerate(lines[:-1]):
        m = TIME_RE.fullmatch(line)
        if not m:
            continue
        h1, m1, h2, m2 = map(int, m.groups())
        start = datetime.combine(day, dtime(h1, m1))
        end = datetime.combine(day, dtime(h2, m2))
        if end <= start:
            end += timedelta(days=1)
        title = lines[i + 1]
        if title != "Resumo":
            out.append((start, end, title))
    # a página de um dia abre com o programa da noite anterior que atravessa a
    # meia-noite (ex.: "23:10 às 00:55"); esse pertence ao dia anterior
    if len(out) > 1 and out[0][1].date() > out[0][0].date() and out[1][0] < out[0][0]:
        one_day = timedelta(days=1)
        out[0] = (out[0][0] - one_day, out[0][1] - one_day, out[0][2])
    return out


def scrape_channel(db, channel, slug):
    today = date.today()
    first = get(f"{BASE}/programacao-tv/{slug}/")
    pages = [(0, first)]
    soup = BeautifulSoup(first, "html.parser")
    day_slugs = []
    for a in soup.find_all("a", href=True):
        m = re.fullmatch(
            rf"(?:{re.escape(BASE)})?/programacao-tv/{re.escape(slug)}/([a-z0-9-]+)/", a["href"]
        )
        if m and m.group(1) not in day_slugs:
            day_slugs.append(m.group(1))
    offset = 0
    for d in day_slugs:
        if d == "ontem":
            off = -1
        else:
            offset += 1
            off = offset
        pages.append((off, get(f"{BASE}/programacao-tv/{slug}/{d}/")))

    total = 0
    for off, page in pages:
        for start, end, title in parse_programs(page, today + timedelta(days=off)):
            db.execute(
                "INSERT OR IGNORE INTO airings VALUES (?,?,?,?)",
                (channel, start.isoformat(), end.isoformat(), title),
            )
            total += 1
    db.commit()
    if total == 0:
        print(f"! {channel}: 0 programas lidos (ajustar parse_programs?)", file=sys.stderr)
    else:
        print(f"{channel}: {total} programas em {len(pages)} dias")


# ---------------------------------------------------------------- ratings IMDb
def load_ratings(db):
    fresh = RATINGS_GZ.exists() and time.time() - RATINGS_GZ.stat().st_mtime < 7 * 86400
    has_rows = db.execute("SELECT COUNT(*) FROM ratings").fetchone()[0] > 0
    if fresh and has_rows:
        return
    print("A descarregar title.ratings do IMDb...")
    with session.get(RATINGS_URL, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(RATINGS_GZ, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    with gzip.open(RATINGS_GZ, "rt", encoding="utf-8") as f:
        next(f)
        rows = (l.rstrip("\n").split("\t") for l in f)
        db.executemany(
            "INSERT OR REPLACE INTO ratings VALUES (?,?,?)",
            ((r[0], float(r[1]), int(r[2])) for r in rows),
        )
    db.commit()


# ---------------------------------------------------------------- TMDB
def tmdb(path, **params):
    r = requests.get(
        f"https://api.themoviedb.org/3{path}",
        params={"api_key": TMDB_KEY, **params},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


SERIES_RE = re.compile(r"\bT\d+\s*-\s*Ep\.?\s*\d+", re.I)
YEAR_RE = re.compile(r"\s*\((\d{4})\)\s*$")


def is_series(title):
    """Episódios ('T12 - Ep. 3') não são filmes, mesmo que durem >= MIN_MINUTES."""
    return bool(SERIES_RE.search(title))


VP_RE = re.compile(r"\s*\(vp\)\s*$", re.I)   # versão portuguesa (dobragem)
MIN_SIM = 0.85            # semelhança mínima entre o título da TV e o do TMDB
MIN_VOTES = 1500          # recurso: 1.º resultado do TMDB só se for muito votado
PREFIX_PENALTY = 0.97     # casar só o prefixo ('Pretty Woman - ...') vale menos que o título inteiro


def clean_title(title):
    """Devolve (título para pesquisa, ano ou None): apóstrofos normalizados, '(VP)' e '(2019)' separados."""
    t = title.replace("´", "'").replace("`", "'")
    t = VP_RE.sub("", t)
    m = YEAR_RE.search(t)
    if m:
        t = t[: m.start()]
    return t.strip(), (m.group(1) if m else None)


def similarity(tv_title, cand_title):
    """0..1; ignora acentos/maiúsculas. O prefixo antes de ' - ' ou ': ' do título da TV vale um pouco menos."""
    full = SequenceMatcher(None, norm(tv_title), norm(cand_title)).ratio()
    head = re.split(r"\s+-\s+|:\s+", tv_title)[0]
    if head == tv_title:
        return full
    return max(full, PREFIX_PENALTY * SequenceMatcher(None, norm(head), norm(cand_title)).ratio())


def best_similarity(tv_title, c):
    return max(similarity(tv_title, c.get("title") or ""), similarity(tv_title, c.get("original_title") or ""))


def choose(tv_title, minutes, cands):
    """Escolhe entre candidatos TMDB (com runtime e imdb_id): título parecido, duração compatível.

    O slot costuma ser mais longo que o filme (publicidade), por isso a tolerância é assimétrica.
    Desempata pela semelhança do título e depois pela duração mais próxima.
    Recurso: os títulos pt-PT do TMDB variam ('Duna' vs 'Dune: Parte Um'); sem título parecido,
    aceita-se o 1.º resultado da pesquisa se for muito votado e a duração quase igual.
    """
    best, best_key, fallback = None, None, None
    for c in cands:
        runtime = c.get("runtime") or 0
        if not (c.get("imdb_id") and runtime):
            continue
        sim = best_similarity(tv_title, c)
        if sim < MIN_SIM:
            if c.get("rank") == 0 and (c.get("vote_count") or 0) >= MIN_VOTES and abs(minutes - runtime) <= 15:
                fallback = c
            continue
        if not -25 <= minutes - runtime <= 60:
            continue
        key = (round(sim, 2), -abs(minutes - runtime))
        if best_key is None or key > best_key:
            best, best_key = c, key
    return best or fallback


def match_title(title, minutes):
    """Devolve (imdb_id, título original, ano, duração) ou None."""
    query, year = clean_title(title)
    params = {"year": year} if year else {}
    results = tmdb("/search/movie", query=query, language="pt-PT", **params)["results"][:8]
    cands = []
    for rank, c in enumerate(results):
        if rank > 0 and best_similarity(query, c) < MIN_SIM:   # evita detalhes de filmes que não são este
            continue
        d = tmdb(f"/movie/{c['id']}", append_to_response="external_ids", language="pt-PT")
        cands.append({**d, "rank": rank, "imdb_id": (d.get("external_ids") or {}).get("imdb_id")})
    d = choose(query, minutes, cands)
    if not d:
        return None
    return d["imdb_id"], d.get("original_title"), (d.get("release_date") or "")[:4], d["runtime"]


def match_titles(db):
    rows = db.execute(
        """SELECT title, MAX((julianday(end) - julianday(start)) * 1440) AS mins
           FROM airings
           WHERE title NOT IN (SELECT title FROM matches)
             AND (julianday(end) - julianday(start)) * 1440 >= ?
           GROUP BY title""",
        (MIN_MINUTES,),
    ).fetchall()
    rows = [r for r in rows if not is_series(r[0])]
    for n, (title, mins) in enumerate(rows, 1):
        try:
            res = match_title(title, mins)
        except requests.RequestException as e:
            print(f"! TMDB falhou em '{title}': {e}", file=sys.stderr)
            continue
        # guarda também os falhanços (imdb_id NULL) para não repetir pedidos
        db.execute(
            "INSERT OR REPLACE INTO matches VALUES (?,?,?,?,?)",
            (title, *(res if res else (None, None, None, None))),
        )
        db.commit()
        print(f"[{n}/{len(rows)}] {title} -> {res[0] if res else 'sem correspondência'}")
        time.sleep(0.1)


# ---------------------------------------------------------------- relatório
def report(db):
    since = (datetime.now() - timedelta(days=7)).isoformat()
    now = datetime.now().isoformat()
    # um filme por imdb_id: junta a versão dobrada '(VP)' e variantes de maiúsculas do mesmo título
    rows = db.execute(
        """SELECT m.imdb_id, MIN(m.original), MIN(m.year), r.rating, r.votes, GROUP_CONCAT(m.title, char(31))
           FROM matches m LEFT JOIN ratings r ON r.tconst = m.imdb_id
           WHERE m.imdb_id IS NOT NULL
             AND EXISTS (SELECT 1 FROM airings a WHERE a.title = m.title AND a.start >= ?)
           GROUP BY m.imdb_id
           ORDER BY r.rating IS NULL, r.rating DESC""",
        (since,),
    ).fetchall()
    films = []
    for imdb, original, year, rating, votes, titles in rows:
        titles = titles.split("\x1f")
        # título a mostrar: o que não é versão dobrada
        title = sorted(titles, key=lambda t: (bool(VP_RE.search(t)), t))[0]
        films.append((title, titles, original, year, rating, votes, imdb))
    unmatched = db.execute(
        """SELECT DISTINCT a.title FROM airings a
           LEFT JOIN matches m ON m.title = a.title
           WHERE a.start >= ? AND m.imdb_id IS NULL
             AND (julianday(a.end) - julianday(a.start)) * 1440 >= ?
           ORDER BY a.title""",
        (since, MIN_MINUTES),
    ).fetchall()
    unmatched = [(t,) for (t,) in unmatched if not is_series(t)]

    parts = [
        "<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>Filmes na TV</title>",
        "<style>body{font-family:system-ui;max-width:760px;margin:1rem auto;padding:0 1rem}"
        "li{margin:.8rem 0}.r{font-weight:700}.y{color:#555}.past{color:#888}small{display:block}</style>",
        "<h1>Filmes na TV por rating IMDb</h1><ol>",
    ]
    for title, titles, original, year, rating, votes, imdb in films:
        airings = db.execute(
            f"SELECT channel, start, title FROM airings WHERE title IN ({','.join('?' * len(titles))}) "
            "AND start >= ? ORDER BY start",
            (*titles, since),
        ).fetchall()
        when = "; ".join(
            f"<span class='{'past' if s < now else ''}'>{html.escape(c)}{' (VP)' if VP_RE.search(t) else ''} "
            f"{datetime.fromisoformat(s):%a %d/%m %H:%M}</span>"
            for c, s, t in airings
        )
        year_txt = f" <span class='y'>({year})</span>" if year else ""
        rtxt = f"{rating:.1f} ({votes:,} votos)" if rating else "sem rating"
        parts.append(
            f"<li><span class='r'>{rtxt}</span> &middot; "
            f"<a href='https://www.imdb.com/title/{imdb}/'>{html.escape(title)}</a>{year_txt} "
            f"<small>{html.escape(original or '')}</small><small>{when}</small></li>"
        )
    parts.append("</ol>")
    if unmatched:
        parts.append("<h2>Sem correspondência</h2><ul>")
        parts += [f"<li>{html.escape(t)}</li>" for (t,) in unmatched]
        parts.append("</ul>")
    Path(OUT_PATH).write_text("\n".join(parts), encoding="utf-8")
    print(f"\n{len(films)} filmes, {len(unmatched)} sem correspondência -> {OUT_PATH}")
    for title, _, _, _, rating, _, _ in films[:10]:
        print(f"  {rating or '-':>4}  {title}")


def main():
    if not TMDB_KEY:
        sys.exit("Define a variável de ambiente TMDB_API_KEY.")
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS airings(
            channel TEXT, start TEXT, end TEXT, title TEXT, PRIMARY KEY(channel, start));
        CREATE TABLE IF NOT EXISTS matches(
            title TEXT PRIMARY KEY, imdb_id TEXT, original TEXT, year TEXT, runtime INT);
        CREATE TABLE IF NOT EXISTS ratings(
            tconst TEXT PRIMARY KEY, rating REAL, votes INT);
        """
    )
    for channel, slug in discover_slugs().items():
        try:
            scrape_channel(db, channel, slug)
        except requests.RequestException as e:
            print(f"! {channel}: {e}", file=sys.stderr)
    load_ratings(db)
    match_titles(db)
    report(db)


if __name__ == "__main__":
    main()
