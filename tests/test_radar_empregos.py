"""Testes de regressao do filtro de vagas, sem acessar a internet."""
import unittest
from scripts.radar_empregos import add


class TestVagas(unittest.TestCase):
    def collect(self, title, location='Worldwide', desc='operations management'):
        items = []
        add(items, title, 'Empresa teste', location, desc, True,
            'https://example.org/vaga', 'Teste', '2026-11-23')
        return items

    def test_rejeita_segurança_nao_relacionada(self):
        self.assertEqual(self.collect('Sr. Security Operations Manager'), [])

    def test_rejeita_gerencia_generica_de_produto(self):
        self.assertEqual(self.collect('Product Manager'), [])

    def test_aceita_gerencia_de_obras(self):
        self.assertEqual(len(self.collect('Gerente de Obras', 'Fernandopolis, SP', 'gestao de obras e custos')), 1)

    def test_aceita_controladoria(self):
        self.assertEqual(len(self.collect('Controller', 'Brazil', 'controle financeiro e orçamento')), 1)

    def test_rejeita_remoto_sem_elegibilidade(self):
        self.assertEqual(self.collect('Gerente de Obras', 'United States'), [])


if __name__ == '__main__':
    unittest.main()
