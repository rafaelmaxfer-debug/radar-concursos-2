#!/usr/bin/env python3
"""Valida registros cadastrados e aplica critérios geográficos configurados.

Não pesquisa novos editais nem confirma automaticamente inscrições abertas.
"""
import json
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
ARQUIVO = ROOT / 'concursos.json'
CONFIG = ROOT / 'config_radar.json'
CAMPOS = ('orgao', 'cargo', 'cidade', 'regiao', 'area', 'remuneracao',
          'inscricoes', 'situacao', 'prioridade', 'fonte')
SITUACOES = {'Inscrições abertas', 'Edital publicado', 'Previsto', 'Encerrado'}


def distancia_km(lat1, lon1, lat2, lon2):
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(min(1, sqrt(a)))


def main():
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    concursos = dados.get('concursos', [])
    if not isinstance(concursos, list):
        raise ValueError('concursos deve ser uma lista')
    aceitos, pendentes, fora = [], [], 0
    for numero, item in enumerate(concursos, 1):
        if not isinstance(item, dict) or any(c not in item for c in CAMPOS):
            raise ValueError(f'Concurso {numero}: campos obrigatórios ausentes')
        url = urlparse(str(item['fonte']))
        if url.scheme != 'https' or not url.netloc:
            raise ValueError(f'Concurso {numero}: fonte HTTPS obrigatória')
        if item['situacao'] not in SITUACOES:
            raise ValueError(f'Concurso {numero}: situação inválida')
        # Abrangência estadual/federal é uma marcação explícita, não inferida do nome.
        if config['excecao_estadual_federal'] and item.get('abrangencia') in ('Estadual', 'Federal'):
            aceitos.append(item)
            continue
        if 'latitude' not in item or 'longitude' not in item:
            pendentes.append(item)
            continue
        d = distancia_km(config['latitude_referencia'], config['longitude_referencia'],
                         float(item['latitude']), float(item['longitude']))
        if d <= config['raio_km']:
            aceitos.append(item)
        else:
            fora += 1
    # Não sobrescreve concursos.json: registros sem coordenadas ou fora do raio
    # são preservados até que haja dados geográficos confiáveis.
    print(f'Configuração: {config["raio_km"]} km em linha reta de {config["referencia"]}.')
    print(f'Registros dentro do raio ou exceção: {len(aceitos)}; '
          f'sem coordenadas: {len(pendentes)}; fora do raio: {fora}.')
    print('Nenhum edital foi pesquisado ou verificado nesta execução.')
    print('Dados originais preservados. A coleta e a publicação filtrada são etapas futuras.')


if __name__ == '__main__':
    main()
