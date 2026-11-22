#!/usr/bin/env python3
"""Radar 2.6: valida cadastros oficiais e prepara fila de conferência.
Não certifica editais por notícias, URLs ou títulos isolados.
"""
import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONCURSOS = ROOT / 'concursos.json'
CANDIDATOS = ROOT / 'candidatos.json'
FILA = ROOT / 'fila_verificacao.json'

def data_iso(s):
    if not isinstance(s, str) or not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None

def url_https(url):
    if not isinstance(url, str):
        return False
    try:
        u = urlparse(url)
        return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password
    except ValueError:
        return False

def ler_objeto(path, campo):
    if not path.exists():
        raise FileNotFoundError(f'Arquivo obrigatório não encontrado: {path.name}')
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or not isinstance(raw.get(campo), list):
        raise ValueError(f'{path.name} deve conter uma lista em {campo}')
    return raw

def gravar(path, raw):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)

def main():
    raw = ler_objeto(CONCURSOS, 'concursos')
    noticias = ler_objeto(CANDIDATOS, 'candidatos')
    hoje = datetime.now(timezone.utc).date()
    contagem = {}
    for x in raw['concursos']:
        if not isinstance(x, dict):
            raise ValueError('Cada concurso deve ser um objeto JSON')
        inicio = data_iso(x.get('inscricoes_inicio'))
        fim = data_iso(x.get('inscricoes_fim'))
        fonte = x.get('url_edital') or x.get('link_edital') or x.get('fonte_oficial')
        # Conferência humana deve ser registrada explicitamente; HTTPS sozinho não comprova origem oficial.
        conferido = (x.get('edital_verificado') is True
                     and bool(x.get('verificado_em'))
                     and url_https(fonte))
        if not (conferido and inicio and fim and inicio <= fim):
            status = 'Pendente de verificação'
        elif hoje < inicio:
            status = 'Inscrições futuras'
        elif hoje > fim:
            status = 'Inscrições encerradas'
        else:
            status = 'No prazo informado — conferir retificações'
        x['status_inscricao'] = status
        contagem[status] = contagem.get(status, 0) + 1

    fila = []
    for x in noticias['candidatos']:
        if not isinstance(x, dict) or not x.get('titulo'):
            continue
        fila.append({
            'id': x.get('id'), 'titulo': x['titulo'],
            'url_noticia': x.get('url_noticia'),
            'publicado_em': x.get('publicado_em'),
            'prioridade_sugerida': x.get('prioridade_sugerida', 'P5'),
            'pontuacao_preliminar': x.get('pontuacao_preliminar', 0),
            'situacao': 'Aguardando conferência de edital em fonte oficial',
            'edital_verificado': False,
        })
    fila.sort(key=lambda x: (-(x['pontuacao_preliminar'] if isinstance(x['pontuacao_preliminar'], (int, float)) else 0), str(x.get('titulo', ''))))
    agora = datetime.now(timezone.utc).isoformat(timespec='seconds')
    raw['atualizado_em'] = agora
    resultado = {'atualizado_em': agora, 'total': len(fila), 'fila': fila[:500],
                 'aviso': 'Fila de notícias para investigação. Nenhum edital é confirmado automaticamente.'}
    gravar(CONCURSOS, raw)
    gravar(FILA, resultado)
    print(f"Validados {len(raw['concursos'])} cadastros. Situações: {contagem}")
    print(f'Fila de conferência gerada: {len(resultado["fila"])} notícias; 0 editais confirmados automaticamente.')

if __name__ == '__main__':
    main()
