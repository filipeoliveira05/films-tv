import re
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import filmes_tv


def gerar(airings, now):
    db = sqlite3.connect(":memory:")
    db.executescript(
        """
        CREATE TABLE airings(channel TEXT, start TEXT, end TEXT, title TEXT, PRIMARY KEY(channel, start));
        CREATE TABLE matches(title TEXT PRIMARY KEY, imdb_id TEXT, original TEXT, year TEXT, runtime INT, poster TEXT);
        CREATE TABLE ratings(tconst TEXT PRIMARY KEY, rating REAL, votes INT);
        """
    )
    db.executemany("INSERT INTO matches (title, imdb_id, original, year, runtime) VALUES (?,?,?,?,?)", [("Alfa", "tt1", "A", "2001", 100), ("Beta", "tt2", "B", "2002", 100)])
    db.executemany("INSERT INTO ratings VALUES (?,?,?)", [("tt1", 7.0, 1000), ("tt2", 8.0, 1000)])
    db.executemany("INSERT INTO airings VALUES (?,?,?,?)", airings)
    out = Path(tempfile.mkdtemp()) / "o.html"
    old = filmes_tv.OUT_PATH
    filmes_tv.OUT_PATH = str(out)
    try:
        filmes_tv.report(db, now=now)
    finally:
        filmes_tv.OUT_PATH = old
    return out.read_text(encoding="utf-8")


NOW = datetime(2026, 10, 5, 12, 0)
AIRINGS = [
    ("AXN", "2026-10-02T20:00:00", "2026-10-02T22:00:00", "Alfa"),
    ("AMC", "2026-10-08T21:00:00", "2026-10-08T23:00:00", "Beta"),
]


class ContratoTest(unittest.TestCase):
    def setUp(self):
        self.html = gerar(AIRINGS, NOW)

    def test_instantes_absolutos_em_utc(self):
        # 02/10 20:00 em Lisboa (WEST, UTC+1) = 19:00 UTC
        esperado = int(datetime(2026, 10, 2, 19, 0, tzinfo=timezone.utc).timestamp())
        self.assertIn(f"data-start='{esperado}'", self.html)
        fim = int(datetime(2026, 10, 2, 21, 0, tzinfo=timezone.utc).timestamp())
        self.assertIn(f"data-end='{fim}'", self.html)

    def test_inverno_usa_utc_mais_zero(self):
        h = gerar([("AXN", "2026-12-02T20:00:00", "2026-12-02T22:00:00", "Alfa")], datetime(2026, 12, 3, 12, 0))
        self.assertIn(f"data-start='{int(datetime(2026, 12, 2, 20, 0, tzinfo=timezone.utc).timestamp())}'", h)

    def test_etiquetas_estaticas_para_o_script(self):
        self.assertIn("data-until='até sex 09/10 20:00'", self.html)
        self.assertIn("data-end-label='22:00'", self.html)

    def test_filmes_com_id_e_ordem_por_rating(self):
        m = re.findall(r"<li class='film' data-film='(tt\d)' data-rank='(\d+)'>", self.html)
        ranks = {i: int(r) for i, r in m}
        self.assertLess(ranks["tt2"], ranks["tt1"])      # Beta (8.0) vem antes de Alfa (7.0)

    def test_a_dar_agora_existe_mas_escondida_quando_vazia(self):
        self.assertIn("<section id='agora' class='s-agora' aria-labelledby='h-agora' hidden>", self.html)
        self.assertIn("<a href='#agora' hidden>", self.html)

    def test_listas_sempre_presentes(self):
        self.assertEqual(self.html.count("<ol class='films'>"), 3)

    def test_mensagem_de_vazio_escondida_se_houver_filmes(self):
        self.assertIn("<p class='empty' hidden>Nada de momento.</p>", self.html)   # há filmes em gravar e vir
        self.assertIn("<p class='empty'>Nada de momento.</p>", self.html)          # agora está vazia

    def test_script_embutido(self):
        self.assertIn("<script>", self.html)
        self.assertIn("setInterval", self.html)


if __name__ == "__main__":
    unittest.main()
