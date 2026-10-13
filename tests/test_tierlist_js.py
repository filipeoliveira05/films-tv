import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "node não está instalado")
class EstadoDaTierlistTest(unittest.TestCase):
    def test_testes_do_modulo_js(self):
        r = subprocess.run(["node", "--test", "tests/js/tierlist_estado.test.js", "tests/js/tierlist_duelos.test.js"], cwd=ROOT,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
