import unittest

from filmes_tv import clean_title, is_series


class CleanTitleTest(unittest.TestCase):
    def test_apostrofo_estranho(self):
        self.assertEqual(clean_title("Five Nights at Freddy´s"), ("Five Nights at Freddy's", None))
        self.assertEqual(clean_title("Um Amor à Beira D´Água"), ("Um Amor à Beira D'Água", None))

    def test_ano_entre_parenteses(self):
        self.assertEqual(clean_title("Pinóquio (2019)"), ("Pinóquio", "2019"))

    def test_sem_alteracoes(self):
        self.assertEqual(clean_title("Duna"), ("Duna", None))
        self.assertEqual(clean_title("2001: Odisseia no Espaço"), ("2001: Odisseia no Espaço", None))

    def test_titulo_so_numerico_nao_e_ano(self):
        self.assertEqual(clean_title("1917"), ("1917", None))


class IsSeriesTest(unittest.TestCase):
    def test_episodios(self):
        self.assertTrue(is_series("Chicago Fire T12 - Ep. 3"))
        self.assertTrue(is_series("Panda T2 - Ep. 2"))

    def test_filmes_com_palavras_parecidas(self):
        self.assertFalse(is_series("Indiana Jones E O Templo Perdido"))
        self.assertFalse(is_series("Dá Tempo ao Tempo"))


if __name__ == "__main__":
    unittest.main()
