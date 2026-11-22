#!/usr/bin/env python3
"""Valida registros de editais cadastrados manualmente contra campos e URLs oficiais.
Não infere inscrições abertas sem evidência explícita de conferência humana.
"""
import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'concursos.json'

def data_iso(s):
    if not isinstance(s, str) or not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None

def url_oficial(url):
    if not isinstance(url, str):
        return False
    u = urlparse(url)
    return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password

def main():
    raw = json.loads(PATH.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or not isinstance(raw.get('concursos'), list):
        raise ValueError('concursos.json deve conter objeto com lista concursos')
    hoje = date.today()
    for x in raw['concursos']:
        if not isinstance(x, dict):
            raise ValueError('Cada concurso precisa ser objeto JSON')
        inicio = data_iso(x.get('inscricoes_inicio'))
        fim = data_iso(x.get('inscricoes_fim'))
        fonte = x.get('url_edital') or x.get('link_edital') or x.get('fonte_oficial')
        conferido = x.get('edital_verificado') is True and bool(x.get('verificado_em'))
        if not (conferido and url_oficial(fonte) and inicio and fim and inicio <= fim):
            x['status_inscricao'] = 'Pendente de verificação'
        elif hoje < inicio:
            x['status_inscricao'] = 'Inscrições futuras'
        elif hoje > fim:
            x['status_inscricao'] = 'Inscrições encerradas'
        else:
            x['status_inscricao'] = 'No prazo informado — conferir retificações'
    raw['atualizado_em'] = datetime.now().astimezone().isoformat(timespec='seconds')
    tmp = PATH.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    tmp.replace(PATH)
    print(f"Verificados {len(raw['concursos'])} cadastros; nenhuma confirmação automática de edital.")

if __name__ == '__main__':
    main()
