"""Supermercado Máximo Ubatuba (Praça 13 de Maio, Centro) — não vende online; só publica encarte em PDF.

O site lista os folhetos de cada loja num arquivo público (folhetos-ofertas.json).
O PDF é baixado e cada página vira uma imagem (site/dados/encartes/), que a IA lê
como os outros encartes e que aparece na aba Encartes do app.
"""
import re
from datetime import datetime

from .comum import SITE_DADOS, log, sessao

LISTA = "https://www.supermercadomaximo.com.br/assets/data/folhetos-ofertas.json"
LOJA = "Ubatuba"


def coletar(limite_paginas=None):
    return []  # sem catálogo online: os preços vêm do encarte


def _data(txt):
    try:
        return datetime.strptime(txt, "%d/%m/%Y").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def encartes():
    import fitz  # PyMuPDF: transforma as páginas do PDF em imagens

    s = sessao()
    lista = s.get(LISTA, timeout=60).json().get(LOJA) or []
    # as páginas viram imagens que vão junto com o app (o PDF não abre como imagem no celular)
    pasta = SITE_DADOS / "encartes"
    pasta.mkdir(parents=True, exist_ok=True)
    feitos = set()
    saida = []
    for f in lista:
        url = f.get("arquivo")
        if not url:
            continue
        nome = re.sub(r"\W+", "_", url.rsplit("/", 1)[-1].rsplit(".", 1)[0])
        r = s.get(url, timeout=120)
        r.raise_for_status()
        doc = fitz.open(stream=r.content, filetype="pdf")
        imagens, arquivos = [], []
        for n, pag in enumerate(doc, 1):
            caminho = pasta / f"{nome}-{n}.jpg"
            pag.get_pixmap(dpi=150).save(str(caminho))
            imagens.append(f"dados/encartes/{caminho.name}")
            arquivos.append(str(caminho))
            feitos.add(caminho.name)
        doc.close()
        inicio, fim = _data(f.get("dataInicio")), _data(f.get("dataFim"))
        saida.append({"mercado": "maximo", "titulo": f"Ofertas Máximo Ubatuba ({f.get('dataInicio')} a {f.get('dataFim')})",
                      "inicio": inicio, "fim": fim, "periodo": f"{f.get('dataInicio')} a {f.get('dataFim')}",
                      "imagens": imagens, "arquivos": arquivos})
    for velho in pasta.glob("*.jpg"):
        if velho.name not in feitos:
            velho.unlink()
    log(f"Máximo · {len(saida)} encarte(s), {sum(len(e['imagens']) for e in saida)} páginas")
    return saida
