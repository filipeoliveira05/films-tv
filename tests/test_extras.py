import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import filmes_tv
from filmes_tv import history_notice, migrate, titles_to_match

NOW = datetime(2026, 10, 20, 12, 0)


def novo_db():
    db = sqlite3.connect(":memory:")
    db.executescript(
        """
        CREATE TABLE airings(channel TEXT, start TEXT, end TEXT, title TEXT, PRIMARY KEY(channel, start));
        CREATE TABLE matches(title TEXT PRIMARY KEY, imdb_id TEXT, original TEXT, year TEXT, runtime INT);
        CREATE TABLE ratings(tconst TEXT PRIMARY KEY, rating REAL, votes INT);
        """
    )
    return db


def airing(db, title, start, minutes=100, channel="AXN"):
    end = start + timedelta(minutes=minutes)
    db.execute("INSERT INTO airings VALUES (?,?,?,?)", (channel, start.isoformat(), end.isoformat(), title))


class HistoryNoticeTest(unittest.TestCase):
    def test_sem_dados(self):
        self.assertIsNone(history_notice(novo_db(), NOW))

    def test_historico_incompleto(self):
        db = novo_db()
        airing(db, "A", datetime(2026, 10, 18, 21, 20))   # só há 2 dias
        msg = history_notice(db, NOW)
        self.assertIn("dom 18/10 21:20", msg)
        self.assertIn("dom 25/10 21:20", msg)      # completo a partir daqui

    def test_historico_completo(self):
        db = novo_db()
        airing(db, "A", NOW - timedelta(days=8))
        self.assertIsNone(history_notice(db, NOW))

    def test_relatorio_mostra_aviso(self):
        db = novo_db()
        airing(db, "A", datetime(2026, 10, 20, 8))
        out = Path(tempfile.mkdtemp()) / "o.html"
        old = filmes_tv.OUT_PATH
        filmes_tv.OUT_PATH = str(out)
        self.addCleanup(setattr, filmes_tv, "OUT_PATH", old)
        filmes_tv.report(db, now=NOW)
        h = out.read_text(encoding="utf-8")
        self.assertIn("class='aviso'", h)
        self.assertIn("themoviedb.org", h)          # atribuição TMDB no rodapé
        self.assertIn("não é endossado nem certificado pelo TMDB", h)


class RetryTest(unittest.TestCase):
    def setUp(self):
        self.db = novo_db()
        migrate(self.db)
        for i, t in enumerate(("Novo", "Falhou Ontem", "Falhou Há 40 Dias", "Acertou Há 40 Dias")):
            airing(self.db, t, NOW - timedelta(days=1, hours=i))
        self.db.executemany(
            "INSERT INTO matches VALUES (?,?,?,?,?,?)",
            [
                ("Falhou Ontem", None, None, None, None, (NOW - timedelta(days=1)).isoformat()),
                ("Falhou Há 40 Dias", None, None, None, None, (NOW - timedelta(days=40)).isoformat()),
                ("Acertou Há 40 Dias", "tt1", "X", "2000", 100, (NOW - timedelta(days=40)).isoformat()),
            ],
        )

    def test_novos_e_falhanços_antigos(self):
        titulos = {t for t, _ in titles_to_match(self.db, NOW)}
        self.assertEqual(titulos, {"Novo", "Falhou Há 40 Dias"})

    def test_migracao_marca_falhanços_antigos_como_verificados_agora(self):
        db = novo_db()
        db.execute("INSERT INTO matches VALUES ('Legado', NULL, NULL, NULL, NULL)")
        migrate(db, now=NOW)
        self.assertEqual(db.execute("SELECT checked FROM matches").fetchone()[0], NOW.isoformat())
        migrate(db, now=NOW)       # idempotente
        self.assertEqual(db.execute("SELECT COUNT(*) FROM matches").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
