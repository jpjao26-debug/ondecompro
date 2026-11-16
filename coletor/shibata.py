"""Coletor do Shibata — usa um navegador de verdade (Playwright).

A loja online (loja.shibata.com.br, plataforma Vipcommerce) monta o catálogo no
navegador. O robô faz o que uma pessoa faria: escolhe "Retirar na Loja → Ubatuba",
abre cada departamento, rola a página até carregar tudo e lê nome e preço dos cartões.
"""
import os
import re
import time

from .comum import ean_valido, log, preco_br, sessao

LOJA = "https://www.loja.shibata.com.br"
LOJA_UBATUBA = "Ubatuba - Compra agendada"
ENDERECO_UBATUBA = "Oswaldo Cruz"

DEPARTAMENTOS = {
    "mercearia": "Mercearia", "bebidas": "Bebidas", "acougue": "Açougue e Peixaria",
    "frios-e-laticinios": "Frios e Laticínios", "higiene-e-limpeza": "Higiene e Beleza",
    "limpeza-2": "Limpeza", "congelados": "Congelados", "hortifruti": "Hortifrúti",
    "padaria": "Padaria", "rotisseria-1": "Rotisseria", "produtos-naturais-e-dieteticos": "Saúde e Bem-estar",
    "petshop": "Pet", "bazar": "Bazar e Utilidades", "produtos-especiais": "Especiais",
}

EXTRAIR_JS = r"""
() => [...document.querySelectorAll('.vip-card-produto')].map(c => {
  const a = c.querySelector('a[title]');
  const linhas = c.innerText.split('\n').map(s => s.trim()).filter(Boolean);
  return {nome: a ? a.getAttribute('title') : null, href: a ? a.getAttribute('href') : null,
          img: (c.querySelector('img') || {}).src || null, linhas};
})
"""

TROCAR_PAGINA_JS = """
(caminho) => {
  history.pushState({}, '', caminho);
  window.dispatchEvent(new PopStateEvent('popstate', {state: {}}));
}
"""

ROLAR_JS = r"""
() => {
  const cs = document.querySelectorAll('.vip-card-produto');
  if (cs.length) cs[cs.length - 1].scrollIntoView({block: 'end'});
  let p = document.querySelector('vip-infinite-scroll');
  while (p) {
    if (p.scrollHeight > p.clientHeight + 10 && getComputedStyle(p).overflowY !== 'visible') p.scrollTop = p.scrollHeight;
    p = p.parentElement;
  }
  window.scrollTo(0, document.body.scrollHeight);
  window.dispatchEvent(new Event('scroll'));
  return cs.length;
}
"""


def _cartao(c, categoria):
    if not c.get("nome") or not c.get("href"):
        return None
    m = re.search(r"/produto/(\d+)/", c["href"])
    if not m:
        return None
    precos = [preco_br(l) for l in c["linhas"] if l.startswith("R$")]
    precos = [p for p in precos if p]
    if not precos:
        return None
    preco = precos[0]
    preco_de = precos[1] if len(precos) > 1 and precos[1] > preco else None
    unidade = next((l for l in c["linhas"] if l.startswith("/")), None)
    return {
        "mercado": "shibata",
        "id": f"shibata:{m.group(1)}",
        "nome": c["nome"].strip(),
        "marca": None,
        "ean": None,
        "preco": preco,
        "atacado": [],
        "promo": ({"preco": preco, "tipo": "Oferta", "ate": None, "preco_de": preco_de} if preco_de else None),
        "categoria": categoria,
        "unidade": unidade,
        "url": LOJA + c["href"],
        "foto": c.get("img"),
        "disponivel": True,
    }


def _abrir_navegador(p):
    opcoes = {"headless": True, "args": ["--no-sandbox"]}
    if os.getenv("CHROME_PATH"):
        opcoes["executable_path"] = os.getenv("CHROME_PATH")
    elif os.name == "nt":
        # no Windows usa o Edge que já vem instalado (não precisa baixar outro navegador)
        opcoes["channel"] = os.getenv("NAVEGADOR", "msedge")
    if os.getenv("HTTPS_PROXY") and os.getenv("USAR_PROXY_NAVEGADOR"):
        opcoes["proxy"] = {"server": os.getenv("HTTPS_PROXY")}
    nav = p.chromium.launch(**opcoes)
    ctx = nav.new_context(locale="pt-BR", viewport={"width": 420, "height": 900},
                          ignore_https_errors=bool(os.getenv("USAR_PROXY_NAVEGADOR")))
    ctx.route("**/*", _filtrar)
    return nav, ctx


_RASTREADORES = ("google", "facebook", "doubleclick", "hotjar", "clarity", "tiktok", "criteo",
                 "onesignal", "gstatic", "fullstory", "bing.com", "newrelic", "sentry")


def _filtrar(route):
    """Não baixa fotos, fontes e rastreadores: a coleta fica bem mais rápida e leve."""
    req = route.request
    if req.resource_type in ("image", "media", "font") or any(r in req.url for r in _RASTREADORES):
        return route.abort()
    return route.continue_()


def _escolher_ubatuba(pg):
    pg.goto(LOJA + "/", wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(5000)
    for texto in ("continuar e fechar",):
        try:
            pg.get_by_text(texto, exact=False).first.click(timeout=3000)
        except Exception:
            pass
    if ENDERECO_UBATUBA in pg.inner_text("body")[:600]:
        return True
    # o cabeçalho diz "Retirar na loja:" no computador e "Retirar no endereço:" no celular
    pg.get_by_text(re.compile(r"Retirar (na loja|no endere)", re.I)).first.click(timeout=15000)
    pg.wait_for_timeout(2000)
    loja = pg.get_by_text(LOJA_UBATUBA, exact=False)
    if loja.count() == 0:
        pg.get_by_text(re.compile(r"^\s*Retirar na Loja\s*$", re.I)).first.click(timeout=15000)
        pg.wait_for_timeout(2000)
        loja = pg.get_by_text(LOJA_UBATUBA, exact=False)
    loja.first.click(timeout=15000)
    pg.wait_for_timeout(5000)
    return ENDERECO_UBATUBA in pg.inner_text("body")[:600]


def _item_api(d, categoria):
    """Converte um produto da resposta que a própria página recebe."""
    preco = float(d.get("preco") or 0)
    oferta = d.get("oferta") or None
    promo = None
    if d.get("em_oferta") and oferta and oferta.get("preco_oferta"):
        po = float(oferta["preco_oferta"])
        pa = float(oferta.get("preco_antigo") or 0) or None
        promo = {"preco": po, "tipo": oferta.get("nome") or "Oferta", "ate": None,
                 "preco_de": pa if pa and pa > po else None}
        preco = po
    if not preco:
        return None
    img = d.get("imagem")
    return {
        "mercado": "shibata",
        "id": f"shibata:{d.get('produto_id')}",
        "nome": (d.get("descricao") or "").strip(),
        "marca": None,
        "ean": ean_valido(d.get("codigo_barras")),
        "preco": preco,
        "atacado": [],
        "promo": promo,
        "categoria": categoria,
        "unidade": (d.get("unidade_sigla") or "").lower() or None,
        "url": f"{LOJA}/produto/{d.get('produto_id')}/{d.get('link') or ''}",
        "foto": f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/250x250/{img}" if img else None,
        "disponivel": bool(d.get("disponivel", True)),
    }


def coletar(limite_paginas=None):
    """Abre cada departamento página por página (?page=N, como o próprio site faz)
    e lê os produtos da resposta que a página recebe."""
    from playwright.sync_api import sync_playwright

    produtos, vistos = [], set()
    with sync_playwright() as p:
        nav, ctx = _abrir_navegador(p)
        pg = ctx.new_page()
        if not _escolher_ubatuba(pg):
            nav.close()
            raise RuntimeError("Não consegui selecionar a loja de Ubatuba no site do Shibata")
        log("Shibata · loja de Ubatuba selecionada")
        for slug, nome in DEPARTAMENTOS.items():
            pagina, total, antes = 1, 1, len(produtos)
            while pagina <= total:
                caminho = f"/departamentos/{slug}?page={pagina}"
                alvo = f"/produtos?page={pagina}&"
                j = None
                # a cada 20 páginas recarrega tudo: a lista do site vai acumulando e pesando a memória
                for jeito in (("spa", "recarregar") if pagina % 20 != 1 else ("recarregar",)):
                    try:
                        with pg.expect_response(
                            lambda r: "/centro_distribuicao/20/" in r.url and alvo in r.url, timeout=30000,
                        ) as resp:
                            if jeito == "spa":
                                # troca de página dentro do próprio site (como ao clicar), sem recarregar tudo
                                pg.evaluate(TROCAR_PAGINA_JS, caminho)
                            else:
                                pg.goto(LOJA + caminho, wait_until="commit", timeout=90000)
                        j = resp.value.json()
                        break
                    except Exception as e:
                        ultimo_erro = e.__class__.__name__
                        if jeito == "spa":
                            log(f"Shibata · {nome} página {pagina}: recarregando a página")
                if j is None:
                    log(f"Shibata · {nome} página {pagina}: falhou ({ultimo_erro}); seguindo")
                    pagina += 1
                    continue
                total = (j.get("paginator") or {}).get("total_pages") or 1
                if limite_paginas:
                    total = min(total, limite_paginas)
                for d in j.get("data") or []:
                    item = _item_api(d, nome)
                    if item and item["id"] not in vistos:
                        vistos.add(item["id"])
                        produtos.append(item)
                if pagina % 50 == 0:
                    log(f"Shibata · {nome}: página {pagina}/{total}")
                pagina += 1
                pg.wait_for_timeout(int(float(os.getenv("SHIBATA_PAUSA", "0.4")) * 1000))
            log(f"Shibata · {nome}: +{len(produtos) - antes} (total {len(produtos)})")
        nav.close()
    return produtos


def encartes():
    """Jornal de Ofertas do site institucional (Ubatuba entra no grupo 'Exceto Cruzeiro...')."""
    s = sessao()
    html = s.get("https://shibata.com.br/ofertas/", timeout=60).text
    links = re.findall(r'href="(https://shibata\.com\.br/ofertas/[^"]+/)"', html)
    saida = []
    for link in dict.fromkeys(links):
        if "exceto-cruzeiro" not in link:
            continue
        pag = s.get(link, timeout=60).text
        titulo = re.search(r'<option[^>]*selected[^>]*>([^<]+)</option>', pag)
        imgs = re.findall(r'(https://shibata\.com\.br/wp-content/uploads/[^"\s]+?campanha[^"\s]+?\.(?:jpe?g|png|webp))', pag)
        # remove versões reduzidas (-150x150, -1200x1571) e fica com o original
        originais = []
        for u in imgs:
            base = re.sub(r"-\d+x\d+(?=\.\w+$)", "", u)
            if base not in originais:
                originais.append(base)
        datas = re.search(r"(\d{1,2})\s*a\s*(\d{1,2})/(\d{1,2})", titulo.group(1) if titulo else link)
        saida.append({
            "mercado": "shibata",
            "titulo": (titulo.group(1).strip() if titulo else "Jornal de Ofertas"),
            "inicio": None, "fim": None,
            "periodo": datas.group(0) if datas else None,
            "imagens": originais,
        })
        time.sleep(1)
    return saida


if __name__ == "__main__":
    import json
    print(json.dumps(encartes(), ensure_ascii=False, indent=1))
    ps = coletar(limite_paginas=int(os.getenv("LIMITE", "2")))
    print(len(ps))
    print(json.dumps(ps[:3], ensure_ascii=False, indent=1))
