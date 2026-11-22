#!/usr/bin/env python3
"""Coleta vagas públicas sem login, sem scraping autenticado e sem candidaturas automáticas.
Fonte primária: API pública Arbeitnow. Falhas preservam vagas existentes e não derrubam Radar de Concursos.
"""
import hashlib,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'vagas.json'
QUERIES=('engenheiro civil','engenharia civil','gerente de obras','gestor de obras','planejamento de obras','construction manager','civil engineer','project manager','administrativo','controller','controladoria','financeiro','agronegocio','agropecuaria','confinamento','boitel','operations manager','administration manager','power bi')
REGIONAL=('fernandopolis','estrela d oeste','jales','votuporanga','santa fe do sul','ouroeste','sao jose do rio preto','mirassol','tanabi','cardoso','palmeira d oeste')
def norm(s):
 import unicodedata
 return re.sub(r'\s+',' ',''.join(c for c in unicodedata.normalize('NFKD',str(s or '')) if not unicodedata.combining(c)).lower())
def area(t):
 if re.search(r'engenh|civil engineer|construction|obras|edificac|revit|autocad',t):return 'engenharia'
 if re.search(r'agro|boitel|confinamento|fazenda|pecuar|livestock|feedlot',t):return 'agro'
 if re.search(r'financ|control|contab|audit|orcament|accounting',t):return 'financas'
 if re.search(r'admin|gest|gerente|manager|diretor|operations|suprimento',t):return 'gestao'
 return 'outros'
def classify(title,company,location,description,remote):
 t=norm(' '.join((title,company,location)));d=norm(description[:1200]);a=area(t)
 loc=norm(location)
 reg='regional' if any(k in loc for k in REGIONAL) else 'sp' if re.search(r'sao paulo|\bsp\b|paulista',loc) else 'remoto' if remote else 'br'
 points={'engenharia':48,'gestao':43,'agro':47,'financas':40,'outros':0}[a]
 points+=18 if re.search(r'gerente|gestor|coordenador|supervisor|manager|diretor|head',t) else 0
 points+=22 if reg=='regional' else 10 if reg=='sp' else 10 if reg=='remoto' else 0
 points+=min(12,3*sum(bool(re.search(k,d)) for k in ('power bi','excel','custo','budget','planejamento','equipe','cronograma','forecast')))
 return a,reg,min(100,points)
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'RadarInteligente3/1.0 (public-job-feed)','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=22) as r:return json.load(r)
def main():
 old=[]
 if OUT.exists():
  try:old=json.loads(OUT.read_text(encoding='utf-8')).get('vagas',[])
  except (ValueError,OSError):pass
 found=[];errors=[]
 for page in (1,2,3):
  try:
   data=fetch(f'https://www.arbeitnow.com/api/job-board-api?page={page}')
   for x in data.get('data',[]):
    title=x.get('title','');loc=x.get('location','');company=x.get('company_name','');raw=x.get('description','')
    desc=re.sub(r'<[^>]*>',' ',html.unescape(raw));desc=re.sub(r'\s+',' ',desc).strip()
    if not any(k in norm(' '.join((title,loc,desc[:250]))) for k in QUERIES):continue
    remote=bool(x.get('remote'));a,reg,score=classify(title,company,loc,desc,remote)
    # Exclui anúncios claramente fora do Brasil que não sejam remotos; remoto não implica contratação no Brasil.
    if reg=='br' and not remote and not re.search(r'brasil|brazil|br\b',norm(loc)):continue
    url=x.get('url','');uid=hashlib.sha256(str(url or title+company).encode()).hexdigest()[:18]
    published=x.get('created_at');published=datetime.fromtimestamp(published,timezone.utc).isoformat() if isinstance(published,(int,float)) else str(published or '')
    found.append({'id':uid,'titulo':title,'empresa':company,'localidade':loc,'remoto':remote,'area':a,'regiao':reg,'compatibilidade':score,'resumo':desc[:340],'url':url,'fonte':'Arbeitnow (anúncio externo)','publicado_em':published})
  except Exception as e:errors.append(f'Página {page}: {type(e).__name__}: {e}')
 if not found and old:found=old
 seen=set();unique=[]
 for j in sorted(found,key=lambda x:(-x['compatibilidade'],x['titulo'])):
  if j['id'] not in seen:unique.append(j);seen.add(j['id'])
 result={'atualizado_em':datetime.now(timezone.utc).isoformat(timespec='seconds'),'total':len(unique),'vagas':unique[:400], 'aviso':'Vagas coletadas de feed público, sem verificação de disponibilidade atual. Compatibilidade heurística. Aprovar no painel não envia candidatura. Algumas vagas remotas podem não aceitar candidatos no Brasil.','erros_coleta':errors}
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(f'Radar Empregos: {len(unique)} vagas; falhas: {len(errors)}')
if __name__=='__main__':main()
