#!/usr/bin/env python3
"""Coleta indicios publicos de vagas e contratos; nao confirma oportunidade aberta."""
import hashlib
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "oportunidades.json"
QUERIES = {
    "Empregos regionais": [
        '"vaga" "engenheiro civil" "Fernandópolis" OR "Jales" OR "Votuporanga"',
        '"contrata" "gerente de obras" "São José do Rio Preto"',
        '"vaga" "administrativo" "Fernandópolis" OR "Votuporanga"',
        '"vaga" "agronegócio" "Jales" OR "Fernandópolis"',
    ],
    "Gestão e controladoria": [
        '"vaga" "controller" "São Paulo" OR "remoto"',
        '"vaga" "gestão de obras" "São Paulo"',
    ],
    "VALORE e serviços técnicos": [
        '"licitação" "projeto de engenharia" "São Paulo"',
        '"contratação" "fiscalização de obras" "São Paulo"',
        '"credenciamento" "engenheiro civil" "São Paulo"',
        '"licitação" "consultoria" "gestão financeira" "São Paulo"',
    ],
}
def clean(s):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", " ", s or ""))).strip()

def search(query):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query + " when:30d", "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"
    })
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=18) as r:
        return ET.fromstring(r.read(1_500_000))

def main():
    old = {}
    if OUTPUT.exists():
        old = json.loads(OUTPUT.read_text(encoding="utf-8"))
    records = {}
    now = datetime.now(timezone.utc)
    for x in old.get("oportunidades", []):
        try:
            when = datetime.fromisoformat(x["publicado_em"])
            if when.tzinfo and now - timedelta(days=30) <= when <= now:
                records[x["id"]] = x
        except (ValueError, TypeError, KeyError):
            pass
    failures = []
    successful = 0
    for category, queries in QUERIES.items():
        for query in queries:
            try:
                feed = search(query)
                successful += 1
                for item in feed.findall(".//item"):
                    title = clean(item.findtext("title"))
                    link = (item.findtext("link") or "").strip()
                    raw_date = item.findtext("pubDate") or ""
                    try:
                        dt = parsedate_to_datetime(raw_date).astimezone(timezone.utc)
                    except (ValueError, TypeError, IndexError):
                        continue
                    if not title or not link.startswith("https://"):
                        continue
                    if not now - timedelta(days=30) <= dt <= now:
                        continue
                    uid = hashlib.sha256((title.casefold() + "|" + link).encode()).hexdigest()[:18]
                    records[uid] = {
                        "id": uid, "titulo": title, "categoria": category,
                        "url_noticia": link, "publicado_em": dt.isoformat(),
                        "status": "Indício não verificado — confirmar anúncio e requisitos",
                    }
            except Exception as exc:
                failures.append(f"{category}: {type(exc).__name__}: {exc}")
    if successful == 0:
        if records:
            print("Todas as fontes falharam; preservando registros recentes.")
            return
        raise RuntimeError("Nenhuma fonte respondeu; não fabricar oportunidades.")
    items = sorted(records.values(), key=lambda x: x["publicado_em"], reverse=True)[:250]
    output = {
        "atualizado_em": now.isoformat(timespec="seconds"),
        "total": len(items), "oportunidades": items,
        "aviso": "Notícias e indícios, NÃO vagas nem contratos confirmados. Verifique fonte original, prazo e requisitos. Sem candidatura automática.",
        "consultas_respondidas": successful, "falhas": failures,
    }
    temp = OUTPUT.with_suffix(".tmp")
    temp.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(OUTPUT)
    print(f"Radar de indícios: {len(items)} registros; {successful} consultas; {len(failures)} falhas.")

if __name__ == "__main__":
    main()
