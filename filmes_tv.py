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
import csv
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
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://tudonumclick.com"
DB_PATH = "filmes.db"
OUT_PATH = "filmes.html"
RATINGS_GZ = Path("title.ratings.tsv.gz")
RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
MIN_MINUTES = 75          # abaixo disto não é tratado como filme
REQUEST_DELAY = 1.0       # segundos entre pedidos ao site
STATE_DIR = Path("data")  # airings.csv e matches.csv: o que é guardado no repo entre execuções
KEEP_DAYS = 8             # emissões mais antigas já não estão no catch-up (7 dias) e são apagadas


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

def now_lisbon():
    """Agora em Lisboa, sem fuso: as horas dos programas são locais e o runner do Actions está em UTC."""
    return datetime.now(ZoneInfo("Europe/Lisbon")).replace(tzinfo=None)


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
    today = now_lisbon().date()
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
    return total


STATE_TABLES = {
    "airings": (["channel", "start", "end", "title"], "channel, start"),
    "matches": (["title", "imdb_id", "original", "year", "runtime", "checked"], "title"),
}


def export_state(db, directory=STATE_DIR):
    """Grava airings e matches em CSV ordenado (diffs pequenos). Os ratings do IMDb não se guardam."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for table, (cols, order) in STATE_TABLES.items():
        with open(directory / f"{table}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cols)
            w.writerows(db.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY {order}"))


def import_state(db, directory=STATE_DIR):
    """Carrega os CSV para a base de dados sem sobrepor o que já lá está."""
    for table, (cols, _) in STATE_TABLES.items():
        path = Path(directory) / f"{table}.csv"
        if not path.exists():
            continue
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                values = [row.get(c) or None for c in cols]   # '' -> NULL
                if table == "matches" and values[4] is not None:
                    values[4] = int(values[4])
                db.execute(
                    f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) VALUES ({','.join('?' * len(cols))})", values
                )
    db.commit()


def prune(db):
    """Apaga emissões com início há mais de KEEP_DAYS dias. Os matches ficam (são pequenos e reaproveitados)."""
    limit = (now_lisbon() - timedelta(days=KEEP_DAYS)).isoformat()
    n = db.execute("DELETE FROM airings WHERE start < ?", (limit,)).rowcount
    db.commit()
    if n:
        print(f"Podadas {n} emissões com mais de {KEEP_DAYS} dias")
    return n


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


RETRY_DAYS = 30           # os falhanços de matching são repetidos ao fim deste tempo


def migrate(db, now=None):
    """Bases de dados antigas: acrescenta matches.checked (falhanços antigos contam como verificados agora)."""
    cols = [r[1] for r in db.execute("PRAGMA table_info(matches)")]
    if "checked" not in cols:
        db.execute("ALTER TABLE matches ADD COLUMN checked TEXT")
    db.execute("UPDATE matches SET checked = ? WHERE checked IS NULL", ((now or now_lisbon()).isoformat(),))
    db.commit()


def titles_to_match(db, now=None):
    """Títulos ainda sem match, mais os falhanços verificados há mais de RETRY_DAYS dias."""
    limit = ((now or now_lisbon()) - timedelta(days=RETRY_DAYS)).isoformat()
    rows = db.execute(
        """SELECT title, MAX((julianday(end) - julianday(start)) * 1440) AS mins
           FROM airings
           WHERE title NOT IN (SELECT title FROM matches WHERE imdb_id IS NOT NULL OR checked >= ?)
             AND (julianday(end) - julianday(start)) * 1440 >= ?
           GROUP BY title""",
        (limit, MIN_MINUTES),
    ).fetchall()
    return [r for r in rows if not is_series(r[0])]


def match_titles(db):
    rows = titles_to_match(db)
    for n, (title, mins) in enumerate(rows, 1):
        try:
            res = match_title(title, mins)
        except requests.RequestException as e:
            print(f"! TMDB falhou em '{title}': {e}", file=sys.stderr)
            continue
        # guarda também os falhanços (imdb_id NULL) para não repetir pedidos até RETRY_DAYS
        db.execute(
            "INSERT OR REPLACE INTO matches (title, imdb_id, original, year, runtime, checked) VALUES (?,?,?,?,?,?)",
            (title, *(res if res else (None, None, None, None)), now_lisbon().isoformat()),
        )
        db.commit()
        print(f"[{n}/{len(rows)}] {title} -> {res[0] if res else 'sem correspondência'}")
        time.sleep(0.1)


# ---------------------------------------------------------------- relatório
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
CATCHUP_DAYS = 7          # a NOS TV deixa ver o que passou nos últimos 7 dias


def epoch(dt):
    """Instante absoluto (segundos UTC) de uma hora de Lisboa sem fuso, para o script da página."""
    return int(dt.replace(tzinfo=ZoneInfo("Europe/Lisbon")).timestamp())


def fmt_when(dt):
    return f"{DIAS[dt.weekday()]} {dt:%d/%m %H:%M}"


def fmt_remaining(delta):
    mins = int(delta.total_seconds() // 60)
    d, rest = divmod(mins, 1440)
    h, m = divmod(rest, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def history_notice(db, now):
    """Aviso se o histórico ainda não cobre os CATCHUP_DAYS dias de 'Para gravar'."""
    first = db.execute("SELECT MIN(start) FROM airings").fetchone()[0]
    if not first:
        return None
    first = datetime.fromisoformat(first)
    if first <= now - timedelta(days=CATCHUP_DAYS) + timedelta(hours=6):
        return None
    return (
        f"Histórico incompleto: só há dados desde {fmt_when(first)}, por isso &laquo;Para gravar&raquo; "
        f"ainda não cobre os {CATCHUP_DAYS} dias completos (fica completo a partir de "
        f"{fmt_when(first + timedelta(days=CATCHUP_DAYS))})."
    )


FOOTER = (
    "<footer><div class='wrap'><p>Horários: <a href='https://tudonumclick.com'>tudonumclick.com</a>. "
    "Ratings: dataset público do IMDb (uso pessoal e não comercial). "
    "Este produto usa a API do <a href='https://www.themoviedb.org'>TMDB</a>, mas não é endossado nem "
    "certificado pelo TMDB. Correspondências feitas automaticamente: podem existir erros.</p></div></footer>"
)


def collect_films(db, now):
    """Filmes (um por imdb_id, ordenados por rating) com as emissões desde há CATCHUP_DAYS dias."""
    since = (now - timedelta(days=CATCHUP_DAYS)).isoformat()
    # junta a versão dobrada '(VP)' e variantes de maiúsculas do mesmo título
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
        # título a mostrar: o que não é versão dobrada, sem o sufixo
        title = VP_RE.sub("", sorted(titles, key=lambda t: (bool(VP_RE.search(t)), t))[0])
        airings = [
            (c, datetime.fromisoformat(s), datetime.fromisoformat(e), bool(VP_RE.search(t)))
            for c, s, e, t in db.execute(
                f"SELECT channel, start, end, title FROM airings WHERE title IN ({','.join('?' * len(titles))}) "
                "AND start >= ? ORDER BY start",
                (*titles, since),
            )
        ]
        films.append(dict(title=title, original=original, year=year, rating=rating, votes=votes,
                          imdb=imdb, airings=airings, rank=len(films)))
    return films


def fmt_rating(r):
    return f"{r:.1f}".replace(".", ",")


def fmt_votes(v):
    if v >= 999_500:
        return f"{v / 1e6:.1f} M votos".replace(".", ",")
    if v >= 1000:
        return f"{round(v / 1000)} mil votos"
    return f"{v} votos"


def rating_tier(r):
    """'hi' (>= 8) fica a ouro, 'lo' (< 6) esbatido, 'none' sem rating."""
    if r is None:
        return "none"
    return "hi" if r >= 8.0 else "lo" if r < 6.0 else ""


def remaining_pct(left):
    """Fração da janela de CATCHUP_DAYS que ainda resta, em % (largura da 'fita')."""
    return round(max(0.0, min(1.0, left / timedelta(days=CATCHUP_DAYS))) * 100, 1)


ICONS = {
    "agora": "<svg viewBox='0 0 12 12' aria-hidden='true'><path d='M2 1l9 5-9 5z'/></svg>",
    "gravar": "<svg viewBox='0 0 12 12' aria-hidden='true'><circle cx='6' cy='6' r='5'/></svg>",
    "vir": "<svg viewBox='0 0 12 12' aria-hidden='true'><path d='M0 1l6 5-6 5zM6 1l6 5-6 5z'/></svg>",
}
HIDDEN = " hidden"
FONTS = "https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,100..900&display=swap"


def film_item(f, airings, kind, now):
    lines = []
    for channel, start, end, vp in airings:
        who = f"<b>{html.escape(channel)}{' (VP)' if vp else ''}</b> {fmt_when(start)}"
        urgent, bar = "", ""
        if kind == "gravar":
            expires = start + timedelta(days=CATCHUP_DAYS)
            left = expires - now
            if left < timedelta(days=1):
                urgent = " urgent"
            bar = (
                f"<span class='bar'><span class='track'><i style='width:{remaining_pct(left)}%'></i></span>"
                f"<span class='left'>faltam {fmt_remaining(left)}</span>"
                f"<span class='until'>até {fmt_when(expires)}</span></span>"
            )
        elif kind == "agora":
            bar = f"<span class='left'>termina às {end:%H:%M}</span>"
        else:
            bar = f"<span class='left'>em {fmt_remaining(start - now)}</span>"
        # data-*: o script da página recalcula secção, prazo e fita a partir destes instantes absolutos
        until = fmt_when(start + timedelta(days=CATCHUP_DAYS))
        lines.append(
            f"<li class='airing{urgent}' data-start='{epoch(start)}' data-end='{epoch(end)}' "
            f"data-until='até {until}' data-end-label='{end:%H:%M}'><span class='where'>{who}</span>{bar}</li>"
        )
    if f["rating"]:
        score = (
            f"<div class='score {rating_tier(f['rating'])}'><b>{fmt_rating(f['rating'])}</b>"
            f"<small>{fmt_votes(f['votes'])}</small></div>"
        ).replace("score '", "score'")
    else:
        score = "<div class='score none'><b>&ndash;</b><small>sem rating</small></div>"
    year = f" <span class='y'>({f['year']})</span>" if f["year"] else ""
    orig = f['original'] or ""
    orig_html = f"<p class='orig'>{html.escape(orig)}</p>" if orig and norm(orig) != norm(f["title"]) else ""
    return (
        f"<li class='film' data-film='{f['imdb']}' data-rank='{f['rank']}'>{score}<div class='info'>"
        f"<h3><a href='https://www.imdb.com/title/{f['imdb']}/'>{html.escape(f['title'])}</a>{year}</h3>"
        f"{orig_html}<ul class='airings'>{''.join(lines)}</ul></div></li>"
    )


def report(db, now=None):
    now = now or now_lisbon()
    since = (now - timedelta(days=CATCHUP_DAYS)).isoformat()
    films = collect_films(db, now)
    # cada filme entra em cada secção só com as emissões que lhe pertencem
    sections = [
        ("agora", "A dar agora", lambda s, e: s <= now < e, ""),
        ("gravar", "Para gravar", lambda s, e: e <= now,
         f"Passaram nos últimos {CATCHUP_DAYS} dias. O prazo conta {CATCHUP_DAYS} dias desde o início da emissão."),
        ("vir", "A vir", lambda s, e: s > now, "Ordenados por rating, não por data."),
    ]
    unmatched = db.execute(
        """SELECT DISTINCT a.title FROM airings a
           LEFT JOIN matches m ON m.title = a.title
           WHERE a.start >= ? AND m.imdb_id IS NULL
             AND (julianday(a.end) - julianday(a.start)) * 1440 >= ?
           ORDER BY a.title""",
        (since, MIN_MINUTES),
    ).fetchall()
    unmatched = [(t,) for (t,) in unmatched if not is_series(t)]

    built = []   # (id, nome, intro, itens)
    for sid, name, belongs, intro in sections:
        items = []
        for f in films:
            mine = [a for a in f["airings"] if belongs(a[1], a[2])]
            if mine:
                items.append(film_item(f, mine, sid, now))
        built.append((sid, name, intro, items))
    counts = {name: len(items) for _, name, _, items in built}

    css = Path(__file__).with_name("estilo.css").read_text(encoding="utf-8")
    parts = [
        "<!doctype html>",
        "<html lang='pt'>",
        "<meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<meta name='theme-color' content='#17278f'>",
        "<title>Filmes na TV</title>",
        "<link rel='preconnect' href='https://fonts.googleapis.com'>",
        "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>",
        f"<link rel='stylesheet' href='{FONTS}'>",
        f"<style>{css}</style>",
        "<body>",
        "<header class='top'><div class='wrap'><h1>Filmes na TV</h1>"
        f"<p>Ordenados por rating IMDb.</p><p class='stamp'>Atualizado {fmt_when(now)}</p></div></header>",
        "<nav class='jump' aria-label='Secções'><div class='wrap'>"
        + "".join(
            f"<a href='#{sid}'{HIDDEN if sid == 'agora' and not items else ''}>"
            f"<span class='i-{sid}'>{ICONS[sid]}</span>{name} <b>{len(items)}</b></a>"
            for sid, name, _, items in built
        )
        + "</div></nav>",
        "<main class='wrap'>",
    ]
    notice = history_notice(db, now)
    if notice:
        parts.append(f"<p class='aviso'>{notice}</p>")
    for sid, name, intro, items in built:
        # "A dar agora" fica escondida (não ausente) quando vazia: o script pode mostrá-la ao longo do dia
        parts.append(
            f"<section id='{sid}' class='s-{sid}' aria-labelledby='h-{sid}'{HIDDEN if sid == 'agora' and not items else ''}>"
            f"<h2 id='h-{sid}'>{ICONS[sid]}<span class='name'>{name}</span><span class='count'>{len(items)}</span></h2>"
        )
        if intro:
            parts.append(f"<p class='intro'>{intro}</p>")
        parts.append("<ol class='films'>" + "\n".join(items) + "</ol>")
        parts.append(f"<p class='empty'{HIDDEN if items else ''}>Nada de momento.</p>")
        parts.append("</section>")
    if unmatched:
        parts.append(
            "<details><summary><h2><span class='name'>Sem correspondência</span>"
            f"<span class='count'>{len(unmatched)}</span></h2></summary><ul>"
            + "".join(f"<li>{html.escape(t)}</li>" for (t,) in unmatched)
            + "</ul></details>"
        )
    parts.append("</main>")
    parts.append(FOOTER)
    parts.append("<script>" + Path(__file__).with_name("pagina.js").read_text(encoding="utf-8") + "</script>")
    Path(OUT_PATH).write_text("\n".join(parts), encoding="utf-8")
    print(f"\n{', '.join(f'{n}: {c}' for n, c in counts.items())}; {len(unmatched)} sem correspondência -> {OUT_PATH}")


def main():
    if not TMDB_KEY:
        sys.exit("Define a variável de ambiente TMDB_API_KEY.")
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS airings(
            channel TEXT, start TEXT, end TEXT, title TEXT, PRIMARY KEY(channel, start));
        CREATE TABLE IF NOT EXISTS matches(
            title TEXT PRIMARY KEY, imdb_id TEXT, original TEXT, year TEXT, runtime INT, checked TEXT);
        CREATE TABLE IF NOT EXISTS ratings(
            tconst TEXT PRIMARY KEY, rating REAL, votes INT);
        """
    )
    migrate(db)
    import_state(db)
    read = 0
    for channel, slug in discover_slugs().items():
        try:
            read += bool(scrape_channel(db, channel, slug))
        except requests.RequestException as e:
            print(f"! {channel}: {e}", file=sys.stderr)
    if not read:
        # sem isto, uma falha total do site (ex.: bloqueio) publicaria uma página desatualizada sem avisar
        sys.exit("Nenhum canal foi lido do tudonumclick.com; nada foi atualizado.")
    prune(db)
    load_ratings(db)
    match_titles(db)
    report(db)
    export_state(db)


if __name__ == "__main__":
    main()
