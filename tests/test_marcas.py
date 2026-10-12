import re
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import filmes_tv
from filmes_tv import init_db

NOW = datetime(2026, 10, 5, 12, 0)


def gerar(titulos, airings, now=NOW):
    db = sqlite3.connect(":memory:")
    init_db(db)
    for i, titulo in enumerate(titulos):
        db.execute("INSERT INTO matches (title, imdb_id, original, year, runtime, checked) VALUES (?,?,?,?,?,?)",
                   (titulo, f"tt{i}", titulo, "2000", 100, "x"))
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
    ("AXN", "2026-10-02T20:00:00", "2026-10-02T22:00:00", "Alfa"),
    ("AXN", "2026-10-08T20:00:00", "2026-10-08T22:00:00", "Alfa"),       # Alfa: Para gravar e A vir
    ("AMC", "2026-10-08T21:00:00", "2026-10-08T23:00:00", "Beta"),
    ("SyFy", "2026-10-09T21:00:00", "2026-10-09T23:30:00", "Sem Match Nenhum"),
]


class MarcacaoDasMarcasTest(unittest.TestCase):
    def setUp(self):
        self.html = gerar(["Alfa", "Beta"], AIRINGS)
        self.filmes = self.html.count("<li class='film' ")

    def test_um_par_de_botoes_por_filme_escondido_ate_o_script_o_mostrar(self):
        self.assertEqual(self.filmes, 3)                      # Alfa em duas secções + Beta
        self.assertEqual(self.html.count("<div class='marks' hidden>"), self.filmes)

    def test_botao_de_visto(self):
        self.assertEqual(
            self.html.count("<button type='button' class='mark seen' data-mark='visto' aria-pressed='false' "
                            "aria-label='Marcar como visto' title='Já vi'>"), self.filmes)

    def test_botao_de_guardar(self):
        self.assertEqual(
            self.html.count("<button type='button' class='mark save' data-mark='guardado' aria-pressed='false' "
                            "aria-label='Guardar para gravar' title='Guardar'>"), self.filmes)

    def test_botoes_ficam_na_coluna_do_rating_sem_mexer_no_rating(self):
        self.assertRegex(self.html, r"<div class='side'><div class='score[a-z ]*'><b>7\.0</b><small>1 mil votos</small></div><div class='marks' hidden>")

    def test_titulos_sem_correspondencia_nao_tem_botoes(self):
        self.assertEqual(self.html.count("class='mark "), 2 * self.filmes)
        self.assertIn("<li data-search='sem match nenhum'>Sem Match Nenhum</li>", self.html)

    def test_botoes_de_filtro_ao_lado_do_campo(self):
        find = re.search(r"<div class='find' hidden>.*?</nav>", self.html, re.S).group(0)
        self.assertIn("<button type='button' class='tool' id='f-guardados' aria-pressed='false' "
                      "aria-label='Mostrar só os guardados' title='Guardados'>", find)
        self.assertIn("<button type='button' class='tool' id='f-vistos' aria-pressed='false' "
                      "aria-label='Ocultar vistos' title='Ocultar vistos'>", find)
        self.assertEqual(find.count("<b class='n'>0</b>"), 2)

    def test_nota_dos_guardados_indisponiveis_escondida(self):
        self.assertEqual(self.html.count("<p class='nota' hidden></p>"), 1)
        self.assertLess(self.html.index("<p class='nota'"), self.html.index("<section id='agora'"))

    def test_icones_inline_para_olho_marcador_e_olho_riscado(self):
        for nome in ("eye", "bookmark", "eye-off"):
            self.assertIn(f"data-icon='{nome}'", self.html)

    def test_pesquisa_continua_a_ter_um_so_campo(self):
        self.assertEqual(self.html.count("type='search'"), 1)


if __name__ == "__main__":
    unittest.main()
