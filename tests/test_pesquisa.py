import re
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import filmes_tv
from filmes_tv import init_db, search_key

NOW = datetime(2026, 10, 5, 12, 0)


class SearchKeyTest(unittest.TestCase):
    def test_sem_acentos_nem_maiusculas(self):
        self.assertEqual(search_key("A Múmia"), "a mumia")
        self.assertEqual(search_key("Fúria"), "furia")
        self.assertEqual(search_key("Índia"), "india")

    def test_pontuacao_vira_espaco_e_espacos_colapsam(self):
        self.assertEqual(search_key("Chip 'n Dale: Rescue Rangers"), "chip n dale rescue rangers")
        self.assertEqual(search_key("Assassin´s Creed"), "assassin s creed")
        self.assertEqual(search_key("  2001:   Odisseia  no Espaço "), "2001 odisseia no espaco")

    def test_texto_sem_letras_latinas_fica_vazio(self):
        self.assertEqual(search_key("乱"), "")
        self.assertEqual(search_key(None), "")


def gerar(matches, airings, now=NOW):
    db = sqlite3.connect(":memory:")
    init_db(db)
    for i, (titulo, original) in enumerate(matches):
        db.execute("INSERT INTO matches (title, imdb_id, original, year, runtime, checked) VALUES (?,?,?,?,?,?)",
                   (titulo, f"tt{i}", original, "2000", 100, "x"))
        db.execute("INSERT INTO ratings VALUES (?,?,?)", (f"tt{i}", 7.0, 1000))
    db.executemany("INSERT INTO airings VALUES (?,?,?,?)", airings)
    out = Path(tempfile.mkdtemp()) / "o.html"
    old = filmes_tv.OUT_PATH
    filmes_tv.OUT_PATH = str(out)
    try:
        filmes_tv.report(db, now=now)
    finally:
        filmes_tv.OUT_PATH = old
    return out.read_text(encoding="utf-8")


AIRINGS = [
    ("AXN", "2026-10-08T20:00:00", "2026-10-08T22:00:00", "A Múmia"),
    ("AMC", "2026-10-08T21:00:00", "2026-10-08T23:00:00", "Duna"),
    ("SyFy", "2026-10-09T21:00:00", "2026-10-09T23:30:00", "Filme Sem Match Nenhum"),
]


class MarcacaoTest(unittest.TestCase):
    def setUp(self):
        self.html = gerar([("A Múmia", "The Mummy"), ("Duna", "Duna")], AIRINGS)

    def test_filme_com_titulo_e_original_normalizados(self):
        self.assertIn("data-search='a mumia the mummy'", self.html)

    def test_original_igual_ao_titulo_nao_repete(self):
        self.assertIn("data-search='duna'", self.html)
        self.assertNotIn("data-search='duna duna'", self.html)

    def test_titulos_sem_correspondencia_tambem_pesquisaveis(self):
        self.assertIn("<li data-search='filme sem match nenhum'>Filme Sem Match Nenhum</li>", self.html)

    def test_campo_de_pesquisa_escondido_ate_o_script_o_mostrar(self):
        nav = re.search(r"<nav.*?</nav>", self.html, re.S).group(0)
        self.assertIn("<div class='find' hidden>", nav)
        self.assertIn("type='search'", nav)
        self.assertIn("placeholder='Pesquisar filme, ator'", nav)
        self.assertIn("aria-label='Pesquisar filme, ator'", nav)
        self.assertIn("autocomplete='off'", nav)
        self.assertIn("<button type='button' class='clear' aria-label='Limpar pesquisa' hidden>", nav)

    def test_so_ha_um_campo_de_pesquisa(self):
        self.assertEqual(self.html.count("type='search'"), 1)

    def test_atalhos_das_seccoes_continuam_na_barra(self):
        nav = re.search(r"<nav.*?</nav>", self.html, re.S).group(0)
        for sid in ("agora", "gravar", "vir"):
            self.assertIn(f"href='#{sid}'", nav)


if __name__ == "__main__":
    unittest.main()
