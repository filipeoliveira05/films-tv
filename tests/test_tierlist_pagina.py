import re
import unittest
from pathlib import Path

from test_marcas import AIRINGS, gerar

ROOT = Path(__file__).resolve().parent.parent
HTML = gerar(["Alfa", "Beta"], AIRINGS)


class EsqueletoDaTierlistTest(unittest.TestCase):
    def test_ha_duas_vistas(self):
        self.assertIn("<main class='wrap' id='main-tv'>", HTML)
        self.assertIn("<main class='wrap' id='main-tier' hidden>", HTML)

    def test_comutador_escondido_ate_o_js_o_mostrar(self):
        self.assertRegex(HTML, r"<div class='views' hidden>")
        self.assertIn("id='v-tv'", HTML)
        self.assertIn("id='v-tier'", HTML)
        self.assertIn("class='jump' aria-label='Secções' data-vista='tv'", HTML)

    def test_elementos_que_o_script_procura(self):
        for ident in ("tl-editar", "tl-exportar", "tl-importar", "tl-ficheiro", "tl-aviso", "tl-tiers", "tl-novo-tier",
                      "tl-livres", "tl-vazio", "tl-q", "tl-msg", "tl-chave", "tl-chave-input", "tl-chave-ok", "tl-resultados"):
            self.assertIn(f"id='{ident}'", HTML, ident)

    def test_scripts_embutidos_pela_ordem_certa(self):
        pos = [HTML.index(marca) for marca in ("Sortable", "const TierEstado", "window.FilmesTV", "filmes-tv:tierlist")]
        self.assertEqual(pos, sorted(pos))

    def test_scripts_nao_fecham_a_tag_por_engano(self):
        for nome in ("vendor/Sortable.min.js", "tierlist_estado.js", "tierlist.js", "pagina.js"):
            self.assertNotIn("</script", (ROOT / nome).read_text(encoding="utf-8").lower(), nome)

    def test_sem_chaves_no_html(self):
        self.assertNotRegex(HTML, r"api_key=[0-9a-f]{20,}")

    def test_o_workflow_dispara_com_os_ficheiros_novos(self):
        wf = (ROOT / ".github/workflows/atualizar.yml").read_text(encoding="utf-8")
        for ficheiro in ("tierlist.js", "tierlist_estado.js", "vendor/Sortable.min.js"):
            self.assertIn(f"- {ficheiro}", wf)
