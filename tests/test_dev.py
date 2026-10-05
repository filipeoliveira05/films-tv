import os
import time
import unittest

import dev


class DevTest(unittest.TestCase):
    def test_recarregamento_so_no_servidor_de_desenvolvimento(self):
        page = dev.inject("<html>página</html>")
        self.assertTrue(page.startswith("<html>página</html>"))
        self.assertIn("/__mtime", page)
        self.assertEqual(page.count("<script>"), 1)

    def test_mtime_muda_quando_um_ficheiro_vigiado_e_gravado(self):
        antes = dev.mtime()
        css = dev.ROOT / "estilo.css"
        original = css.stat()
        try:
            novo = time.time() + 3600   # no futuro, para ser o mais recente
            os.utime(css, (novo, novo))
            self.assertNotEqual(antes, dev.mtime())
        finally:
            os.utime(css, (original.st_atime, original.st_mtime))
        self.assertEqual(antes, dev.mtime())

    def test_a_pagina_real_nao_tem_o_aviso_de_recarregar(self):
        self.assertNotIn("/__mtime", (dev.ROOT / "pagina.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
