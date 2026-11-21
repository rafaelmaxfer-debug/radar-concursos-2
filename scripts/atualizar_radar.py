#!/usr/bin/env python3
"""Descobre publicações de concursos; NÃO presume que inscrições estejam abertas.
As descobertas vão para candidatos.json, separado dos editais confirmados em concursos.json.
"""
import json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from email.utils import parsedate_to_datetime

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'config_radar.json').read_text(encoding='utf-8'))
QUERIES = [
    '"concurso público" "engenheiro civil" São Paulo edital',
    '"concurso público" "Fernandópolis" OR "Jales" OR "Votuporanga"',
    '"concurso público" "São José do Rio Preto" OR "Santa Fé do Sul" OR "Andradina"',
    '"concurso público" "administração" OR "orçamento" "São Paulo"',
    'site:doe.sp.gov.br "concurso público" "engenharia"',
]
CIDADES = ['fernandópolis','jales','votuporanga','estrela d’oeste','estrela d\'oeste',
           'santa fé do sul','são josé do rio preto','andradina','mirassol','tanabi',
           'general salgado','auriflama','ilha solteira','nhandeara','cardoso']
AREAS = ['engenheir', 'administr', 'gestão', 'orcament', 'orçament', 'finanç', 'contabil', 'auditor', 'controlador']

def fetch_rss(query):
    url = 'https://www.google.com/search?' + urllib.parse.urlencode({'q':query,'tbm':'nws','output':'rss'})
    # Google Search RSS pode não estar disponível; usar Google News RSS como descoberta.
    url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode({'q':query,'hl':'pt-BR','gl':'BR','ceid':'BR:pt-419'})
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (compatible; RadarConcursos/2.0)'})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return ET.fromstring(resp.read(2_000_000))

def main():
    path = ROOT / 'candidatos.json'
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'candidatos': []}
    existing = {x['id']: x for x in old.get('candidatos', []) if x.get('id')}
    failures = []
    added = 0
    for q in QUERIES:
        try:
            root = fetch_rss(q)
            for item in root.findall('.//item'):
                title = re.sub(r'<[^>]+>', '', item.findtext('title') or '').strip()
                link = (item.findtext('link') or '').strip()
                if not title or not link: continue
                low = title.casefold()
                if not any(t in low for t in ['concurso','edital','processo seletivo']): continue
                if not (any(t in low for t in AREAS) or any(t in low for t in CIDADES)): continue
                import hashlib
                uid = hashlib.sha256((title + link).encode()).hexdigest()[:16]
                if uid in existing: continue
                existing[uid] = {'id':uid,'titulo':title,'url_noticia':link,
                                 'publicado_em':item.findtext('pubDate') or '',
                                 'consulta':q,'situacao':'Aguardando conferência do edital oficial',
                                 'verificado':False}
                added += 1
        except Exception as e:
            failures.append(f'{q}: {type(e).__name__}: {e}')
    data = {'atualizado_em':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'referencia':CONFIG.get('referencia','Fernandópolis, SP'),
            'raio_km_configurado':CONFIG.get('raio_km',150),
            'aviso':'Descobertas não verificadas; raio geográfico ainda não validado por rotas. Não representam inscrições abertas.',
            'candidatos':list(existing.values())[-200:], 'falhas':failures}
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Busca concluída: {added} novas notícias candidatas; {len(failures)} fontes com falha.')
    print('concursos.json preservado: nenhuma inscrição foi classificada como aberta sem edital oficial.')
    if failures: print('Falhas:', *failures, sep='\n - ')

if __name__ == '__main__': main()
