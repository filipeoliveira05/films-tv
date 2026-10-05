import sqlite3
import tempfile
import unittest
from pathlib import Path

from filmes_tv import export_state, import_state, migrate


def novo_db():
    db = sqlite3.connect(":memory:")
    db.executescript(
        """
        CREATE TABLE airings(channel TEXT, start TEXT, end TEXT, title TEXT, PRIMARY KEY(channel, start));
        CREATE TABLE matches(title TEXT PRIMARY KEY, imdb_id TEXT, original TEXT, year TEXT, runtime INT, checked TEXT);
        """
    )
    return db


class EstadoTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "data"
        self.db = novo_db()
        self.db.executemany("INSERT INTO airings VALUES (?,?,?,?)", [
            ("AXN", "2026-10-06T21:00:00", "2026-10-06T23:00:00", 'Pinóquio, o "Filme" (2019)'),
            ("AMC", "2026-10-05T21:00:00", "2026-10-05T23:00:00", "Éden"),
        ])
        self.db.executemany("INSERT INTO matches VALUES (?,?,?,?,?,?)", [
            ("Éden", "tt1", "Eden", "2025", 129, "2026-10-05T10:00:00"),
            ("Sem Match", None, None, None, None, "2026-10-05T10:00:00"),
        ])

    def test_ida_e_volta(self):
        export_state(self.db, self.dir)
        novo = novo_db()
        import_state(novo, self.dir)
        self.assertEqual(sorted(novo.execute("SELECT * FROM airings")), sorted(self.db.execute("SELECT * FROM airings")))
        self.assertEqual(sorted(novo.execute("SELECT * FROM matches"), key=str), sorted(self.db.execute("SELECT * FROM matches"), key=str))

    def test_nulls_ficam_nulls(self):
        export_state(self.db, self.dir)
        novo = novo_db()
        import_state(novo, self.dir)
        row = novo.execute("SELECT imdb_id, original, year, runtime FROM matches WHERE title='Sem Match'").fetchone()
        self.assertEqual(row, (None, None, None, None))
        self.assertEqual(novo.execute("SELECT runtime FROM matches WHERE title='Éden'").fetchone()[0], 129)

    def test_ficheiros_ordenados_e_estaveis(self):
        export_state(self.db, self.dir)
        primeiro = (self.dir / "airings.csv").read_text(encoding="utf-8")
        export_state(self.db, self.dir)
        self.assertEqual(primeiro, (self.dir / "airings.csv").read_text(encoding="utf-8"))
        linhas = primeiro.splitlines()
        self.assertTrue(linhas[1].startswith("AMC,2026-10-05"))   # ordenado por início

    def test_import_sem_ficheiros_nao_falha(self):
        import_state(novo_db(), self.dir)

    def test_import_nao_sobrepoe_o_que_ja_existe(self):
        export_state(self.db, self.dir)
        novo = novo_db()
        novo.execute("INSERT INTO matches VALUES ('Éden', 'tt_novo', 'Eden', '2025', 129, '2026-10-06T00:00:00')")
        import_state(novo, self.dir)
        self.assertEqual(novo.execute("SELECT imdb_id FROM matches WHERE title='Éden'").fetchone()[0], "tt_novo")

    def test_import_de_csv_antigo_sem_coluna_checked(self):
        self.dir.mkdir(parents=True)
        (self.dir / "matches.csv").write_text("title,imdb_id,original,year,runtime\nÉden,tt1,Eden,2025,129\n", encoding="utf-8")
        db = novo_db()
        import_state(db, self.dir)
        self.assertEqual(db.execute("SELECT imdb_id FROM matches").fetchone()[0], "tt1")


if __name__ == "__main__":
    unittest.main()
