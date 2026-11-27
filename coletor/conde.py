"""Conde Supermercados (Centro e Itaguá) — não tem loja online; publica as ofertas no Instagram
(@condesupermercados). Decisão do usuário: o robô entra no Instagram com a conta DELE.

- Login: uma vez só, pelo entrar_instagram.bat, que abre o Edge do robô na página de login para
  ELE digitar a senha. O robô nunca vê nem guarda a senha: só reaproveita a sessão que fica salva
  na pasta navegador_robo/ (fora do GitHub).
- Na coleta: abre o perfil do Conde no Edge (minimizado), olha os posts dos últimos dias e, dos que
  são de ofertas, guarda as fotos (site/dados/encartes_conde/), que a IA lê como encarte.
- Pouco acesso: uma vez por dia, só o perfil do Conde e os posts recentes, com pausas entre eles.
"""
import os
import random
import re
import sys
import time
from datetime import date, datetime, timedelta

from .comum import DADOS, RAIZ, SITE_DADOS, hoje, ler_json, log, salvar_json

PERFIL_IG = "condesupermercados"
PASTA_NAVEGADOR = RAIZ / "navegador_robo"        # sessão do Instagram (nunca vai para o GitHub)
PASTA_FOTOS = SITE_DADOS / "encartes_conde"       # fotos dos posts de ofertas (vão para o app)
LISTA_SALVA = DADOS / "encartes_conde.json"       # última lista boa, se um dia o Instagram falhar
DIAS = 7                                          # posts mais antigos que isso não entram
MAX_POSTS = 12                                    # o perfil mostra 12 posts na primeira tela
VALIDADE_PADRAO = 3                               # post de oferta sem data na legenda: vale 3 dias
_OFERTA = re.compile(r"ofert|promo|r\$\s*\d|pre[cç]o|v[aá]lid|imperd|desconto|quinta|sexta|s[aá]bado|"
                     r"semana|black|feira|a[cç]ougue|hortifr", re.I)


def coletar(limite_paginas=None):
    return []  # sem catálogo online: os preços vêm das fotos de ofertas


def _abrir(p, visivel=False):
    opcoes = {"headless": False, "locale": "pt-BR", "viewport": {"width": 1100, "height": 900},
              "args": [] if visivel else ["--start-minimized"]}
    if os.name == "nt":
        opcoes["channel"] = os.getenv("NAVEGADOR", "msedge")
    PASTA_NAVEGADOR.mkdir(exist_ok=True)
    return p.chromium.launch_persistent_context(str(PASTA_NAVEGADOR), **opcoes)


def _logado(ctx):
    return any(c.get("name") == "sessionid" and c.get("value") for c in ctx.cookies("https://www.instagram.com"))


def _datas_da_legenda(legenda, base):
    """Datas escritas na legenda (26.11.26, 30/11, 02/12/2026...) que não são antes do post."""
    achadas = []
    for d, m, a in re.findall(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b", legenda or ""):
        try:
            ano = int(a) + (2000 if a and len(a) == 2 else 0) if a else base.year
            dt = date(ano, int(m), int(d))
            if not a and dt < base - timedelta(days=60):
                dt = date(ano + 1, int(m), int(d))  # "05/01" num post de dezembro é do ano seguinte
        except ValueError:
            continue
        if base - timedelta(days=1) <= dt <= base + timedelta(days=45):
            achadas.append(dt)
    return achadas


def _fotos_do_post(pg):
    """Fotos do post (todas as do carrossel), na ordem, pegando a maior versão de cada."""
    vistas = []
    # só as fotos grandes do topo da página (a grade "Mais posts" fica mais abaixo e não entra)
    js = """() => {
      window.scrollTo(0, 0);
      return [...document.querySelectorAll('main img')]
        .filter(i => {
          const r = i.getBoundingClientRect();
          return i.naturalWidth >= 400 && r.width >= 300 && r.top < innerHeight * 0.9
            && /cdninstagram|fbcdn/.test(i.currentSrc || i.src);
        })
        .map(i => i.currentSrc || i.src);
    }"""
    for _ in range(12):
        for u in pg.evaluate(js):
            if u not in vistas:
                vistas.append(u)
        botao = pg.query_selector('main button[aria-label="Avançar"], main button[aria-label="Next"]')
        if not botao:
            break
        botao.click()
        pg.wait_for_timeout(900)
    return vistas


def _ler_post(pg, url):
    pg.goto(url, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_selector("main", timeout=30000)
    pg.wait_for_timeout(2000)
    quando = pg.eval_on_selector("main time[datetime]", "e => e.getAttribute('datetime')") if pg.query_selector("main time[datetime]") else None
    # a legenda na tela vem cortada ("... mais"); a versão completa (com as datas de validade) está no og:description
    meta = pg.query_selector('meta[property="og:description"]')
    og = (meta.get_attribute("content") if meta else "") or ""
    og = og.split(': "', 1)[1].rstrip('". ') if ': "' in og else og  # tira "28 curtidas, ... em 26 de novembro:"
    h1 = pg.query_selector("main h1")
    tela = h1.inner_text() if h1 else ""
    return quando, max(og, tela, key=len).strip()


def _baixar(ctx, src, caminho):
    r = ctx.request.get(src, timeout=60000)
    if not r.ok:
        raise RuntimeError(f"foto não baixou ({r.status})")
    caminho.write_bytes(r.body())


def _titulo(legenda):
    linha = next((l for l in (legenda or "").splitlines() if re.search(r"[A-Za-zÀ-ú]{3}", l)), "")
    linha = re.sub(r"[^\w\sÀ-ú$%.,/!-]", "", linha).strip()
    return (linha[:60] or "Ofertas do Instagram")


def _lista_anterior(motivo):
    """Instagram falhou hoje: usa os posts da última coleta boa que ainda valem."""
    salvo = ler_json(LISTA_SALVA, {}) or {}
    hj = date.fromisoformat(hoje())
    validos = [e for e in salvo.get("encartes") or []
               if e.get("fim") and date.fromisoformat(e["fim"]) >= hj and all(os.path.exists(a) for a in e.get("arquivos") or [])]
    log(f"Conde · {motivo}; uso {len(validos)} post(s) de ofertas da última coleta que ainda valem")
    return validos


def encartes():
    from playwright.sync_api import sync_playwright

    PASTA_FOTOS.mkdir(parents=True, exist_ok=True)
    hj = date.fromisoformat(hoje())
    saida, feitos = [], set()
    with sync_playwright() as p:
        ctx = _abrir(p)
        try:
            if not _logado(ctx):
                return _lista_anterior("o Instagram não está conectado (rode o entrar_instagram.bat)")
            pg = ctx.pages[0] if ctx.pages else ctx.new_page()
            pg.goto(f"https://www.instagram.com/{PERFIL_IG}/", wait_until="domcontentloaded", timeout=60000)
            if "/accounts/login" in pg.url or "/challenge" in pg.url:
                return _lista_anterior("o Instagram pediu para entrar de novo (rode o entrar_instagram.bat)")
            pg.wait_for_selector('main a[href*="/p/"]', timeout=45000)
            pg.wait_for_timeout(1500)
            links = pg.eval_on_selector_all(
                'main a[href*="/p/"]',
                "els => [...new Set(els.map(a => a.href.split('?')[0]))]")[:MAX_POSTS]
            antigos = 0
            for url in links:
                time.sleep(random.uniform(2.5, 5))  # sem pressa, como uma pessoa olhando
                try:
                    quando, legenda = _ler_post(pg, url)
                except Exception as e:
                    log(f"Conde · post não abriu ({url}): {e}")
                    continue
                if not quando:
                    continue
                dia = datetime.fromisoformat(quando.replace("Z", "+00:00")).date()
                if dia < hj - timedelta(days=DIAS):
                    antigos += 1
                    if antigos >= 3:
                        break  # o resto da grade é mais antigo (os primeiros podem ser posts fixados)
                    continue
                if not _OFERTA.search(legenda):
                    continue  # post que não é de ofertas (receita, aviso...)
                datas = _datas_da_legenda(legenda, dia)
                fim = max(datas) if datas else dia + timedelta(days=VALIDADE_PADRAO)
                if fim < hj:
                    continue
                codigo = re.search(r"/p/([^/]+)/", url).group(1)
                imagens, arquivos = [], []
                for n, src in enumerate(_fotos_do_post(pg), 1):
                    caminho = PASTA_FOTOS / f"conde-{codigo}-{n}.jpg"
                    try:
                        if not caminho.exists():
                            _baixar(ctx, src, caminho)
                    except Exception as e:
                        log(f"Conde · foto {n} do post {codigo} não baixou: {e}")
                        continue
                    imagens.append(f"dados/encartes_conde/{caminho.name}")
                    arquivos.append(str(caminho))
                    feitos.add(caminho.name)
                if imagens:
                    saida.append({"mercado": "conde", "titulo": _titulo(legenda),
                                  "inicio": dia.isoformat(), "fim": fim.isoformat(),
                                  "periodo": f"{dia:%d/%m} a {fim:%d/%m}", "link": url,
                                  "imagens": imagens, "arquivos": arquivos})
        except Exception as e:
            return _lista_anterior(f"o Instagram não abriu direito ({type(e).__name__}: {str(e)[:120]})")
        finally:
            ctx.close()
    for velho in PASTA_FOTOS.glob("*.jpg"):
        if velho.name not in feitos:
            velho.unlink()
    salvar_json(LISTA_SALVA, {"salvo": hoje(), "encartes": saida})
    log(f"Conde · {len(saida)} post(s) de ofertas, {sum(len(e['imagens']) for e in saida)} foto(s)")
    return saida


def entrar():
    """Abre o Edge do robô na página de login do Instagram para o usuário entrar com a conta dele."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = _abrir(p, visivel=True)
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        if _logado(ctx):
            print("O robô já está conectado ao Instagram.")
        else:
            pg.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")
            print("Entre com a sua conta na janela do Edge que abriu (o robô não vê a senha).")
            print("Pode responder às perguntas do Instagram (salvar login, código etc.). Esperando até 10 minutos...")
            for _ in range(300):
                if _logado(ctx):
                    break
                time.sleep(2)
        conectado = _logado(ctx)
        if conectado:
            pg.wait_for_timeout(3000)  # deixa o Instagram terminar de salvar a sessão
        ctx.close()
    # o teste abre o navegador de novo, por isso fica fora do bloco acima
    if conectado:
        print("Conectado! Agora vou testar abrindo o perfil do Conde...")
        r = encartes()
        print(f"Teste: {len(r)} post(s) de ofertas dos últimos {DIAS} dias, "
              f"{sum(len(e['imagens']) for e in r)} foto(s).")
        for e in r:
            print(f"  - {e['titulo']} (vale até {e['fim']}): {len(e['imagens'])} foto(s)")
    else:
        print("Não deu para conectar (o tempo acabou ou a janela foi fechada). Rode de novo quando quiser.")


if __name__ == "__main__":
    if "--entrar" in sys.argv:
        entrar()
    else:
        r = encartes()
        print(f"{len(r)} post(s) de ofertas:")
        for e in r:
            print(f"  - {e['titulo']} ({e['periodo']}): {len(e['imagens'])} foto(s) · {e['link']}")
