import sqlite3
import unittest
from datetime import datetime, timedelta

from filmes_tv import prune


def iso(days):
    return (datetime.now() + timedelta(days=days)).replace(microsecond=0).isoformat()


class PrunetTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(
            """
            CREATE TABLE airings(channel TEXT, start TEXT, end TEXT, title TEXT, PRIMARY KEY(channel, start));
            CREATE TABLE matches(title TEXT PRIMARY KEY, imdb_id TEXT, original TEXT, year TEXT, runtime INT);
            """
        )
        self.db.execute("INSERT INTO matches VALUES ('Velho', 'tt1', 'Old', '1999', 100)")

    def titulos(self):
        return {t for (t,) in self.db.execute("SELECT title FROM airings")}

    def test_apaga_so_o_que_tem_mais_de_8_dias(self):
        self.db.executemany(
            "INSERT INTO airings VALUES ('AXN', ?, ?, ?)",
            [
                (iso(-9), iso(-9 + 0.1), "Velho"),
                (iso(-7.9), iso(-7.8), "Limite"),
                (iso(-1), iso(-0.9), "Ontem"),
                (iso(3), iso(3.1), "Futuro"),
            ],
        )
        n = prune(self.db)
        self.assertEqual(n, 1)
        self.assertEqual(self.titulos(), {"Limite", "Ontem", "Futuro"})

    def test_mantem_matches(self):
        self.db.execute("INSERT INTO airings VALUES ('AXN', ?, ?, 'Velho')", (iso(-20), iso(-19.9)))
        prune(self.db)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM matches").fetchone()[0], 1)

    def test_bd_vazia(self):
        self.assertEqual(prune(self.db), 0)


if __name__ == "__main__":
    unittest.main()
