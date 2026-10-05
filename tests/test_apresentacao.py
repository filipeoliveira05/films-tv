import re
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import filmes_tv
from filmes_tv import fmt_rating, fmt_votes, rating_tier, remaining_pct


class FormatosTest(unittest.TestCase):
    def test_rating_com_ponto(self):
        self.assertEqual(fmt_rating(9.3), "9.3")
        self.assertEqual(fmt_rating(7.0), "7.0")

    def test_votos_compactos(self):
        self.assertEqual(fmt_votes(3247765), "3,2 M votos")
        self.assertEqual(fmt_votes(63313), "63 mil votos")
        self.assertEqual(fmt_votes(812), "812 votos")
        self.assertEqual(fmt_votes(999800), "1,0 M votos")   # sem '1000 mil'

    def test_escaloes_de_rating(self):
        self.assertEqual(rating_tier(8.0), "hi")
        self.assertEqual(rating_tier(7.9), "")
        self.assertEqual(rating_tier(5.9), "lo")
        self.assertEqual(rating_tier(None), "none")

    def test_fita_da_janela_de_7_dias(self):
        self.assertAlmostEqual(remaining_pct(timedelta(days=3.5)), 50.0)
        self.assertEqual(remaining_pct(timedelta(days=9)), 100.0)
        self.assertEqual(remaining_pct(timedelta(hours=-2)), 0.0)


class PaginaTest(unittest.TestCase):
    def setUp(self):
        db = sqlite3.connect(":memory:")
        db.executescript(
            """
            CREATE TABLE airings(channel TEXT, start TEXT, end TEXT, title TEXT, PRIMARY KEY(channel, start));
            CREATE TABLE matches(title TEXT PRIMARY KEY, imdb_id TEXT, original TEXT, year TEXT, runtime INT);
            CREATE TABLE ratings(tconst TEXT PRIMARY KEY, rating REAL, votes INT);
            """
        )
        db.execute("INSERT INTO matches VALUES ('Duna','tt1','Dune','2021',155)")
        db.execute("INSERT INTO ratings VALUES ('tt1', 8.0, 812)")
        db.execute("INSERT INTO airings VALUES ('AXN','2026-10-02T20:00:00','2026-10-02T22:00:00','Duna')")
        db.execute("INSERT INTO airings VALUES ('AXN','2026-10-08T20:00:00','2026-10-08T22:00:00','Duna')")
        db.execute("INSERT INTO airings VALUES ('AMC','2026-10-08T20:00:00','2026-10-08T22:00:00','Sem Match Longo')")
        out = Path(tempfile.mkdtemp()) / "o.html"
        old = filmes_tv.OUT_PATH
        filmes_tv.OUT_PATH = str(out)
        self.addCleanup(setattr, filmes_tv, "OUT_PATH", old)
        filmes_tv.report(db, now=datetime(2026, 10, 5, 12, 0))
        self.html = out.read_text(encoding="utf-8")

    def test_documento_completo(self):
        self.assertTrue(self.html.startswith("<!doctype html>"))
        self.assertIn("<html lang='pt'>", self.html)
        self.assertIn("name='viewport'", self.html)

    def test_estilo_embutido(self):
        self.assertIn(":root", self.html)                 # estilo.css dentro da página
        self.assertIn("family=Archivo", self.html)

    def test_navegacao_com_contagens(self):
        nav = re.search(r"<nav.*?</nav>", self.html, re.S).group(0)
        self.assertIn("href='#gravar'", nav)
        self.assertIn("href='#vir'", nav)
        self.assertIn("href='#agora' hidden", nav)        # nada a dar agora: entrada escondida (o script pode mostrá-la)
        self.assertRegex(nav, r"Para gravar.*?<b>1</b>")

    def test_ids_das_seccoes(self):
        self.assertIn("id='gravar'", self.html)
        self.assertIn("id='vir'", self.html)

    def test_rating_votos_e_escalao(self):
        self.assertIn("<div class='score hi'><b>8.0</b><small>812 votos</small></div>", self.html)

    def test_sem_correspondencia_recolhida(self):
        self.assertIn("<details>", self.html)
        self.assertNotIn("<details open", self.html)
        self.assertIn("Sem Match Longo", self.html)

    def test_data_de_atualizacao(self):
        self.assertIn("Atualizado seg 05/10 12:00", self.html)

    def test_fita_com_percentagem(self):
        # expira dom 09/10 20:00 -> faltam 4d 8h de 7d = ~61,9 %
        self.assertRegex(self.html, r"<i style='width:61\.\d%'></i>")


if __name__ == "__main__":
    unittest.main()
