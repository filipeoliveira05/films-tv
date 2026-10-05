import unittest

from filmes_tv import choose, clean_title, similarity


def cand(title, original, runtime, imdb="tt1", year="2000"):
    return {"title": title, "original_title": original, "runtime": runtime,
            "imdb_id": imdb, "release_date": f"{year}-01-01"}


class SimilarityTest(unittest.TestCase):
    def test_iguais_sem_acentos_nem_maiusculas(self):
        self.assertEqual(similarity("Quero Ser uma Estrela", "Quero ser Uma Estrela"), 1.0)

    def test_prefixo_do_titulo_tv(self):
        self.assertGreaterEqual(similarity("Pretty Woman - Um Sonho de Mulher", "Pretty Woman"), 0.95)

    def test_titulos_diferentes(self):
        for tv, c in [("Inferno", "Insidious Inferno"), ("Bird", "Lady Bird"),
                      ("O Grito", "O Grito da Mocidade"), ("Índia", "The Lives of a Bengal Lancer")]:
            self.assertLess(similarity(tv, c), 0.85, (tv, c))


class ChooseTest(unittest.TestCase):
    def test_rejeita_titulo_diferente_mesmo_com_duracao_certa(self):
        self.assertIsNone(choose("Inferno", 127, [cand("Insidious Inferno", "Insidious Inferno", 97)]))
        self.assertIsNone(choose("Bird", 115, [cand("Lady Bird", "Lady Bird", 93)]))

    def test_aceita_slot_longo_por_publicidade(self):
        c = cand("Os Sonhadores", "The Dreamers", 115, "tt0328832")
        self.assertEqual(choose("Os Sonhadores", 167, [c])["imdb_id"], "tt0328832")

    def test_rejeita_filme_muito_mais_longo_que_o_slot(self):
        self.assertIsNone(choose("Duna", 90, [cand("Duna", "Dune", 155)]))

    def test_desempate_pela_duracao(self):
        novo = cand("A Guerra dos Mundos", "War of the Worlds", 91, "tt_2025", "2025")
        antigo = cand("A Guerra dos Mundos", "War of the Worlds", 116, "tt_2005", "2005")
        self.assertEqual(choose("A Guerra dos Mundos", 109, [novo, antigo])["imdb_id"], "tt_2005")

    def test_titulo_completo_ganha_ao_prefixo(self):
        curto = cand("Robin Hood", "Robin Hood", 140, "tt_2010", "2010")
        longo = cand("Robin Hood: Príncipe dos Ladrões", "Robin Hood: Prince of Thieves", 137, "tt_1991", "1991")
        r = choose("Robin Hood: Príncipe dos Ladrões", 167, [curto, longo])
        self.assertEqual(r["imdb_id"], "tt_1991")

    def test_ignora_sem_imdb_ou_sem_duracao(self):
        self.assertIsNone(choose("Duna", 150, [cand("Duna", "Dune", 155, imdb=None)]))
        self.assertIsNone(choose("Duna", 150, [cand("Duna", "Dune", 0)]))

    def test_corresponde_pelo_titulo_original(self):
        c = cand("Os Salteadores da Arca Perdida", "Raiders of the Lost Ark", 115, "tt0082971")
        self.assertEqual(choose("Raiders of the Lost Ark", 115, [c])["imdb_id"], "tt0082971")


class CleanTitleVpTest(unittest.TestCase):
    def test_remove_vp(self):
        self.assertEqual(clean_title("Madagáscar 2 (Vp)"), ("Madagáscar 2", None))
        self.assertEqual(clean_title("Planeta Willy (VP)"), ("Planeta Willy", None))


if __name__ == "__main__":
    unittest.main()
