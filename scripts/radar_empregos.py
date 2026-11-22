#!/usr/bin/env python3
"""Radar 3.1: vagas de feeds públicos; não envia candidaturas nem comprova elegibilidade.
Somente vagas com indicação de Brasil ou trabalho global são exibidas.
"""
import hashlib
import html
import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'vagas.json'
KEYWORDS = ('engenheiro civil','engenharia civil','civil engineer','construction','obras',
            'project manager','gerente de projetos','gerente de obras','gestor de obras',
            'controller','controladoria','financeiro','financial manager','administrativo',
            'operations manager','agronegocio','agropecuaria','agro','feedlot','livestock',
            'power bi','business intelligence','budget','planejamento')
REGIONAL = ('fernandopolis','estrela d oeste','jales','votuporanga','santa fe do sul',
            'ouroeste','sao jose do rio preto','mirassol','tanabi','cardoso','ilha solteira',
            'general salgado','nhandeara','auriflama','andradina')
GLOBAL = ('worldwide','anywhere','global','latin america','latam','south america',
          'brazil','brasil','brazil only','br only')

def norm(value):
    return re.sub(r'\s+', ' ', ''.join(c for c in unicodedata.normalize('NFKD', str(value or ''))
              if not unicodedata.combining(c)).lower()).strip()

def clean(value):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', ' ', html.unescape(str(value or '')))).strip()

def area(text):
    if re.search(r'engenh|civil engineer|construction|\bobras\b|edificac|revit', text): return 'engenharia'
    if re.search(r'agro|boitel|confinamento|fazenda|pecuar|livestock|feedlot', text): return 'agro'
    if re.search(r'financ|control|contab|audit|orcament|accounting|budget', text): return 'financas'
    if re.search(r'admin|gest|gerente|manager|diretor|operations|suprimento|project', text): return 'gestao'
    return 'outros'

def eligibility(location, remote):
    loc = norm(location)
    if any(city in loc for city in REGIONAL): return 'regional'
    if 'brasil' in loc or 'brazil' in loc or re.search(r'\bsp\b|sao paulo', loc): return 'sp'
    if remote and any(word in loc for word in GLOBAL): return 'remoto'
    # Remote, por si só, não significa que brasileiros possam se candidatar.
    return None

def classify(title, company, location, description, remote):
    t=norm(' '.join((title,company,location))); d=norm(description[:1600]); a=area(t)
    if a=='outros': a=area(d)
    region=eligibility(location,remote)
    points={'engenharia':48,'gestao':43,'agro':47,'financas':40,'outros':0}[a]
    points+=18 if re.search(r'gerente|gestor|coordenador|supervisor|manager|diretor|head',t) else 0
    points+=22 if region=='regional' else 12 if region=='sp' else 10 if region=='remoto' else 0
    points+=min(12,3*sum(bool(re.search(k,d)) for k in ('power bi','excel','custo','budget','planejamento','equipe','cronograma','forecast')))
    return a,region,min(100,points)

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; RadarInteligente/3.1)', 'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=22) as response:
        return json.load(response)

def add(items, title, company, location, description, remote, url, source, published):
    title=clean(title); company=clean(company); location=clean(location); description=clean(description)
    if not title or not url or not str(url).startswith('https://'): return
    searchable=norm(' '.join((title,description[:700])))
    if not any(k in searchable for k in KEYWORDS): return
    a,region,score=classify(title,company,location,description,remote)
    if not region or a=='outros': return
    uid=hashlib.sha256(str(url).encode()).hexdigest()[:18]
    items.append({'id':uid,'titulo':title,'empresa':company,'localidade':location,'remoto':bool(remote),
                  'area':a,'regiao':region,'compatibilidade':score,'resumo':description[:340],
                  'url':url,'fonte':source,'publicado_em':str(published or '')})

def main():
    old=[]
    if OUT.exists():
        try: old=json.loads(OUT.read_text(encoding='utf-8')).get('vagas',[])
        except (ValueError,OSError): pass
    found=[]; errors=[]; success=0
    for page in (1,2,3):
        try:
            data=fetch(f'https://www.arbeitnow.com/api/job-board-api?page={page}')
            success+=1
            for x in data.get('data',[]):
                created=x.get('created_at')
                published=datetime.fromtimestamp(created,timezone.utc).isoformat() if isinstance(created,(int,float)) else created
                add(found,x.get('title'),x.get('company_name'),x.get('location'),x.get('description'),
                    x.get('remote'),x.get('url'),'Arbeitnow',published)
        except Exception as exc: errors.append(f'Arbeitnow página {page}: {type(exc).__name__}: {exc}')
    try:
        data=fetch('https://remotive.com/api/remote-jobs?limit=500')
        success+=1
        for x in data.get('jobs',[]):
            add(found,x.get('title'),x.get('company_name'),x.get('candidate_required_location'),
                x.get('description'),True,x.get('url'),'Remotive',x.get('publication_date'))
    except Exception as exc: errors.append(f'Remotive: {type(exc).__name__}: {exc}')
    try:
        data=fetch('https://remoteok.com/api')
        success+=1
        for x in data if isinstance(data,list) else []:
            if not isinstance(x,dict) or not x.get('position'): continue
            add(found,x.get('position'),x.get('company'),x.get('location'),x.get('description'),
                True,x.get('url'),'Remote OK',x.get('date'))
    except Exception as exc: errors.append(f'Remote OK: {type(exc).__name__}: {exc}')
    # Não reaproveitar vagas antigas quando as fontes responderam mas não encontraram vagas elegíveis.
    if success==0 and old: found=old
    unique={x['id']:x for x in found}
    jobs=sorted(unique.values(),key=lambda x:(-x['compatibilidade'],x['titulo']))[:400]
    result={'atualizado_em':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'total':len(jobs),'vagas':jobs,
            'aviso':'Vagas públicas não verificadas individualmente. Localidade e elegibilidade devem ser confirmadas no anúncio. Pontuação apenas heurística. Aprovar não envia candidatura.',
            'fontes_respondidas':success,'erros_coleta':errors}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Radar Empregos: {len(jobs)} vagas, {success} consultas bem-sucedidas, {len(errors)} falhas')

if __name__=='__main__': main()
