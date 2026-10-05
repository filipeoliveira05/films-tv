import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import requests

import filmes_tv
from filmes_tv import export_state, fill_posters, import_state, init_db, match_titles, migrate, poster_url

NOW = datetime(2026, 10, 5, 12, 0)


class PosterUrlTest(unittest.TestCase):
    def test_endereco_do_tmdb(self):
        self.assertEqual(poster_url("/abc.jpg"), "https://image.tmdb.org/t/p/w185/abc.jpg")

    def test_sem_poster(self):
        for vazio in (None, "", "-"):
            self.assertIsNone(poster_url(vazio))


class MigracaoTest(unittest.TestCase):
    def test_acrescenta_a_coluna_poster_a_uma_bd_antiga(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE matches(title TEXT PRIMARY KEY, imdb_id TEXT, original TEXT, year TEXT, runtime INT)")
        db.execute("INSERT INTO matches VALUES ('X','tt1','X','2000',90)")
        migrate(db)
        migrate(db)   # idempotente
        self.assertIn("poster", [r[1] for r in db.execute("PRAGMA table_info(matches)")])
        self.assertIsNone(db.execute("SELECT poster FROM matches").fetchone()[0])


class FillPostersTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        init_db(self.db)
        self.db.executemany(
            "INSERT INTO matches (title, imdb_id, original, year, runtime, checked, poster) VALUES (?,?,?,?,?,?,?)",
            [
                ("Com Poster", "tt_ok", "A", "2000", 90, "x", None),
                ("Sem Poster No TMDB", "tt_sem", "B", "2000", 90, "x", None),
                ("Desconhecido", "tt_nada", "C", "2000", 90, "x", None),
                ("Rede Falhou", "tt_rede", "D", "2000", 90, "x", None),
                ("Ja Tem", "tt_ja", "E", "2000", 90, "x", "/ja.jpg"),
                ("Sem Match", None, None, None, None, "x", None),
            ],
        )
        self.chamadas = []
        self._tmdb = filmes_tv.tmdb

        def falso(path, **params):
            self.chamadas.append((path, params))
            if path == "/find/tt_ok":
                return {"movie_results": [{"poster_path": "/ok.jpg"}]}
            if path == "/find/tt_sem":
                return {"movie_results": [{"poster_path": None}]}
            if path == "/find/tt_nada":
                return {"movie_results": []}
            raise requests.ConnectionError("rede")

        filmes_tv.tmdb = falso
        self.addCleanup(setattr, filmes_tv, "tmdb", self._tmdb)

    def poster(self, imdb):
        return self.db.execute("SELECT poster FROM matches WHERE imdb_id = ?", (imdb,)).fetchone()[0]

    def test_preenche_so_o_que_falta(self):
        fill_posters(self.db, delay=0)
        self.assertEqual(self.poster("tt_ok"), "/ok.jpg")
        self.assertEqual(self.poster("tt_ja"), "/ja.jpg")
        self.assertEqual({p for p, _ in self.chamadas}, {"/find/tt_ok", "/find/tt_sem", "/find/tt_nada", "/find/tt_rede"})

    def test_marca_com_traco_o_que_nao_tem_poster_para_nao_repetir(self):
        fill_posters(self.db, delay=0)
        self.assertEqual(self.poster("tt_sem"), "-")
        self.assertEqual(self.poster("tt_nada"), "-")
        self.chamadas.clear()
        fill_posters(self.db, delay=0)
        self.assertEqual([p for p, _ in self.chamadas], ["/find/tt_rede"])   # só o que falhou por rede

    def test_falha_de_rede_deixa_para_a_proxima(self):
        fill_posters(self.db, delay=0)
        self.assertIsNone(self.poster("tt_rede"))

    def test_pesquisa_por_imdb_id(self):
        fill_posters(self.db, delay=0)
        self.assertIn(("/find/tt_ok", {"external_source": "imdb_id"}), self.chamadas)


class MatchTitlesGuardaPosterTest(unittest.TestCase):
    def test_guarda_o_poster_do_match(self):
        db = sqlite3.connect(":memory:")
        init_db(db)
        db.executemany("INSERT INTO airings VALUES (?,?,?,?)", [
            ("AXN", "2026-10-06T20:00:00", "2026-10-06T22:00:00", "Filme Bom"),
            ("AXN", "2026-10-07T20:00:00", "2026-10-07T22:00:00", "Filme Sem Match"),
        ])
        saved = filmes_tv.match_title, filmes_tv.time.sleep
        filmes_tv.match_title = lambda t, m: ("tt9", "Good Film", "2020", 118, "/bom.jpg") if t == "Filme Bom" else None
        filmes_tv.time.sleep = lambda s: None
        self.addCleanup(lambda: (setattr(filmes_tv, "match_title", saved[0]), setattr(filmes_tv.time, "sleep", saved[1])))
        match_titles(db)
        self.assertEqual(db.execute("SELECT imdb_id, poster FROM matches WHERE title='Filme Bom'").fetchone(), ("tt9", "/bom.jpg"))
        self.assertEqual(db.execute("SELECT imdb_id, poster FROM matches WHERE title='Filme Sem Match'").fetchone(), (None, None))


class EstadoComPosterTest(unittest.TestCase):
    def test_poster_vai_para_o_csv_e_volta(self):
        d = Path(tempfile.mkdtemp()) / "data"
        a = sqlite3.connect(":memory:")
        init_db(a)
        a.execute("INSERT INTO matches (title, imdb_id, original, year, runtime, checked, poster) VALUES ('Duna','tt1','Dune','2021',155,'x','/duna.jpg')")
        a.execute("INSERT INTO matches (title, imdb_id, original, year, runtime, checked, poster) VALUES ('Outro','tt2','O','2000',90,'x','-')")
        export_state(a, d)
        b = sqlite3.connect(":memory:")
        init_db(b)
        import_state(b, d)
        self.assertEqual(b.execute("SELECT title, poster FROM matches ORDER BY title").fetchall(), [("Duna", "/duna.jpg"), ("Outro", "-")])


def pagina(posters):
    db = sqlite3.connect(":memory:")
    init_db(db)
    for i, (titulo, poster) in enumerate(posters):
        db.execute("INSERT INTO matches (title, imdb_id, original, year, runtime, checked, poster) VALUES (?,?,?,?,?,?,?)",
                   (titulo, f"tt{i}", titulo, "2000", 100, "x", poster))
        db.execute("INSERT INTO ratings VALUES (?,?,?)", (f"tt{i}", 7.0, 1000))
        db.execute("INSERT INTO airings VALUES ('AXN', ?, ?, ?)", (f"2026-10-0{6 + i}T20:00:00", f"2026-10-0{6 + i}T22:00:00", titulo))
    out = Path(tempfile.mkdtemp()) / "o.html"
    old = filmes_tv.OUT_PATH
    filmes_tv.OUT_PATH = str(out)
    try:
        filmes_tv.report(db, now=NOW)
    finally:
        filmes_tv.OUT_PATH = old
    return out.read_text(encoding="utf-8")


class PaginaComPosterTest(unittest.TestCase):
    def setUp(self):
        self.html = pagina([("Com", "/com.jpg"), ("Sem", None), ("Traco", "-")])

    def test_imagem_com_tamanho_fixo_e_lazy(self):
        self.assertIn(
            "<div class='poster'><img src='https://image.tmdb.org/t/p/w185/com.jpg' alt='' "
            "width='185' height='278' loading='lazy' decoding='async'></div>",
            self.html,
        )

    def test_placeholder_com_o_mesmo_tamanho_quando_nao_ha_poster(self):
        self.assertEqual(self.html.count("<div class='poster none'></div>"), 2)   # NULL e '-'

    def test_um_poster_por_filme(self):
        self.assertEqual(self.html.count("<div class='poster"), 3)

    def test_airings_ocupam_a_largura_toda_fora_do_cabecalho(self):
        self.assertNotIn("class='info'", self.html)
        self.assertIn("<div class='head'><h3>", self.html)

    def test_atribuicao_com_logotipo_do_tmdb(self):
        rodape = self.html[self.html.index("<footer>"):]
        self.assertIn("aria-label='TMDB'", rodape)
        self.assertIn("<svg", rodape)
        self.assertIn("themoviedb.org", rodape)
        self.assertIn("imagens", rodape)       # os termos do TMDB pedem atribuição também para imagens


if __name__ == "__main__":
    unittest.main()
