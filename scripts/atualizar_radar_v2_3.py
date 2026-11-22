#!/usr/bin/env python3
"""Descobre publicações de concursos; NÃO presume que inscrições estejam abertas.
As descobertas vão para candidatos.json, separado dos editais confirmados em concursos.json.
"""
import json, re, hashlib, unicodedata, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.utils import parsedate_to_datetime
from html import unescape

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

CIDADES = ['fernandópolis','jales','votuporanga','estrela d’oeste','estrela d\'oeste',
           'santa fé do sul','são josé do rio preto','andradina','mirassol','tanabi',
           'general salgado','auriflama','ilha solteira','nhandeara','cardoso']
AREAS = ['engenheir', 'administr', 'gestão', 'orcament', 'orçament', 'finanç', 'contabil', 'auditor', 'controlador']

def fetch_rss(query):
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

def chave_noticia(titulo):
    """Agrupa manchetes equivalentes mesmo com links RSS diferentes."""
    titulo = unescape(re.sub(r'<[^>]+>', '', titulo)).casefold()
    titulo = unicodedata.normalize('NFKD', titulo)
    titulo = ''.join(c for c in titulo if not unicodedata.combining(c))
    titulo = re.sub(r'\s+-\s+[^-]+$', '', titulo)  # sufixo do veículo
    return re.sub(r'[^a-z0-9]+', ' ', titulo).strip()


def data_valida(item, dias=90):
    """Notícia recente; mantém a data de publicação original."""
    return noticia_recente(item.get('publicado_em', ''), dias=dias)


def tipo_indicio(titulo):
    t = titulo.casefold()
    if any(x in t for x in ('inscrições abertas', 'abre inscrições', 'inscrições começam')):
        return 'Notícia menciona inscrições (não verificadas)'
    if 'edital' in t:
        return 'Notícia menciona edital (não verificado)'
    return 'Notícia em análise'


def main():
    path = ROOT / 'candidatos.json'
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'candidatos': []}
    existing = {x['id']: x for x in old.get('candidatos', []) if x.get('id') and data_valida(x)}
    old_ids = set(existing)
    seen_titles = {chave_noticia(x.get('titulo', '')) for x in existing.values()}
    failures = []
    added = 0
    for q in QUERIES:
        try:
            root = fetch_rss(q)
            for item in root.findall('.//item'):
                title = unescape(re.sub(r'<[^>]+>', '', item.findtext('title') or '')).strip()
                link  = (item.findtext('link') or '').strip()
                if not title or not link: continue

                # Ignorar notícias com mais de 90 dias
                data_publicacao = item.findtext('pubDate') or ''
                if not noticia_recente(data_publicacao):
                    continue
                low = title.casefold()
                if not any(t in low for t in ['concurso','edital','processo seletivo']): continue
                if not (any(t in low for t in AREAS) or any(t in low for t in CIDADES) or any(t in q.casefold() for t in AREAS)): continue
                normalized = chave_noticia(title)
                uid = hashlib.sha256(normalized.encode()).hexdigest()[:16]
                if uid in existing or normalized in seen_titles: continue
                seen_titles.add(normalized)
                existing[uid] = {'id':uid,'titulo':title,'url_noticia':link,
                                 'publicado_em':item.findtext('pubDate') or '',
                                 'consulta':q,'situacao':'Aguardando conferência do edital oficial',
                                 'verificado':False, 'tipo_indicio':tipo_indicio(title), 'prioridade_sugerida':classificar_prioridade(title), 'pontuacao_preliminar':pontuar(title), 'novo_na_coleta':True}
                added += 1
        except Exception as e:
            failures.append(f'{q}: {type(e).__name__}: {e}')
    for x in existing.values():
        x['novo_na_coleta'] = x.get('id') not in old_ids
        x['pontuacao_preliminar'] = pontuar(x.get('titulo',''))
        x['tipo_indicio'] = tipo_indicio(x.get('titulo',''))
        x['prioridade_sugerida'] = classificar_prioridade(x.get('titulo',''))
    data = {'atualizado_em':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'referencia':CONFIG.get('referencia','Fernandópolis, SP'),
            'raio_km_configurado':CONFIG.get('raio_km',150), 'abrangencia':'Brasil', 'versao':'2.3',
            'aviso':'Notícias não verificadas. Inscrições abertas exigem confirmação de edital oficial e prazo; raio regional não validado por rotas.',
            'candidatos':sorted(existing.values(), key=lambda x: (x.get('pontuacao_preliminar', 0), parsedate_to_datetime(x['publicado_em']).timestamp() if x.get('publicado_em') else 0), reverse=True)[:500], 'falhas':failures, 'novas_noticias':added, 'fontes_com_falha':len(failures)}
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)
    print(f'Busca concluída: {added} novas notícias candidatas; {len(failures)} fontes com falha.')
    print('concursos.json preservado: nenhuma inscrição foi classificada como aberta sem edital oficial.')
    if failures: print('Falhas:', *failures, sep='\n - ')

if __name__ == '__main__': main()
