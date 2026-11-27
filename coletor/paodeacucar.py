"""Pão de Açúcar Ubatuba (loja 5792, Rua Guarani · Barra da Lagoa) — catálogo do site com os preços DA LOJA.

O site usa a mesma busca para todas as lojas; o que escolhe a loja é o storeId (2372 = Ubatuba,
o mesmo que o site manda quando o cliente escolhe "Retire na loja: Ubatuba"). Não precisa de conta.
Cada categoria vem em páginas de 21 produtos (Alimentos tem ~7.400 produtos).

Primeiro tenta direto (requests); se o site recusar, abre o Edge minimizado e busca de dentro da página.
"""
import json
import os
import time

from .comum import log, sessao

API = "https://api.vendas.gpa.digital/pa/search/category-page"
SITE = "https://www.paodeacucar.com"
FOTOS = "https://static.paodeacucar.com"
LOJA_UBATUBA = 2372
POR_PAGINA = 21
PAUSA = float(os.getenv("PAO_PAUSA", "0.35"))  # segundos entre páginas
CATEGORIAS = {
    "alimentos": "Alimentos",
    "bebidas": "Bebidas",
    "limpeza": "Limpeza",
    "descartaveis": "Descartáveis",
    "bebe-e-crianca": "Bebê",
    "perfumaria": "Higiene e Beleza",
    "bazar": "Bazar e Utilidades",
    "petshop": "Pet",
}


def _corpo(categoria, pagina):
    return {"partner": "linx", "page": pagina, "resultsPerPage": POR_PAGINA, "multiCategory": categoria,
            "sortBy": "relevance", "department": "ecom", "storeId": LOJA_UBATUBA, "customerPlus": False,
            "filters": []}


def _data(txt):
    t = (txt or "")[:10]
    return f"{t[8:10]}/{t[5:7]}/{t[:4]}" if len(t) == 10 else None


def _produto(p, categoria):
    preco = p.get("price")
    if not preco:
        return None
    preco = float(preco)
    promo, atacado, avisos = None, [], []
    pr = p.get("productPromotion") or ((p.get("productPromotions") or [None])[0]) or {}
    ate = _data(pr.get("endDate"))
    # oferta "de/por": o preço já vem com desconto e o antigo em priceFrom
    if p.get("priceType") == "O" and (p.get("priceFrom") or 0) > preco:
        promo = {"preco": preco, "tipo": "Oferta", "ate": ate, "preco_de": float(p["priceFrom"])}
    if pr and not pr.get("appExclusive") and not pr.get("paymentFormName"):
        leve, pague = pr.get("promotionQuantityBuy"), pr.get("promotionQuantityPayFor")
        n_un, pct = pr.get("promotionPercentOffOnUnity"), pr.get("promotionPercentOff")
        unit = pr.get("unitPrice")
        if leve and leve > 1 and unit and unit < preco:
            atacado.append({"qtd": int(leve), "preco": float(unit)})  # leve X pague Y: preço de cada um levando X
            avisos.append(f"Leve {leve} pague {pague}" + (f" até {ate[:5]}" if ate else ""))
        elif n_un and n_un > 1 and pct and unit and unit < preco:
            atacado.append({"qtd": int(n_un), "preco": float(unit)})  # 2ª unidade com X%: média de cada um
            avisos.append(f"{n_un}ª unidade com {pct}% de desconto" + (f" até {ate[:5]}" if ate else ""))
        elif unit and unit < preco and not promo:
            # desconto direto (ex.: "20% off"): o preço de cada um já é o com desconto
            promo = {"preco": float(unit), "tipo": "Oferta", "ate": ate, "preco_de": preco}
            preco = float(unit)
    elif pr and (pr.get("unitPrice") or 0) and pr["unitPrice"] < preco:
        # promoção só no app ou num cartão: aparece como aviso, não muda o preço
        onde = "no app do Pão de Açúcar" if pr.get("appExclusive") else f"pagando com {pr.get('paymentFormName')}"
        avisos.append(f"R$ {pr['unitPrice']:.2f} {onde}".replace(".", ","))
    img = (p.get("productImages") or [None])[0]
    return {
        "mercado": "pao",
        "id": f"pao:{p.get('id')}",
        "nome": (p.get("name") or "").strip(),
        "marca": p.get("brand") or None,
        "ean": None,
        "preco": preco,
        "atacado": atacado,
        "promo": promo,
        "categoria": categoria,
        # peso variável (frutas, carnes): o preço é da embalagem com o peso aproximado do nome
        "unidade": "kg" if p.get("variableWeight") else None,
        "url": p.get("urlDetails") or SITE,
        "foto": f"{FOTOS}{img}?im=Resize,width=300" if img else None,
        "disponivel": bool(p.get("stock", True)),
        "aviso": " · ".join(avisos) or None,
    }


BUSCAR_JS = """async (corpo) => {
  try {
    const r = await fetch(%s, { method: "POST", credentials: "omit",
      headers: { "content-type": "application/json" }, body: JSON.stringify(corpo) });
    if (!r.ok) return { erro: r.status };
    return await r.json();
  } catch (e) { return { erro: String(e) }; }
}""" % json.dumps(API)


def coletar(limite_paginas=None):
    s = sessao()
    s.headers.update({"Content-Type": "application/json", "Origin": SITE, "Referer": SITE + "/"})

    def direto(corpo):
        r = s.post(API, json=corpo, timeout=60)
        r.raise_for_status()
        return r.json()

    buscar, nav, pw = direto, None, None
    try:
        direto(_corpo("alimentos", 1))
    except Exception as e:
        # o site recusou a busca direta: busca de dentro de uma página do site no Edge minimizado
        from playwright.sync_api import sync_playwright
        log(f"Pão de Açúcar · busca direta recusada ({type(e).__name__}); abrindo o navegador minimizado")
        pw = sync_playwright().start()
        opcoes = {"headless": False, "args": ["--start-minimized"]}
        if os.name == "nt":
            opcoes["channel"] = os.getenv("NAVEGADOR", "msedge")
        nav = pw.chromium.launch(**opcoes)
        pg = nav.new_context(locale="pt-BR").new_page()
        pg.goto(SITE, wait_until="domcontentloaded", timeout=90000)
        pg.wait_for_timeout(4000)

        def pelo_site(corpo):
            j = pg.evaluate(BUSCAR_JS, corpo)
            if not j or "erro" in j:
                raise RuntimeError(f"busca pelo site falhou ({(j or {}).get('erro')})")
            return j
        buscar = pelo_site

    produtos, vistos = [], set()
    try:
        for cat, nome in CATEGORIAS.items():
            pagina, total_pag, antes = 1, 1, len(produtos)
            while pagina <= total_pag:
                j = None
                for tentativa in range(3):
                    try:
                        j = buscar(_corpo(cat, pagina))
                        break
                    except Exception as e:
                        if tentativa == 2:
                            log(f"Pão de Açúcar · {nome} página {pagina}: falhou ({type(e).__name__}); seguindo")
                        time.sleep(4 * (tentativa + 1))
                if j:
                    total_pag = j.get("totalPages") or total_pag
                    for p in j.get("products") or []:
                        item = _produto(p, nome)
                        if item and item["id"] not in vistos:
                            vistos.add(item["id"])
                            produtos.append(item)
                if limite_paginas and pagina >= limite_paginas:
                    break
                pagina += 1
                time.sleep(PAUSA)
            log(f"Pão de Açúcar · {nome}: +{len(produtos) - antes} (total {len(produtos)})")
    finally:
        if nav:
            nav.close()
        if pw:
            pw.stop()
    return produtos


def encartes():
    return []  # as ofertas já vêm no catálogo (de/por, leve X pague Y)


if __name__ == "__main__":
    ps = coletar(limite_paginas=1)
    print(f"{len(ps)} produtos de teste (1 página por categoria)")
    for p in ps[:8]:
        print(f"  R$ {p['preco']:7.2f}  {p['nome']}  {p.get('aviso') or ''}")
