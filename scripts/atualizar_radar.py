#!/usr/bin/env python3
"""Descobre publicações de concursos; NÃO presume que inscrições estejam abertas.
As descobertas vão para candidatos.json, separado dos editais confirmados em concursos.json.
"""
import json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.utils import parsedate_to_datetime

def noticia_recente(data_publicacao, dias=90):
    """Aceita notícias publicadas nos últimos 90 dias."""
    if not data_publicacao:
        return False

    try:
        data = parsedate_to_datetime(data_publicacao)

        if data.tzinfo is None:
            data = data.replace(tzinfo=timezone.utc)

        agora = datetime.now(timezone.utc)
        limite = agora - timedelta(days=dias)

        return limite <= data <= agora

    except (TypeError, ValueError, OverflowError):
        return False

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'config_radar.json').read_text(encoding='utf-8'))
QUERIES = [
    '"concurso público" "engenheiro civil" edital Brasil',
    '"concurso público" "analista administrativo" edital',
    '"concurso público" "auditor" "controle" edital',
    '"concurso público" "orçamento" "finanças" edital',
    '"concurso público" "controlador interno" edital',
    '"concurso público" "engenharia civil" "prefeitura" edital',
    '"concurso público" "engenheiro civil" "universidade federal"',
    '"concurso público" "analista" "tribunal" edital',
    '"concurso público" "SEFAZ" "finanças" edital',
    '"concurso público" "Fernandópolis" OR "Jales" OR "Votuporanga"',
    '"concurso público" "São José do Rio Preto" OR "Santa Fé do Sul" OR "Andradina"',
    '"concurso público" "engenheiro civil" "Minas Gerais" OR "Goiás"',
    '"concurso público" "engenheiro civil" "Paraná" OR "Mato Grosso do Sul"',
    '"concurso público" "administração" "Nordeste" OR "Norte"',
    '"concurso público" "engenharia" "Sul" OR "Sudeste"',
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

def pontuar(titulo):
    """Pontuação de triagem textual, não comprova elegibilidade nem edital."""
    t = titulo.casefold()
    score = 10
    if any(x in t for x in ('engenheiro civil','engenharia civil')): score += 35
    elif any(x in t for x in ('administr','controlador','auditor','orçamento','finanças','contábil','contabil')): score += 28
    if any(x in t for x in CIDADES): score += 20
    if any(x in t for x in ('federal','nacional','tribunal','sefaz')): score += 10
    if any(x in t for x in ('inscrições abertas','abre inscrições')): score += 5  # apenas indício
    return min(score, 100)

def classificar_prioridade(titulo):
    score = pontuar(titulo)
    return 'P1' if score >= 70 else 'P2' if score >= 55 else 'P3' if score >= 40 else 'P4' if score >= 25 else 'P5'

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
                if not (any(t in low for t in AREAS) or any(t in low for t in CIDADES) or any(t in q.casefold() for t in AREAS)): continue
                import hashlib
                uid = hashlib.sha256((title + link).encode()).hexdigest()[:16]
                if uid in existing: continue
                existing[uid] = {'id':uid,'titulo':title,'url_noticia':link,
                                 'publicado_em':item.findtext('pubDate') or '',
                                 'consulta':q,'situacao':'Aguardando conferência do edital oficial',
                                 'verificado':False, 'prioridade_sugerida':classificar_prioridade(title), 'pontuacao_preliminar':pontuar(title)}
                added += 1
        except Exception as e:
            failures.append(f'{q}: {type(e).__name__}: {e}')
    for x in existing.values():
        x.setdefault('pontuacao_preliminar', pontuar(x.get('titulo','')))
        x.setdefault('prioridade_sugerida', classificar_prioridade(x.get('titulo','')))
    data = {'atualizado_em':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'referencia':CONFIG.get('referencia','Fernandópolis, SP'),
            'raio_km_configurado':CONFIG.get('raio_km',150), 'abrangencia':'Brasil', 'versao':'2.1',
            'aviso':'Descobertas não verificadas; raio geográfico ainda não validado por rotas. Não representam inscrições abertas.',
            'candidatos':sorted(existing.values(), key=lambda x: (x.get('pontuacao_preliminar', pontuar(x.get('titulo',''))), x.get('publicado_em','')), reverse=True)[:500], 'falhas':failures}
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Busca concluída: {added} novas notícias candidatas; {len(failures)} fontes com falha.')
    print('concursos.json preservado: nenhuma inscrição foi classificada como aberta sem edital oficial.')
    if failures: print('Falhas:', *failures, sep='\n - ')

if __name__ == '__main__': main()
