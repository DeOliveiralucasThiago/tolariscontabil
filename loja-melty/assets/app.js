/* Loja Melty Velas - Fase 1 (vitrine + carrinho). Sem dependências. */
(function () {
  "use strict";

  var brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* ---------- carrinho (localStorage, com fallback em memória) ---------- */
  var memoria = {};
  function lerCarrinho() {
    try { return JSON.parse(localStorage.getItem("melty_carrinho") || "{}"); }
    catch (e) { return memoria; }
  }
  function salvarCarrinho(c) {
    memoria = c;
    try { localStorage.setItem("melty_carrinho", JSON.stringify(c)); } catch (e) { /* ignora */ }
  }
  function totalItens(c) {
    return Object.keys(c).reduce(function (n, k) { return n + c[k]; }, 0);
  }

  /* ---------- dados ---------- */
  function carregar() {
    return Promise.all([
      fetch("data/config.json").then(function (r) { return r.json(); }),
      fetch("data/produtos.json").then(function (r) { return r.json(); })
    ]).then(function (v) { return { config: v[0], produtos: v[1] }; });
  }

  /* ---------- layout comum ---------- */
  function montarLayout(config) {
    var cart = totalItens(lerCarrinho());
    document.getElementById("topo").innerHTML =
      '<div class="wrap">' +
      '<a class="logo" href="index.html">' + esc(config.loja) + "</a>" +
      "<nav>" +
      '<a href="index.html">Velas</a>' +
      '<a href="prazos.html">Prazos e Envio</a>' +
      '<a class="cart-link" href="carrinho.html">Carrinho <span class="badge" id="badge">' + cart + "</span></a>" +
      "</nav></div>";
    document.getElementById("rodape").innerHTML =
      '<div class="wrap"><p><strong>' + esc(config.loja) + "</strong> · " + esc(config.slogan) + "</p>" +
      '<p><a href="prazos.html">Prazos e Envio</a>' +
      '<a href="https://instagram.com/' + esc(config.instagram) + '" rel="noopener">Instagram</a>' +
      '<a href="https://wa.me/' + esc(config.whatsapp) + '" rel="noopener">WhatsApp</a>' +
      '<a href="mailto:' + esc(config.email) + '">' + esc(config.email) + "</a></p></div>";
  }
  function atualizarBadge() {
    var b = document.getElementById("badge");
    if (b) b.textContent = totalItens(lerCarrinho());
  }

  function avisoPrazo(config) {
    return '<div class="notice"><strong>Prazo de entrega:</strong> ' + esc(config.aviso_prazo) + "</div>";
  }

  /* ---------- páginas ---------- */
  function cardProduto(p) {
    var tag = "";
    if (p.estoque <= 0) tag = '<span class="tag">Esgotado</span>';
    else if (p.estoque === 1) tag = '<span class="tag low">Última unidade</span>';
    return '<a class="card" href="produto.html?id=' + encodeURIComponent(p.id) + '">' +
      '<div class="img"><img src="' + esc(p.imagem) + '" alt="' + esc(p.nome) + '" loading="lazy">' + tag + "</div>" +
      '<div class="info"><h3>' + esc(p.nome) + '</h3><span class="price">' + brl.format(p.preco) + "</span></div></a>";
  }

  function paginaHome(d) {
    document.getElementById("app").innerHTML =
      '<div class="wrap"><section class="hero"><h1>' + esc(d.config.loja) + "</h1><p>" + esc(d.config.slogan) + "</p></section>" +
      avisoPrazo(d.config) +
      '<div class="grid">' + d.produtos.map(cardProduto).join("") + "</div></div>";
  }

  function paginaProduto(d) {
    var id = new URLSearchParams(location.search).get("id");
    var p = d.produtos.filter(function (x) { return x.id === id; })[0];
    var app = document.getElementById("app");
    if (!p) {
      app.innerHTML = '<div class="wrap page"><h1>Produto não encontrado</h1><p><a href="index.html">Voltar para a loja</a></p></div>';
      return;
    }
    document.title = p.nome + " | " + d.config.loja;
    var esgotado = p.estoque <= 0;
    var estoqueTxt = esgotado ? "Esgotado" : (p.estoque === 1 ? "Última unidade disponível" : p.estoque + " unidades disponíveis");
    app.innerHTML =
      '<div class="wrap"><div class="product">' +
      '<div><img src="' + esc(p.imagem) + '" alt="' + esc(p.nome) + '"></div>' +
      "<div><p class='muted small'><a href='index.html'>Velas</a> / " + esc(p.nome) + "</p>" +
      "<h1>" + esc(p.nome) + '</h1><div class="price">' + brl.format(p.preco) + "</div>" +
      '<p class="small ' + (esgotado ? "" : "muted") + '">' + estoqueTxt + "</p>" +
      "<p>" + esc(p.descricao) + "</p>" +
      '<div class="qty"><button id="menos" aria-label="Diminuir">−</button><span id="q">1</span><button id="mais" aria-label="Aumentar">+</button></div>' +
      '<button class="btn" id="add"' + (esgotado ? " disabled" : "") + ">" + (esgotado ? "Esgotado" : "Adicionar ao carrinho") + "</button>" +
      '<p id="msg" class="small" role="status"></p>' +
      avisoPrazo(d.config) +
      "</div></div></div>";
    var q = 1;
    var qEl = document.getElementById("q");
    document.getElementById("menos").onclick = function () { q = Math.max(1, q - 1); qEl.textContent = q; };
    document.getElementById("mais").onclick = function () { q = Math.min(Math.max(p.estoque, 1), q + 1); qEl.textContent = q; };
    document.getElementById("add").onclick = function () {
      if (esgotado) return;
      var c = lerCarrinho();
      c[p.id] = Math.min(p.estoque, (c[p.id] || 0) + q);
      salvarCarrinho(c);
      atualizarBadge();
      document.getElementById("msg").innerHTML = 'Adicionado! <a href="carrinho.html">Ver carrinho</a>';
    };
  }

  function paginaCarrinho(d) {
    var app = document.getElementById("app");
    function desenhar() {
      var c = lerCarrinho();
      var linhas = [], subtotal = 0, ajustou = false;
      Object.keys(c).forEach(function (id) {
        var p = d.produtos.filter(function (x) { return x.id === id; })[0];
        if (!p || p.estoque <= 0) { delete c[id]; ajustou = true; return; }
        if (c[id] > p.estoque) { c[id] = p.estoque; ajustou = true; }
        subtotal += p.preco * c[id];
        linhas.push({ p: p, n: c[id] });
      });
      if (ajustou) { salvarCarrinho(c); atualizarBadge(); }

      if (!linhas.length) {
        app.innerHTML = '<div class="wrap page"><h1>Seu carrinho</h1><p>O carrinho está vazio.</p><a class="btn" href="index.html">Ver velas</a></div>';
        return;
      }
      var itens = linhas.map(function (l) {
        return '<div class="cart-row"><img src="' + esc(l.p.imagem) + '" alt="">' +
          "<div><strong>" + esc(l.p.nome) + "</strong><br><span class='muted small'>" + brl.format(l.p.preco) + " cada</span>" +
          '<div class="qty"><button data-a="menos" data-id="' + esc(l.p.id) + '">−</button><span>' + l.n +
          '</span><button data-a="mais" data-id="' + esc(l.p.id) + '">+</button></div></div>' +
          '<div style="text-align:right"><div class="price">' + brl.format(l.p.preco * l.n) + "</div>" +
          '<button class="rm" data-a="rm" data-id="' + esc(l.p.id) + '">Remover</button></div></div>';
      }).join("");

      var msg = "Olá! Gostaria de fazer um pedido:%0A" + linhas.map(function (l) {
        return encodeURIComponent("• " + l.n + "x " + l.p.nome + " (" + brl.format(l.p.preco) + ")");
      }).join("%0A") + "%0A" + encodeURIComponent("Subtotal: " + brl.format(subtotal));

      app.innerHTML =
        '<div class="wrap page"><h1>Seu carrinho</h1>' + itens +
        '<div class="summary"><div class="line"><span>Subtotal</span><span>' + brl.format(subtotal) + "</span></div>" +
        '<div class="line muted"><span>Frete</span><span>calculado no fechamento (em breve)</span></div>' +
        '<div class="line total"><span>Total</span><span>' + brl.format(subtotal) + "</span></div></div>" +
        avisoPrazo(d.config) +
        '<p><a class="btn" href="https://wa.me/' + esc(d.config.whatsapp) + "?text=" + msg + '" rel="noopener">Finalizar pelo WhatsApp (provisório)</a></p>' +
        '<p class="small muted">O pagamento online e o cálculo de frete por CEP serão ativados nas próximas fases. Por enquanto o pedido é combinado pelo WhatsApp.</p></div>';

      app.querySelectorAll("button[data-a]").forEach(function (b) {
        b.onclick = function () {
          var id = b.getAttribute("data-id"), a = b.getAttribute("data-a");
          var cc = lerCarrinho();
          var p = d.produtos.filter(function (x) { return x.id === id; })[0];
          if (a === "rm") delete cc[id];
          if (a === "mais") cc[id] = Math.min(p.estoque, (cc[id] || 0) + 1);
          if (a === "menos") { cc[id] = (cc[id] || 1) - 1; if (cc[id] <= 0) delete cc[id]; }
          salvarCarrinho(cc); atualizarBadge(); desenhar();
        };
      });
    }
    desenhar();
  }

  function paginaPrazos(d) {
    document.getElementById("app").innerHTML =
      '<div class="wrap page"><h1>Prazos e Envio</h1>' + avisoPrazo(d.config) +
      "<h2>Produção</h2><p>Cada vela é preparada após a confirmação do pagamento, em até <strong>" +
      esc(d.config.prazo_producao_dias_uteis) + " dias úteis</strong>.</p>" +
      "<h2>Transporte</h2><p>O prazo de transporte é estimado conforme o seu CEP e a modalidade escolhida, contado em dias úteis a partir da postagem.</p>" +
      "<h2>Imprevistos</h2><p>Greves, feriados, clima ou áreas de difícil acesso podem afetar a entrega. Nesses casos, acompanhamos o rastreio e ajudamos você a resolver.</p>" +
      "<h2>Rastreamento</h2><p>Enviamos o código de rastreio assim que o pedido for postado.</p>" +
      "<h2>Embalagem</h2><p>As velas seguem em embalagem reforçada. Em dias muito quentes, mantenha a vela em local fresco após o recebimento.</p>" +
      '<h2>Dúvidas?</h2><p><a href="https://wa.me/' + esc(d.config.whatsapp) + '" rel="noopener">Fale com a gente pelo WhatsApp</a>.</p></div>';
  }

  /* ---------- início ---------- */
  var paginas = { home: paginaHome, produto: paginaProduto, carrinho: paginaCarrinho, prazos: paginaPrazos };
  carregar().then(function (d) {
    montarLayout(d.config);
    var tipo = document.body.getAttribute("data-page");
    (paginas[tipo] || paginaHome)(d);
  }).catch(function () {
    document.getElementById("app").innerHTML =
      '<div class="wrap page"><p>Não foi possível carregar a loja. Abra o site por um servidor (veja o README).</p></div>';
  });
})();
