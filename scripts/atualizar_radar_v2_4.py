#!/usr/bin/env python3
"""Radar 2.4: coleta RSS, deduplicação e triagem conservadora.
Não certifica editais, inscrições, elegibilidade ou distâncias rodoviárias.
"""
import hashlib
import json
import re
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config_radar.json").read_text(encoding="utf-8"))
QUERIES = [
    '"concurso público" "engenheiro civil" edital',
    '"concurso público" "engenheiro civil" "Fernandópolis"',
    '"concurso público" "engenheiro civil" "Jales"',
    '"concurso público" "engenheiro civil" "Votuporanga"',
    '"concurso público" "analista administrativo" edital',
    '"concurso público" "contador" edital',
    '"concurso público" "gestor público" edital',
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
CIDADES = ['fernandopolis', 'jales', 'votuporanga', 'estrela d oeste',
           'santa fe do sul', 'sao jose do rio preto', 'andradina',
           'mirassol', 'tanabi', 'general salgado', 'auriflama',
           'ilha solteira', 'nhandeara', 'cardoso']
AREAS = ['engenheir', 'administr', 'gestao', 'orcament', 'financ',
         'contabil', 'contador', 'auditor', 'controlador', 'controle interno']

def normalizar(s):
    s = unicodedata.normalize('NFKD', unescape(re.sub(r'<[^>]+>', '', s or '')).casefold())
    return ''.join(c for c in s if not unicodedata.combining(c)).replace('’', "'")

def chave_noticia(titulo):
    s = re.sub(r'\s+-\s+[^-]+$', '', normalizar(titulo))
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()

def data_noticia(s):
    try:
        d = parsedate_to_datetime(s)
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError, IndexError):
        return None

def recente(s, agora):
    d = data_noticia(s)
    return bool(d and agora - timedelta(days=90) <= d <= agora)

def relevante(titulo):
    t = normalizar(titulo)
    return (any(w in t for w in ('concurso', 'edital', 'processo seletivo'))
            and (any(w in t for w in AREAS) or any(w in t for w in CIDADES)))

def pontuar(titulo):
    t = normalizar(titulo)
    score = 10
    if 'engenheiro civil' in t or 'engenharia civil' in t:
        score += 35
    elif any(w in t for w in AREAS):
        score += 28
    if any(w in t for w in CIDADES):
        score += 20
    if any(w in t for w in ('federal', 'nacional', 'tribunal', 'sefaz')):
        score += 10
    if any(w in t for w in ('inscricoes abertas', 'abre inscricoes')):
        score += 5
    return min(score, 100)

def prioridade(score):
    return 'P1' if score >= 70 else 'P2' if score >= 55 else 'P3' if score >= 40 else 'P4' if score >= 25 else 'P5'

def tipo_indicio(titulo):
    t = normalizar(titulo)
    if any(w in t for w in ('inscricoes abertas', 'abre inscricoes', 'inscricoes comecam')):
        return 'Notícia menciona inscrições (não verificadas)'
    if 'edital' in t:
        return 'Notícia menciona edital (não verificado)'
    return 'Notícia em análise'

def fetch_rss(query):
    url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode(
        {'q': query, 'hl': 'pt-BR', 'gl': 'BR', 'ceid': 'BR:pt-419'})
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (RadarConcursos/2.4)'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return ET.fromstring(response.read(2_000_000))

def main():
    path = ROOT / 'candidatos.json'
    agora = datetime.now(timezone.utc)
    try:
        old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    except (ValueError, OSError) as exc:
        raise RuntimeError('candidatos.json inválido; arquivo preservado') from exc
    if not isinstance(old, dict) or not isinstance(old.get('candidatos', []), list):
        raise RuntimeError('Formato de candidatos.json inválido; arquivo preservado')
    existing = {}
    titles = set()
    for x in old.get('candidatos', []):
        if not isinstance(x, dict) or not x.get('id') or not recente(x.get('publicado_em'), agora):
            continue
        key = chave_noticia(x.get('titulo', ''))
        if not key or key in titles:
            continue
        existing[x['id']] = x
        titles.add(key)
    old_ids = set(existing)
    failures = []
    added = 0
    successful = 0
    for q in QUERIES:
        try:
            feed = fetch_rss(q)
            successful += 1
            for item in feed.findall('.//item'):
                title = unescape(re.sub(r'<[^>]+>', '', item.findtext('title') or '')).strip()
                link = (item.findtext('link') or '').strip()
                published = item.findtext('pubDate') or ''
                if not title or not link or not recente(published, agora) or not relevante(title):
                    continue
                key = chave_noticia(title)
                if not key or key in titles:
                    continue
                uid = hashlib.sha256(key.encode()).hexdigest()[:16]
                titles.add(key)
                existing[uid] = {
                    'id': uid, 'titulo': title, 'url_noticia': link,
                    'publicado_em': published, 'consulta': q,
                    'situacao': 'Aguardando conferência do edital oficial',
                    'verificado': False, 'tipo_indicio': tipo_indicio(title),
                    'prioridade_sugerida': prioridade(pontuar(title)),
                    'pontuacao_preliminar': pontuar(title), 'novo_na_coleta': True,
                }
                added += 1
        except Exception as exc:
            failures.append(f'{q}: {type(exc).__name__}: {exc}')
    if successful == 0:
        raise RuntimeError('Nenhuma consulta RSS funcionou; dados anteriores preservados')
    for x in existing.values():
        x['novo_na_coleta'] = x['id'] not in old_ids
        x['pontuacao_preliminar'] = pontuar(x.get('titulo', ''))
        x['prioridade_sugerida'] = prioridade(x['pontuacao_preliminar'])
        x['tipo_indicio'] = tipo_indicio(x.get('titulo', ''))
    records = sorted(existing.values(), key=lambda x: (
        x.get('pontuacao_preliminar', 0),
        data_noticia(x.get('publicado_em')).timestamp() if data_noticia(x.get('publicado_em')) else 0
    ), reverse=True)[:500]
    data = {
        'atualizado_em': agora.isoformat(timespec='seconds'),
        'referencia': CONFIG.get('referencia', 'Fernandópolis, SP'),
        'raio_km_configurado': CONFIG.get('raio_km', 150),
        'abrangencia': 'Brasil', 'versao': '2.4',
        'aviso': 'Notícias não verificadas. Inscrições abertas exigem edital oficial e prazo; raio regional não validado por rotas.',
        'candidatos': records, 'falhas': failures,
        'novas_noticias': added, 'fontes_com_falha': len(failures),
    }
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)
    print(f'Busca concluída: {added} novas notícias; {len(failures)} consultas com falha.')
    print('concursos.json preservado: nenhuma inscrição classificada como aberta sem edital oficial.')
    if failures:
        print('Falhas:', *failures, sep='\n - ')

if __name__ == '__main__':
    main()
