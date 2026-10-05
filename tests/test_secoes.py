import re
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import filmes_tv
from filmes_tv import fmt_remaining, fmt_when

NOW = datetime(2026, 10, 5, 12, 0)   # segunda-feira


class FormatosTest(unittest.TestCase):
    def test_remaining(self):
        self.assertEqual(fmt_remaining(timedelta(days=4, hours=8, minutes=5)), "4d 8h")
        self.assertEqual(fmt_remaining(timedelta(hours=5, minutes=30)), "5h 30m")
        self.assertEqual(fmt_remaining(timedelta(minutes=45)), "45m")

    def test_when_em_portugues(self):
        self.assertEqual(fmt_when(datetime(2026, 10, 5, 9, 20)), "seg 05/10 09:20")
        self.assertEqual(fmt_when(datetime(2026, 10, 10, 23, 5)), "sáb 10/10 23:05")


def dt(day, hour, minute=0):
    return datetime(2026, 10, day, hour, minute).isoformat()


class SeccoesTest(unittest.TestCase):
    def setUp(self):
        db = sqlite3.connect(":memory:")
        db.executescript(
            """
            CREATE TABLE airings(channel TEXT, start TEXT, end TEXT, title TEXT, PRIMARY KEY(channel, start));
            CREATE TABLE matches(title TEXT PRIMARY KEY, imdb_id TEXT, original TEXT, year TEXT, runtime INT, poster TEXT);
            CREATE TABLE ratings(tconst TEXT PRIMARY KEY, rating REAL, votes INT);
            """
        )
        db.executemany("INSERT INTO matches (title, imdb_id, original, year, runtime) VALUES (?,?,?,?,?)", [
            ("Alfa", "tt1", "Alpha", "2001", 100),    # passou há 3 dias e volta dia 7
            ("Beta", "tt2", "Beta", "2002", 100),     # só futuro
            ("Gama", "tt3", "Gamma", "2003", 100),    # a dar agora
            ("Delta", "tt4", "Delta", "2004", 100),   # há 8 dias: já não está disponível
            ("Epsilon", "tt5", "Epsilon", "2005", 100),  # passou ontem, rating mais alto
            ("Zeta", "tt6", "Zeta", "2006", 100),     # passou há quase 7 dias
        ])
        db.executemany("INSERT INTO ratings VALUES (?,?,?)", [
            ("tt1", 7.0, 1000), ("tt2", 8.0, 1000), ("tt3", 6.0, 1000),
            ("tt4", 9.9, 1000), ("tt5", 8.5, 1000), ("tt6", 5.0, 1000),
        ])
        db.executemany("INSERT INTO airings VALUES (?,?,?,?)", [
            ("AXN", dt(2, 20), dt(2, 22), "Alfa"),
            ("AXN", dt(7, 21), dt(7, 23), "Alfa"),
            ("Hollywood", dt(8, 21), dt(8, 23), "Beta"),
            ("SyFy", dt(5, 11), dt(5, 13), "Gama"),
            ("AMC", datetime(2026, 9, 27, 21).isoformat(), datetime(2026, 9, 27, 23).isoformat(), "Delta"),
            ("AMC", dt(4, 21), dt(4, 23), "Epsilon"),
            ("AMC", datetime(2026, 9, 28, 12, 30).isoformat(), datetime(2026, 9, 28, 14).isoformat(), "Zeta"),
        ])
        self.out = Path(tempfile.mkdtemp()) / "out.html"
        old = filmes_tv.OUT_PATH
        filmes_tv.OUT_PATH = str(self.out)
        self.addCleanup(setattr, filmes_tv, "OUT_PATH", old)
        filmes_tv.report(db, now=NOW)
        html_ = self.out.read_text(encoding="utf-8")
        self.sec = {}
        for part in html_.split("<h2")[1:]:
            name = re.search(r"<span class='name'>([^<]+)</span>", part).group(1)
            self.sec[name] = part

    def titulos(self, secao):
        return re.findall(r"<a href='https://www\.imdb\.com[^']*'>([^<]+)</a>", self.sec[secao])

    def test_para_gravar_ordenado_por_rating(self):
        self.assertEqual(self.titulos("Para gravar"), ["Epsilon", "Alfa", "Zeta"])

    def test_a_vir_ordenado_por_rating(self):
        self.assertEqual(self.titulos("A vir"), ["Beta", "Alfa"])

    def test_a_dar_agora_a_parte(self):
        self.assertEqual(self.titulos("A dar agora"), ["Gama"])
        self.assertNotIn("Gama", self.titulos("Para gravar") + self.titulos("A vir"))

    def test_filme_fora_da_janela_nao_aparece(self):
        for s in self.sec.values():
            self.assertNotIn("Delta", s)

    def test_cada_seccao_so_tem_as_suas_emissoes(self):
        # Alfa: a emissão de dia 2 só em "Para gravar", a de dia 7 só em "A vir"
        self.assertIn("sex 02/10", self.sec["Para gravar"])
        self.assertNotIn("qua 07/10", self.sec["Para gravar"])
        self.assertIn("qua 07/10", self.sec["A vir"])
        self.assertNotIn("sex 02/10", self.sec["A vir"])

    def test_a_dar_agora_mostra_a_hora_de_fim(self):
        self.assertIn("termina às 13:00", self.sec["A dar agora"])

    def test_a_vir_mostra_quanto_falta(self):
        self.assertIn("em 2d 9h", self.sec["A vir"])      # Alfa: qua 07/10 21:00, agora seg 05/10 12:00

    def test_prazo_de_disponibilidade(self):
        # Alfa passou sex 02/10 20:00 -> até sex 09/10 20:00, faltam 4d 8h
        self.assertIn("faltam 4d 8h", self.sec["Para gravar"])
        self.assertIn("até sex 09/10 20:00", self.sec["Para gravar"])

    def test_urgente_quando_falta_menos_de_um_dia(self):
        # Zeta passou 28/09 12:30 -> expira 05/10 12:30, faltam 30 min
        self.assertRegex(self.sec["Para gravar"], r"<li class='airing urgent'[^>]*><span class='where'><b>AMC</b> seg 28/09")
        self.assertNotRegex(self.sec["Para gravar"], r"<li class='airing urgent'[^>]*><span class='where'><b>AXN</b> sex 02/10")
        self.assertIn("faltam 30m", self.sec["Para gravar"])


if __name__ == "__main__":
    unittest.main()
