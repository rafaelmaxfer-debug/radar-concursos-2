"""Testes de regressão da priorização do Radar de Empregos."""
import unittest
from scripts.radar_empregos import identificar_cidade, salario_mensal, pontuar_prioridade, add

class TestClassificacao(unittest.TestCase):
    def test_cidade_regional(self):
        self.assertEqual(identificar_cidade('Fernandópolis, SP')[0], 'Fernandopolis')
        self.assertEqual(identificar_cidade('Brazil'), (None, None))

    def test_salario_declarado(self):
        self.assertEqual(salario_mensal('Salário: R$ 8.500,00 por mês'), 8500.0)
        self.assertIsNone(salario_mensal('Salário a combinar'))
        self.assertIsNone(salario_mensal('Salário: R$ 120.000 por ano'))

    def test_prioriza_compatibilidade(self):
        self.assertGreater(pontuar_prioridade(90, 'Fernandópolis SP', None)[0],
                           pontuar_prioridade(35, 'Fernandópolis SP', None)[0])

    def test_vaga_gera_atributos(self):
        found=[]
        add(found, 'Gerente de Obras', 'Construtora Teste', 'Fernandópolis, SP',
            'Engenharia civil e controle de custos. Salário: R$ 9.000,00 por mês',
            False, 'https://example.org/obras', 'Teste', '2026-11-23')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['salario_mensal_brl'], 9000.0)
        self.assertEqual(found[0]['cidade_identificada'], 'Fernandopolis')
        self.assertIn(found[0]['grau_importancia'], ('Alta','Média','Baixa'))

if __name__ == '__main__': unittest.main()
