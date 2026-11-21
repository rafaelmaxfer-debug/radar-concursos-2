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


def Ponteiro(titulo):
    """Pontuação preliminar por aderência ao perfil."""
    import unicodedata

    def normalizar(texto):
        texto = unicodedata.normalize("NFKD", texto.casefold())
        return "".join(
            c for c in texto if not unicodedata.combining(c)
        )

    t = normalizar(titulo)
    pontuacao = 10

    # Concurso-alvo
    if "sefaz" in t and any(x in t for x in (
        "orcamento", "financas", "planejamento"
    )):
        pontuacao += 65

    # Engenharia civil
    elif any(x in t for x in (
        "engenheiro civil", "engenharia civil"
    )):
        pontuacao += 45

    # Administração, gestão e finanças
    elif any(x in t for x in (
        "administrador", "analista administrativo",
        "controlador", "auditor", "orcamento",
        "financas", "contabilidade"
    )):
        pontuacao += 30

    # Localização preferencial
    if any(x in t for x in (
        "fernandopolis", "jales", "votuporanga",
        "estrela d'oeste", "sao jose do rio preto"
    )):
        pontuacao += 20

    elif "sao paulo" in t or "sp" in t.split():
        pontuacao += 10

    # Penalização de notícias antigas
    import re
    anos = [int(a) for a in re.findall(r"\b20\d{2}\b", t)]
    if anos and max(anos) < 2026:
        pontuacao -= 60

    return max(0, min(pontuacao, 100))

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
    
for x in existente.values():
    titulo = x.get('titulo', '')
    x['pontuacao_preliminar'] = Ponteiro(titulo)
    x['prioridade_sugerida'] = classificar_prioridade(titulo)

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
