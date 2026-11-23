"""Integrações de fontes de emprego sem acessar rede."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import radar_empregos as radar

class TestFontes(unittest.TestCase):
    def test_jobicy_himalayas_sem_inventar_remuneracao(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def fake_fetch(url):
                if 'arbeitnow' in url: return {'data':[]}
                if 'remotive' in url: return {'jobs':[]}
                if 'remoteok' in url: return []
                if 'jobicy' in url:
                    return {'success':True,'jobs':[{
                        'jobTitle':'Construction Manager','companyName':'Teste Construtora',
                        'jobGeo':'Anywhere','jobDescription':'Construction budget management',
                        'url':'https://jobicy.com/jobs/construction-123','pubDate':'2026-11-23',
                        'salaryMin':9000,'salaryCurrency':'BRL','salaryPeriod':'monthly'}]}
                if 'himalayas' in url:
                    return {'jobs':[{
                        'title':'Operations Manager','companyName':'Teste Operacoes',
                        'locationRestrictions':[{'name':'Brazil','code':'BR'}],
                        'description':'Operations management and planning',
                        'applicationLink':'https://himalayas.app/job/operations-456',
                        'pubDate':1795442400}]}
                raise AssertionError('URL inesperada '+url)
            with patch.object(radar,'ROOT',root),patch.object(radar,'OUT',root/'vagas.json'),patch.object(radar,'fetch',side_effect=fake_fetch):
                radar.main()
                data=json.loads((root/'vagas.json').read_text(encoding='utf-8'))
            self.assertEqual(data['fontes_respondidas'],10)
            self.assertEqual(data['total'],2)
            job=next(x for x in data['vagas'] if x['fonte']=='Jobicy')
            self.assertEqual(job['salario_mensal_brl'],9000.0)
            self.assertTrue(any(x['fonte']=='Himalayas' for x in data['vagas']))

if __name__=='__main__': unittest.main()
