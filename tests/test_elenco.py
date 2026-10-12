import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import requests

import filmes_tv
from filmes_tv import elenco_from_details, export_state, fill_elenco, import_state, init_db, match_titles, migrate

NOW = datetime(2026, 10, 5, 12, 0)


class ElencoFromDetailsTest(unittest.TestCase):
    def test_nomes_em_ordem_de_credito(self):
        d = {"credits": {"cast": [{"name": "Tom Hanks"}, {"name": "Colin Hanks"}]}}
        self.assertEqual(elenco_from_details(d), "Tom Hanks|Colin Hanks")

    def test_sem_elenco_fica_marcado(self):
        self.assertEqual(elenco_from_details({"credits": {"cast": []}}), "-")
        self.assertEqual(elenco_from_details({}), "-")
        self.assertEqual(elenco_from_details({"credits": None}), "-")

    def test_barra_vertical_no_nome_nao_parte_a_lista(self):
        self.assertEqual(elenco_from_details({"credits": {"cast": [{"name": "A|B"}, {"name": "C"}]}}), "A B|C")

    def test_ignora_entradas_sem_nome(self):
        self.assertEqual(elenco_from_details({"credits": {"cast": [{"name": ""}, {}, {"name": "X"}]}}), "X")


class MigracaoTest(unittest.TestCase):
    def test_acrescenta_a_coluna_elenco(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE matches(title TEXT PRIMARY KEY, imdb_id TEXT, original TEXT, year TEXT, runtime INT, checked TEXT, poster TEXT)")
        migrate(db)
        migrate(db)
        self.assertIn("elenco", [r[1] for r in db.execute("PRAGMA table_info(matches)")])


class FillElencoTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        init_db(self.db)
        self.db.executemany(
            "INSERT INTO matches (title, imdb_id, original, year, runtime, checked, poster, elenco) VALUES (?,?,?,?,?,?,?,?)",
            [
                ("Com Elenco", "tt_ok", "A", "2000", 90, "x", "/a.jpg", None),
                ("Sem Elenco", "tt_sem", "B", "2000", 90, "x", "/b.jpg", None),
                ("Desconhecido", "tt_nada", "C", "2000", 90, "x", "-", None),
                ("Rede Falhou", "tt_rede", "D", "2000", 90, "x", "/d.jpg", None),
                ("Ja Tem", "tt_ja", "E", "2000", 90, "x", "/e.jpg", "Ana|Rui"),
                ("Sem Match", None, None, None, None, "x", None, None),
            ],
        )
        self.chamadas = []
        self._tmdb = filmes_tv.tmdb

        def falso(path, **params):
            self.chamadas.append(path)
            if path == "/find/tt_ok":
                return {"movie_results": [{"id": 11}]}
            if path == "/movie/11/credits":
                return {"cast": [{"name": "Tom Hanks"}, {"name": "Meg Ryan"}]}
            if path == "/find/tt_sem":
                return {"movie_results": [{"id": 12}]}
            if path == "/movie/12/credits":
                return {"cast": []}
            if path == "/find/tt_nada":
                return {"movie_results": []}
            raise requests.ConnectionError("rede")

        filmes_tv.tmdb = falso
        self.addCleanup(setattr, filmes_tv, "tmdb", self._tmdb)

    def elenco(self, imdb):
        return self.db.execute("SELECT elenco FROM matches WHERE imdb_id = ?", (imdb,)).fetchone()[0]

    def test_preenche_so_o_que_falta(self):
        fill_elenco(self.db, delay=0)
        self.assertEqual(self.elenco("tt_ok"), "Tom Hanks|Meg Ryan")
        self.assertEqual(self.elenco("tt_ja"), "Ana|Rui")
        self.assertNotIn("/find/tt_ja", self.chamadas)

    def test_marca_com_traco_o_que_nao_tem_elenco_para_nao_repetir(self):
        fill_elenco(self.db, delay=0)
        self.assertEqual(self.elenco("tt_sem"), "-")
        self.assertEqual(self.elenco("tt_nada"), "-")
        self.chamadas.clear()
        fill_elenco(self.db, delay=0)
        self.assertEqual(self.chamadas, ["/find/tt_rede"])      # só o que falhou por rede

    def test_falha_de_rede_deixa_para_a_proxima(self):
        fill_elenco(self.db, delay=0)
        self.assertIsNone(self.elenco("tt_rede"))


class MatchTitlesGuardaElencoTest(unittest.TestCase):
    def test_guarda_o_elenco_do_match(self):
        db = sqlite3.connect(":memory:")
        init_db(db)
        db.execute("INSERT INTO airings VALUES ('AXN','2026-10-06T20:00:00','2026-10-06T22:00:00','Filme Bom')")
        saved = filmes_tv.match_title, filmes_tv.time.sleep
        filmes_tv.match_title = lambda t, m: ("tt9", "Good Film", "2020", 118, "/bom.jpg", "Ana|Rui")
        filmes_tv.time.sleep = lambda s: None
        self.addCleanup(lambda: (setattr(filmes_tv, "match_title", saved[0]), setattr(filmes_tv.time, "sleep", saved[1])))
        match_titles(db)
        self.assertEqual(db.execute("SELECT poster, elenco FROM matches").fetchone(), ("/bom.jpg", "Ana|Rui"))


class EstadoComElencoTest(unittest.TestCase):
    def test_elenco_vai_para_o_csv_e_volta(self):
        d = Path(tempfile.mkdtemp()) / "data"
        a = sqlite3.connect(":memory:")
        init_db(a)
        a.execute("INSERT INTO matches (title, imdb_id, original, year, runtime, checked, poster, elenco) VALUES ('Duna','tt1','Dune','2021',155,'x','/d.jpg',\"Timothée Chalamet|Zendaya\")")
        a.execute("INSERT INTO matches (title, imdb_id, original, year, runtime, checked, poster, elenco) VALUES ('Outro','tt2','O','2000',90,'x','/o.jpg','-')")
        export_state(a, d)
        b = sqlite3.connect(":memory:")
        init_db(b)
        import_state(b, d)
        self.assertEqual(b.execute("SELECT title, elenco FROM matches ORDER BY title").fetchall(),
                         [("Duna", "Timothée Chalamet|Zendaya"), ("Outro", "-")])


def pagina(elencos):
    db = sqlite3.connect(":memory:")
    init_db(db)
    for i, (titulo, elenco) in enumerate(elencos):
        db.execute("INSERT INTO matches (title, imdb_id, original, year, runtime, checked, poster, elenco) VALUES (?,?,?,?,?,?,?,?)",
                   (titulo, f"tt{i}", titulo, "2000", 100, "x", "/p.jpg", elenco))
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


class PaginaComElencoTest(unittest.TestCase):
    def setUp(self):
        self.html = pagina([
            ("Com Muitos", "Ana Silva|Rui Costa|Eva Dias|Rita Gomes|Luis Reis"),
            ("Com Apostrofo", "Peter O'Toole|Maria <b>"),
            ("Sem Elenco", "-"),
            ("Nulo", None),
        ])

    def test_linha_com_os_tres_primeiros(self):
        self.assertIn("<p class='cast'>Com Ana Silva, Rui Costa, Eva Dias</p>", self.html)
        self.assertNotIn("Rita Gomes</p>", self.html)           # o 4.º não aparece na linha fixa

    def test_elenco_todo_em_data_cast_para_a_pesquisa(self):
        self.assertIn("data-cast='Ana Silva|Rui Costa|Eva Dias|Rita Gomes|Luis Reis'", self.html)

    def test_nomes_com_aspas_e_html_sao_escapados(self):
        self.assertIn("data-cast='Peter O&#x27;Toole|Maria &lt;b&gt;'", self.html)
        self.assertIn("<p class='cast'>Com Peter O&#x27;Toole, Maria &lt;b&gt;</p>", self.html)
        self.assertNotIn("<b>Maria", self.html)

    def test_sem_elenco_nao_ha_linha_nem_atributo(self):
        for titulo in ("Sem Elenco", "Nulo"):
            li = self.html[self.html.index(f">{titulo}</a>"):]
            li = li[:li.index("</li><li class='film'") if "</li><li class='film'" in li else len(li)]
            self.assertNotIn("class='cast'", li.split("<ul class='airings'>")[0])

    def test_linha_dentro_do_cabecalho_do_filme(self):
        self.assertRegex(self.html, r"<div class='head'><h3>.*?</h3>(<p class='orig'>[^<]*</p>)?<p class='cast'>")


if __name__ == "__main__":
    unittest.main()
