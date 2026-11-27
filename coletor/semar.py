"""Coletor do Semar — loja Ubatuba II Ressaca (26), id 1723 na plataforma OSuper.

Uso pessoal, sem fins comerciais, com autorização do Semar.
O site bloqueia acessos vindos de servidores na nuvem, então este coletor roda
no PC: abre o site num navegador de verdade e pede os produtos à mesma busca
que o próprio site usa ao rolar a página (20 por vez).
"""
import json
import os
import re
import time

from .comum import DADOS, log

SITE = "https://www.semarentrega.com.br"
LOJA_SLUG = "loja-26-ubatuba-ii"
LOJA_ID = "1723"
BUSCA = f"https://sense.osuper.com.br/336/{LOJA_ID}/v2/search"
PAUSA = float(os.getenv("SEMAR_PAUSA", "0.4"))

DEPARTAMENTOS = {
    "3135639": "Mercearia", "3135626": "Açougue e Peixaria", "3135624": "Açougue e Peixaria",
    "3135627": "Hortifrúti", "3135628": "Bebidas", "3135634": "Bebidas",
    "3135632": "Higiene e Beleza", "3135637": "Limpeza", "3135638": "Frios e Laticínios",
    "3135636": "Congelados", "3135633": "Bazar e Utilidades", "3135631": "Pet",
    "3135630": "Padaria", "3135635": "Bebê", "3135629": "Especiais",
}

BUSCAR_JS = """
async ([url]) => {
  try {
    const r = await fetch(url);
    if (!r.ok) return {erro: r.status};
    return await r.json();
  } catch (e) {
    return {erro: String(e)};
  }
}
"""


def _abrir(p, janela=False):
    # janela=True abre o Edge de verdade minimizado (usado se o modo invisível for recusado pelo site)
    opcoes = {"headless": not janela}
    if janela:
        opcoes["args"] = ["--start-minimized"]
    if os.getenv("CHROME_PATH"):
        opcoes["executable_path"] = os.getenv("CHROME_PATH")
    elif os.name == "nt":
        opcoes["channel"] = os.getenv("NAVEGADOR", "msedge")
    nav = p.chromium.launch(**opcoes)
    ctx = nav.new_context(locale="pt-BR", viewport={"width": 420, "height": 900})
    return nav, ctx


def _produto(h, categoria):
    pr = h.get("pricing") or {}
    preco = pr.get("price")
    if not preco:
        return None
    promo = None
    if pr.get("promotion") and pr.get("promotionalPrice") and pr["promotionalPrice"] < preco:
        promo = {"preco": float(pr["promotionalPrice"]), "tipo": "Oferta", "ate": None, "preco_de": float(preco)}
        preco = pr["promotionalPrice"]
    q = h.get("quantity") or {}
    # preço de clube (grupo de clientes do Semar): decisão do usuário — só aviso, não muda o preço
    aviso = None
    for pp in h.get("personaPromotions") or []:
        v = pp.get("promotionPrice")
        if pp.get("active") and v and v < preco:
            ate = (pp.get("endDate") or "")[:10]
            ate = f" até {ate[8:10]}/{ate[5:7]}" if len(ate) == 10 else ""
            aviso = f"Clientes do clube Semar: R$ {v:.2f}{ate}".replace(".", ",")
            break
    return {
        "mercado": "semar",
        "id": f"semar:{h.get('id')}",
        "nome": (h.get("name") or "").strip(),
        "marca": h.get("brandName") or None,
        "ean": None,
        "preco": float(preco),
        "atacado": [],
        "promo": promo,
        "categoria": categoria,
        "unidade": (h.get("saleUnit") or "").lower() or None,
        "url": f"{SITE}/{LOJA_SLUG}/produtos/{h.get('id')}/{h.get('slug') or ''}",
        "foto": h.get("image"),
        "disponivel": (q.get("inStock") or 0) > 0 if q else True,
        "aviso": aviso,
    }


def coletar(limite_paginas=None):
    from playwright.sync_api import sync_playwright

    produtos, vistos = [], set()
    with sync_playwright() as p:
        teste = f"{BUSCA}?brands=&categories=&tags=&sortField=_score&sortOrder=desc&search=&size=1&from=0"
        for janela in (False, True):
            nav, ctx = _abrir(p, janela)
            pg = ctx.new_page()
            pg.goto(f"{SITE}/{LOJA_SLUG}", wait_until="domcontentloaded", timeout=90000)
            pg.wait_for_timeout(4000)
            r = pg.evaluate(BUSCAR_JS, [teste])
            if r and "erro" not in r:
                break
            nav.close()
            if janela:
                raise RuntimeError(f"Semar recusou a busca mesmo com o navegador aberto ({(r or {}).get('erro')})")
            log(f"Semar · busca recusada no modo invisível ({(r or {}).get('erro')}); abrindo o navegador minimizado")
        for cid, nome in DEPARTAMENTOS.items():
            inicio, antes, paginas = 0, len(produtos), 0
            while True:
                url = (f"{BUSCA}?brands=&categories=&tags=&sortField=_score&sortOrder=desc"
                       f"&search=&size=20&from={inicio}&categoryId={cid}")
                j = None
                for tentativa in range(3):
                    j = pg.evaluate(BUSCAR_JS, [url])
                    if j and "erro" not in j:
                        break
                    time.sleep(5 * (tentativa + 1))
                if not j or "erro" in j:
                    log(f"Semar · {nome}: busca falhou em {inicio} ({(j or {}).get('erro')})")
                    break
                for h in j.get("hits") or []:
                    item = _produto(h, nome)
                    if item and item["id"] not in vistos:
                        vistos.add(item["id"])
                        produtos.append(item)
                paginas += 1
                if not j.get("hasNext") or (limite_paginas and paginas >= limite_paginas):
                    break
                inicio = j.get("nextFrom") or inicio + 20
                time.sleep(PAUSA)
            log(f"Semar · {nome}: +{len(produtos) - antes} (total {len(produtos)})")
        nav.close()
    return produtos


def encartes():
    """Encartes da loja 26: lê a lista e abre cada um para pegar as páginas em tamanho grande.
    As imagens também são guardadas no PC (dados/encartes_semar/) para a IA ler."""
    from playwright.sync_api import sync_playwright

    pasta = DADOS / "encartes_semar"
    pasta.mkdir(parents=True, exist_ok=True)
    saida = []
    with sync_playwright() as p:
        # o endereço antigo (/encartes/sp/ubatuba/...) parou de funcionar; a lista agora fica em /loja-26.../encartes
        folhetos = []
        for janela in (False, True):
            nav, ctx = _abrir(p, janela)
            pg = ctx.new_page()
            pg.goto(f"{SITE}/{LOJA_SLUG}/encartes", wait_until="domcontentloaded", timeout=90000)
            pg.wait_for_timeout(5000)
            html = pg.content()
            for m in re.finditer(r'"StorefrontFlyer:(\d+)":\{"__typename":"StorefrontFlyer","id":"\d+","title":"((?:[^"\\]|\\.)*)"', html):
                folhetos.append((m.group(1), json.loads('"' + m.group(2) + '"')))
            if folhetos:
                break
            nav.close()
            if not janela:
                log("Semar · encartes não carregaram no modo invisível; abrindo o navegador minimizado")
        if not folhetos:
            log("Semar · nenhum encarte encontrado")
            return saida
        for fid, titulo in dict(folhetos).items():
            respostas = []

            def guardar(resp):
                if "/1200x0/" in resp.url:
                    respostas.append(resp)
            pg.on("response", guardar)
            pg.goto(f"{SITE}/{LOJA_SLUG}/encartes/{fid}", wait_until="domcontentloaded", timeout=90000)
            pg.wait_for_timeout(4000)
            pg.remove_listener("response", guardar)
            urls = []
            for resp in respostas:
                if resp.url in urls or not resp.ok:
                    continue
                try:
                    corpo = resp.body()
                except Exception:
                    continue
                urls.append(resp.url)
                (pasta / f"{fid}-{len(urls)}.jpg").write_bytes(corpo)
            periodo = re.search(r"\d{1,2}\s*(?:e|a)\s*\d{1,2}/\d{1,2}|\d{1,2}/\d{1,2}", titulo)
            if urls:
                saida.append({"mercado": "semar", "titulo": titulo, "inicio": None, "fim": None,
                              "periodo": periodo.group(0) if periodo else None, "imagens": urls,
                              "arquivos": [str(pasta / f"{fid}-{i + 1}.jpg") for i in range(len(urls))]})
            time.sleep(1)
        nav.close()
    return saida


if __name__ == "__main__":
    ps = coletar(limite_paginas=int(os.getenv("LIMITE", "1")))
    print(len(ps), json.dumps(ps[:2], ensure_ascii=False, indent=1))
    print(json.dumps(encartes(), ensure_ascii=False, indent=1)[:1500])
