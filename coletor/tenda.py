"""Coletor do Tenda Atacado — usa a API pública do site (a mesma que o site usa).

A loja de Ubatuba é a filial 72 (CT57). O preço do site é único para a rede;
o estoque vem por filial, então marcamos se há estoque em Ubatuba.
"""
import os
import re
import time

from .comum import ean_valido, log, pegar_json, sessao

API = "https://api.tendaatacado.com.br/api/public/store"
FILIAL_UBATUBA = "72"
PAUSA = float(os.getenv("TENDA_PAUSA", "0.4"))  # segundos entre páginas


def _promo(p):
    for pr in p.get("promotions") or []:
        preco = pr.get("price")
        if not preco:
            continue
        ate = None
        for regra in (pr.get("restriction") or {}).get("rules") or []:
            m = re.search(r"(\d{2}/\d{2}/\d{4})", regra.get("description") or "")
            if m:
                ate = m.group(1)
        tipo = (pr.get("template") or "Promoção").capitalize()
        if tipo.upper() == "DESCONTOU":
            tipo = "Descontou (preço no app Tenda)"
        return {"preco": float(preco), "tipo": tipo, "ate": ate}
    return None


def _produto(p, depto_nome):
    seller = p.get("seller") or {}
    if isinstance(seller, dict) and seller and not seller.get("tendaMainSeller", False):
        return None  # ignora vendedores de marketplace
    preco = p.get("price")
    if not preco:
        return None
    estoque_uba = None
    for inv in p.get("inventory") or []:
        if str(inv.get("branchId")) == FILIAL_UBATUBA:
            estoque_uba = (inv.get("totalAvailable") or 0) > 0
    return {
        "mercado": "tenda",
        "id": f"tenda:{p.get('id')}",
        "nome": (p.get("name") or "").strip(),
        "marca": p.get("brand") or None,
        "ean": ean_valido(p.get("barcode")),
        "preco": float(preco),
        "atacado": [
            {"qtd": w.get("minQuantity"), "preco": float(w.get("price"))}
            for w in (p.get("wholesalePrices") or []) if w.get("price")
        ],
        "promo": _promo(p),
        "categoria": depto_nome,
        "url": (p.get("url") or "").replace("https://tendaatacado", "https://www.tendaatacado"),
        "foto": p.get("thumbnail"),
        "disponivel": estoque_uba if estoque_uba is not None else (p.get("availability") == "in_stock"),
    }


NOMES_DEPTO = {
    "bebidas": "Bebidas", "mercearia": "Mercearia", "congelados": "Congelados",
    "frios-e-laticinios": "Frios e Laticínios", "carnes-aves-e-peixes": "Açougue e Peixaria",
    "limpeza": "Limpeza", "higiene-e-perfumaria": "Higiene e Beleza", "bebe": "Bebê",
    "bomboniere": "Doces e Bomboniere", "paes-e-bolos": "Padaria", "hortifruti": "Hortifrúti",
    "bazar": "Bazar e Utilidades", "pet-shop": "Pet", "bem-estar": "Saúde e Bem-estar",
}


def coletar(limite_paginas=None):
    s = sessao()
    deptos = pegar_json(s, f"{API}/departments")
    produtos, vistos = [], set()
    for d in deptos:
        link = d.get("link")
        if link not in NOMES_DEPTO:  # pula "marca própria" (repete itens) e food service
            continue
        nome = NOMES_DEPTO[link]
        pagina, total = 1, 1
        while pagina <= total:
            # "order" é obrigatório para a paginação funcionar; por nome a ordem fica estável
            j = pegar_json(s, f"{API}/category/{d['id']}/products?page={pagina}&order=name&filters=false")
            total = j.get("total_pages") or 1
            if limite_paginas:
                total = min(total, limite_paginas)
            for p in j.get("products") or []:
                item = _produto(p, nome)
                if item and item["id"] not in vistos:
                    vistos.add(item["id"])
                    produtos.append(item)
            pagina += 1
            time.sleep(PAUSA)
        log(f"Tenda · {nome}: {len(produtos)} produtos até agora")
    return produtos


def encartes():
    """Encarte semanal (o mesmo para todas as lojas; pegamos o da loja de Ubatuba)."""
    s = sessao()
    lista, pagina = [], 1
    while pagina < 10:
        j = s.get(f"{API.replace('/store', '')}/branch/flyers?per_page=50&page={pagina}", timeout=60).json()
        dados = j.get("data") or []
        if not dados:
            break
        lista += dados
        pagina += 1
    saida = []
    for f in lista:
        if str((f.get("branch") or {}).get("id")) == FILIAL_UBATUBA:
            saida.append({
                "mercado": "tenda",
                "titulo": f.get("name") or "Ofertas da Semana",
                "inicio": f.get("startDate"),
                "fim": f.get("endDate"),
                "imagens": [pg["image"] for pg in sorted(f.get("pages") or [], key=lambda x: x.get("order", 0))],
            })
    return saida


if __name__ == "__main__":
    import json
    ps = coletar(limite_paginas=int(os.getenv("LIMITE", "1")))
    print(len(ps))
    print(json.dumps(ps[:3], ensure_ascii=False, indent=1))
    print(json.dumps(encartes(), ensure_ascii=False, indent=1)[:800])
