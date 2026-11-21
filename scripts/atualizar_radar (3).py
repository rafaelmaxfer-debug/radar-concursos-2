#!/usr/bin/env python3
"""Valida concursos já cadastrados sem inventar editais ou estados de inscrição.

A coleta automática de fontes oficiais será acrescentada em etapa posterior.
"""
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
ARQUIVO = ROOT / 'concursos.json'
CAMPOS = ('orgao', 'cargo', 'cidade', 'regiao', 'area', 'remuneracao',
          'inscricoes', 'situacao', 'prioridade', 'fonte')
SITUACOES = {'Inscrições abertas', 'Edital publicado', 'Previsto', 'Encerrado'}


def main():
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    concursos = dados.get('concursos', [])
    if not isinstance(concursos, list):
        raise ValueError('concursos deve ser uma lista')
    for numero, item in enumerate(concursos, 1):
        if not isinstance(item, dict) or any(c not in item for c in CAMPOS):
            raise ValueError(f'Concurso {numero}: campos obrigatórios ausentes')
        url = urlparse(str(item['fonte']))
        if url.scheme != 'https' or not url.netloc:
            raise ValueError(f'Concurso {numero}: fonte HTTPS obrigatória')
        if item['situacao'] not in SITUACOES:
            raise ValueError(f'Concurso {numero}: situação inválida')
    if not concursos:
        print('Nenhum concurso validado cadastrado. Dados preservados; sem atualização fictícia.')
        return
    # A data indica somente a validação estrutural, não a conferência do edital.
    dados['validacao_estrutura_em'] = datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(timespec='seconds')
    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(concursos)} registro(s) validados estruturalmente; fontes NÃO conferidas automaticamente.')


if __name__ == '__main__':
    main()
