import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import filmes_tv


def iso(days):
    return (datetime.now() + timedelta(days=days)).replace(microsecond=0).isoformat()


class RelatorioTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(
            """
            CREATE TABLE airings(channel TEXT, start TEXT, end TEXT, title TEXT, PRIMARY KEY(channel, start));
            CREATE TABLE matches(title TEXT PRIMARY KEY, imdb_id TEXT, original TEXT, year TEXT, runtime INT);
            CREATE TABLE ratings(tconst TEXT PRIMARY KEY, rating REAL, votes INT);
            """
        )
        self.db.executemany(
            "INSERT INTO matches VALUES (?,?,?,?,?)",
            [
                ("Mínimos (VP)", "tt1", "Minions", "2015", 91),
                ("Mínimos", "tt1", "Minions", "2015", 91),
                ("O Caso DeLorean", "tt2", "Driven", "2019", 108),
                ("O Caso Delorean", "tt2", "Driven", "2019", 108),
                ("Duna", "tt3", "Dune", "2021", 155),
            ],
        )
        self.db.executemany("INSERT INTO ratings VALUES (?,?,?)", [("tt1", 6.4, 1000), ("tt2", 6.0, 500), ("tt3", 8.0, 9000)])
        rows = [
            ("TVCine Top", iso(1), iso(1.1), "Mínimos"),
            ("Panda", iso(2), iso(2.1), "Mínimos (VP)"),
            ("NOS Studios", iso(1), iso(1.1), "O Caso DeLorean"),
            ("NOS Studios", iso(2), iso(2.1), "O Caso Delorean"),
            ("AXN", iso(3), iso(3.1), "Duna"),
        ]
        self.db.executemany("INSERT INTO airings VALUES (?,?,?,?)", rows)
        self.out = Path(tempfile.mkdtemp()) / "out.html"
        self._old = filmes_tv.OUT_PATH
        filmes_tv.OUT_PATH = str(self.out)
        filmes_tv.report(self.db)
        self.html = self.out.read_text(encoding="utf-8")

    def tearDown(self):
        filmes_tv.OUT_PATH = self._old

    def test_junta_vp_e_variantes_de_maiusculas(self):
        self.assertEqual(self.html.count("<li><span class='r'>"), 3)

    def test_titulo_sem_vp_e_horarios_juntos(self):
        self.assertIn(">Mínimos</a>", self.html)
        self.assertNotIn(">Mínimos (VP)</a>", self.html)
        self.assertIn("TVCine Top", self.html)
        self.assertIn("Panda (VP)", self.html)   # emissão dobrada marcada

    def test_ano_junto_ao_titulo(self):
        self.assertIn("Duna</a> <span class='y'>(2021)</span>", self.html)

    def test_ordem_por_rating(self):
        self.assertLess(self.html.index("Duna"), self.html.index("Mínimos"))


if __name__ == "__main__":
    unittest.main()
