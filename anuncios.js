/* Anúncios do Google AdSense com aviso de cookies (LGPD).
   Só faz alguma coisa quando a página tem a marca <meta name="google-adsense-account">,
   que o robô coloca quando a conta do AdSense existe. Sem ela: nada de anúncio nem aviso.
   "Aceitar" e "Recusar" têm o mesmo destaque; quem recusa usa o app normalmente, sem anúncios. */
(function () {
  const meta = document.querySelector('meta[name="google-adsense-account"]');
  const ID = meta && meta.content;
  if (!ID) return;
  const CHAVE = "oc-cookies";
  const ler = () => { try { return localStorage.getItem(CHAVE); } catch (e) { return null; } };
  const gravar = (v) => { try { v ? localStorage.setItem(CHAVE, v) : localStorage.removeItem(CHAVE); } catch (e) {} };

  document.querySelectorAll(".so-anuncios").forEach((el) => { el.hidden = false; });

  function carregar() {
    if (document.querySelector("script[data-oc-ads]")) return;
    const s = document.createElement("script");
    s.async = true;
    s.crossOrigin = "anonymous";
    s.dataset.ocAds = "1";
    s.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" + encodeURIComponent(ID);
    document.head.appendChild(s);
  }

  const css = document.createElement("style");
  css.textContent = `
  .oc-cookies{position:fixed;left:12px;right:12px;bottom:calc(84px + env(safe-area-inset-bottom));z-index:9999;max-width:520px;margin:0 auto;
    background:#fff;color:#1b2430;border-radius:16px;box-shadow:0 10px 40px rgba(8,38,82,.28);padding:16px;font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
  .oc-cookies p{margin:0 0 12px}
  .oc-cookies a{color:#0d4fa0;font-weight:600}
  .oc-cookies .oc-botoes{display:flex;gap:10px}
  .oc-cookies button{flex:1;padding:11px 8px;border-radius:10px;border:2px solid #0d4fa0;background:#fff;color:#0d4fa0;font:700 14px system-ui,sans-serif;cursor:pointer}
  .oc-cookies button:focus-visible{outline:3px solid #f5b301;outline-offset:2px}
  body.paginas .oc-cookies{bottom:calc(16px + env(safe-area-inset-bottom))}`;
  document.head.appendChild(css);

  function aviso() {
    if (document.querySelector(".oc-cookies")) return;
    const d = document.createElement("div");
    d.className = "oc-cookies";
    d.setAttribute("role", "dialog");
    d.setAttribute("aria-label", "Cookies e anúncios");
    d.innerHTML = '<p>O OndeCompro? é gratuito e se mantém com anúncios do Google, que usam cookies. ' +
      'Você aceita esses cookies? Se recusar, o app continua igual, só que sem anúncios. ' +
      '<a href="privacidade.html">Saiba mais</a></p>' +
      '<div class="oc-botoes"><button type="button" data-oc="nao">Recusar</button><button type="button" data-oc="sim">Aceitar</button></div>';
    d.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-oc]");
      if (!b) return;
      const antes = ler();
      gravar(b.dataset.oc);
      d.remove();
      if (b.dataset.oc === "sim") carregar();
      else if (antes === "sim") location.reload(); // tira os anúncios que já estavam carregados
    });
    document.body.appendChild(d);
  }

  document.addEventListener("click", (ev) => {
    const el = ev.target.closest && ev.target.closest("[data-cookies]");
    if (!el) return;
    ev.preventDefault();
    aviso();
  });

  const escolha = ler();
  if (escolha === "sim") carregar();
  else if (escolha !== "nao") aviso();
})();
