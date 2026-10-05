import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import filmes_tv
from filmes_tv import export_state, init_db, read_stamp, relatorio_local, write_stamp


class CarimboTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "data"

    def test_ida_e_volta(self):
        write_stamp(self.dir, datetime(2026, 10, 5, 6, 0, 17, 999))
        self.assertEqual(read_stamp(self.dir), datetime(2026, 10, 5, 6, 0, 17))

    def test_sem_ficheiro_ou_lixo(self):
        self.assertIsNone(read_stamp(self.dir))
        self.dir.mkdir(parents=True)
        (self.dir / "atualizado.txt").write_text("não é uma data", encoding="utf-8")
        self.assertIsNone(read_stamp(self.dir))


class InitDbTest(unittest.TestCase):
    def test_cria_tabelas_e_e_idempotente(self):
        db = sqlite3.connect(":memory:")
        init_db(db)
        init_db(db)
        tabelas = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"airings", "matches", "ratings"} <= tabelas)
        self.assertIn("checked", [r[1] for r in db.execute("PRAGMA table_info(matches)")])


class RelatorioLocalTest(unittest.TestCase):
    """O que o GitHub faz num push: base de dados vazia + data/ + ratings, sem pedidos ao site nem ao TMDB."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "data"
        origem = sqlite3.connect(":memory:")
        init_db(origem)
        origem.execute("INSERT INTO matches VALUES ('Duna','tt1','Dune','2021',155,'2026-10-05T10:00:00')")
        origem.execute("INSERT INTO airings VALUES ('AXN','2099-01-01T20:00:00','2099-01-01T22:00:00','Duna')")
        export_state(origem, self.dir)
        write_stamp(self.dir, datetime(2026, 10, 5, 6, 0))
        self.out = Path(tempfile.mkdtemp()) / "o.html"
        self._saved = (filmes_tv.OUT_PATH, filmes_tv.load_ratings)
        filmes_tv.OUT_PATH = str(self.out)
        self.chamadas = []

        def ratings_falsos(db):
            self.chamadas.append("ratings")
            db.execute("INSERT OR REPLACE INTO ratings VALUES ('tt1', 8.0, 9000)")

        filmes_tv.load_ratings = ratings_falsos
        self.addCleanup(lambda: (setattr(filmes_tv, "OUT_PATH", self._saved[0]), setattr(filmes_tv, "load_ratings", self._saved[1])))

    def test_gera_a_pagina_a_partir_de_data_e_ratings(self):
        db = sqlite3.connect(":memory:")          # como no GitHub: sem filmes.db nem tabelas
        relatorio_local(db, self.dir)
        h = self.out.read_text(encoding="utf-8")
        self.assertEqual(self.chamadas, ["ratings"])
        self.assertIn(">Duna</a>", h)
        self.assertIn("<b>8.0</b>", h)

    def test_mostra_a_hora_da_ultima_recolha_e_nao_a_da_geracao(self):
        relatorio_local(sqlite3.connect(":memory:"), self.dir)
        self.assertIn("Atualizado seg 05/10 06:00", self.out.read_text(encoding="utf-8"))

    def test_sem_carimbo_usa_a_hora_de_agora(self):
        (self.dir / "atualizado.txt").unlink()
        relatorio_local(sqlite3.connect(":memory:"), self.dir)
        self.assertIn("Atualizado ", self.out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
