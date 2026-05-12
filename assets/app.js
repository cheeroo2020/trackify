(() => {
  "use strict";

  const RETAILER_LABELS = {
    on_au: "On AU",
    the_iconic: "The Iconic",
    foot_locker_au: "Foot Locker",
    jd_sports_au: "JD Sports",
    platypus: "Platypus",
    hype_dc: "Hype DC",
    rebel: "Rebel",
    eb_games: "EB Games",
    jb_hifi: "JB Hi-Fi",
    amazon_au: "Amazon AU",
    big_w: "Big W",
    harvey_norman: "Harvey Norman",
    the_good_guys: "The Good Guys",
  };

  const CATEGORY_LABELS = {
    sneakers: "ON",
    ps5: "PS5",
    xbox: "Xbox",
  };

  const formatAUD = new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
    maximumFractionDigits: 0,
  });
  const formatAUD2 = new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
    maximumFractionDigits: 2,
  });
  const formatDate = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" });
  };

  const state = {
    products: [],          // array of grouped products (one per product_key)
    productMap: new Map(), // product_key -> grouped product
    filter: "all",
    query: "",
    sort: "cheapest",
    compareMode: false,
    selected: new Set(),
  };

  async function safeFetch(path, fallback) {
    try {
      const r = await fetch(path, { cache: "no-cache" });
      if (!r.ok) return fallback;
      return await r.json();
    } catch {
      return fallback;
    }
  }

  function groupByProduct(listings) {
    const map = new Map();
    for (const l of listings) {
      const key = l.product_key;
      if (!map.has(key)) {
        map.set(key, {
          product_key: key,
          category: l.category,
          title: l.title || key,
          image_path: l.image_path || null,
          image_url: l.image_url || null,
          size: l.size || null,
          offers: [],
          latest_observed: l.observed_at || null,
        });
      }
      const g = map.get(key);
      if (!g.image_path && l.image_path) g.image_path = l.image_path;
      if (!g.image_url && l.image_url) g.image_url = l.image_url;
      if (!g.title && l.title) g.title = l.title;
      if (l.observed_at && (!g.latest_observed || l.observed_at > g.latest_observed)) {
        g.latest_observed = l.observed_at;
      }
      g.offers.push({
        retailer: l.retailer,
        price: typeof l.price_aud === "number" ? l.price_aud : null,
        in_stock: !!l.in_stock,
        url: l.url,
      });
    }
    for (const g of map.values()) {
      g.offers.sort((a, b) => {
        const aHas = a.price != null;
        const bHas = b.price != null;
        if (aHas !== bHas) return aHas ? -1 : 1;
        if (aHas && bHas) return a.price - b.price;
        return 0;
      });
      g.cheapest = g.offers.find((o) => o.price != null) || null;
    }
    return map;
  }

  function imgSrc(g) {
    if (g.image_path) return g.image_path;
    if (g.image_url) return g.image_url;
    return null;
  }

  function applyImage(img, imgwrap, src, alt) {
    if (src) {
      img.src = src;
      img.alt = alt;
      img.addEventListener(
        "error",
        () => {
          img.dataset.missing = "1";
          imgwrap.dataset.missing = "1";
        },
        { once: true }
      );
    } else {
      img.dataset.missing = "1";
      imgwrap.dataset.missing = "1";
      img.alt = "";
    }
  }

  function makeCard(g, tmpl) {
    const node = tmpl.content.cloneNode(true);
    const card = node.querySelector(".card");
    const imgwrap = node.querySelector(".card__imgwrap");
    const img = node.querySelector(".card__img");
    const cat = node.querySelector(".card__cat");
    const title = node.querySelector(".card__title");
    const meta = node.querySelector(".card__meta");
    const offers = node.querySelector(".offers");
    const check = node.querySelector(".card__check");

    card.dataset.key = g.product_key;
    card.dataset.category = g.category;
    if (state.selected.has(g.product_key)) card.classList.add("is-selected");

    applyImage(img, imgwrap, imgSrc(g), g.title);
    cat.textContent = CATEGORY_LABELS[g.category] || g.category;
    title.textContent = g.title;

    const metaBits = [];
    if (g.size) metaBits.push(g.size);
    metaBits.push(`${g.offers.length} retailer${g.offers.length === 1 ? "" : "s"}`);
    meta.textContent = metaBits.join(" • ");

    const cheapestPrice = g.cheapest ? g.cheapest.price : null;
    for (const o of g.offers) {
      const li = document.createElement("li");
      li.className = "offer";
      const isBest = o.price != null && o.price === cheapestPrice;
      if (isBest) li.classList.add("offer--best");
      if (!o.in_stock) li.classList.add("offer--oos");

      const a = document.createElement("a");
      a.href = o.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.addEventListener("click", (ev) => ev.stopPropagation());

      const left = document.createElement("span");
      left.className = "offer__retailer";
      left.textContent = RETAILER_LABELS[o.retailer] || o.retailer;

      const right = document.createElement("span");
      right.className = "offer__price";
      right.textContent = o.price != null ? formatAUD.format(o.price) : "—";

      a.appendChild(left);
      a.appendChild(right);
      li.appendChild(a);
      offers.appendChild(li);
    }

    // Card click → details (unless clicking the checkbox in compare mode)
    card.addEventListener("click", (ev) => {
      if (state.compareMode && ev.target.closest(".card__select")) return;
      openDetail(g.product_key);
    });
    card.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        openDetail(g.product_key);
      }
    });

    check.checked = state.selected.has(g.product_key);
    check.addEventListener("change", (ev) => {
      ev.stopPropagation();
      toggleSelected(g.product_key, check.checked);
    });
    check.addEventListener("click", (ev) => ev.stopPropagation());

    return node;
  }

  function compareValueForSort(g) {
    return g.cheapest ? g.cheapest.price : Infinity;
  }

  function sortProducts(arr) {
    const s = state.sort;
    if (s === "az") {
      arr.sort((a, b) => a.title.localeCompare(b.title));
    } else if (s === "expensive") {
      arr.sort((a, b) => {
        const av = g => g.cheapest ? g.cheapest.price : -Infinity;
        return av(b) - av(a);
      });
    } else if (s === "recent") {
      arr.sort((a, b) => (b.latest_observed || "").localeCompare(a.latest_observed || ""));
    } else {
      // cheapest (default)
      arr.sort((a, b) => compareValueForSort(a) - compareValueForSort(b));
    }
    return arr;
  }

  function render() {
    const root = document.getElementById("app");
    const empty = document.getElementById("empty");
    root.innerHTML = "";

    const q = state.query.trim().toLowerCase();
    let filtered = state.products.filter((g) => {
      if (state.filter !== "all" && g.category !== state.filter) return false;
      if (!q) return true;
      return g.title.toLowerCase().includes(q) || g.product_key.toLowerCase().includes(q);
    });

    filtered = sortProducts(filtered);

    if (filtered.length === 0) {
      empty.hidden = false;
      return;
    }
    empty.hidden = true;

    const tmpl = document.getElementById("card-template");
    const frag = document.createDocumentFragment();
    for (const g of filtered) frag.appendChild(makeCard(g, tmpl));
    root.appendChild(frag);
  }

  function renderStats() {
    const stats = document.getElementById("stats");
    if (state.products.length === 0) {
      stats.hidden = true;
      return;
    }
    stats.hidden = false;

    let retailers = new Set();
    let inStock = 0;
    let cheapestProduct = null;
    let cheapestPrice = Infinity;

    for (const g of state.products) {
      for (const o of g.offers) {
        retailers.add(o.retailer);
        if (o.in_stock) inStock += 1;
      }
      if (g.cheapest && g.cheapest.price < cheapestPrice) {
        cheapestPrice = g.cheapest.price;
        cheapestProduct = g;
      }
    }

    document.getElementById("stat-products").textContent = state.products.length;
    document.getElementById("stat-retailers").textContent = retailers.size;
    document.getElementById("stat-instock").textContent = inStock;
    document.getElementById("stat-cheapest").textContent = cheapestProduct
      ? `${formatAUD.format(cheapestPrice)} — ${cheapestProduct.title}`
      : "no in-stock prices yet";
  }

  /* ---------- Detail modal ---------- */

  async function openDetail(productKey) {
    const g = state.productMap.get(productKey);
    if (!g) return;
    const body = document.getElementById("modal-body");
    body.innerHTML = renderDetailSkeleton(g);
    showModal();
    // Load history per retailer
    const histories = await Promise.all(
      g.offers.map((o) =>
        safeFetch(productHistoryPath(g.product_key, o.retailer), null).then((h) => ({
          retailer: o.retailer,
          data: h,
        }))
      )
    );
    body.querySelector(".chart").replaceWith(renderHistoryChart(g, histories));
    body.querySelector(".kpis").replaceWith(renderKpis(g, histories));
  }

  function productHistoryPath(key, retailer) {
    const safe = key.replaceAll("/", "-");
    return `data/products/${safe}__${retailer}.json`;
  }

  function renderDetailSkeleton(g) {
    const src = imgSrc(g);
    const imgTag = src
      ? `<img src="${src}" alt="${escapeHtml(g.title)}">`
      : `<span style="color:var(--text-dim); font-size:13px;">no image</span>`;
    return `
      <div class="detail">
        <div class="detail__img">${imgTag}</div>
        <div>
          <h2 id="modal-title" class="detail__title">${escapeHtml(g.title)}</h2>
          <p class="detail__meta">${
            (g.size ? g.size + " • " : "") +
            (CATEGORY_LABELS[g.category] || g.category) +
            " • " +
            g.offers.length +
            " retailer" +
            (g.offers.length === 1 ? "" : "s")
          }</p>
          <div class="kpis"></div>
          <table class="retailer-table">
            <thead><tr><th>Retailer</th><th></th><th style="text-align:right;">Price</th></tr></thead>
            <tbody>${renderRetailerRows(g)}</tbody>
          </table>
        </div>
      </div>
      <div class="chart"><h4>Price history</h4><div class="chart__empty">Loading…</div></div>
    `;
  }

  function renderRetailerRows(g) {
    const cheapestPrice = g.cheapest ? g.cheapest.price : null;
    return g.offers
      .map((o) => {
        const cls = [];
        if (o.price != null && o.price === cheapestPrice) cls.push("is-best");
        if (!o.in_stock) cls.push("is-oos");
        const label = RETAILER_LABELS[o.retailer] || o.retailer;
        const status = o.in_stock
          ? '<span style="color:var(--good); font-size:12px;">in stock</span>'
          : '<span style="color:var(--bad); font-size:12px;">out of stock</span>';
        const priceText = o.price != null ? formatAUD2.format(o.price) : "—";
        return `<tr class="${cls.join(" ")}"><td><a href="${escapeAttr(o.url)}" target="_blank" rel="noopener">${escapeHtml(label)}</a></td><td>${status}</td><td class="num">${priceText}</td></tr>`;
      })
      .join("");
  }

  function renderKpis(g, histories) {
    let allTimeLow = Infinity;
    let allTimeLowDate = null;
    let allTimeLowRetailer = null;
    let totalPoints = 0;
    for (const { retailer, data } of histories) {
      if (!data || !Array.isArray(data.history)) continue;
      for (const p of data.history) {
        if (typeof p.price_aud === "number") {
          totalPoints += 1;
          if (p.price_aud < allTimeLow) {
            allTimeLow = p.price_aud;
            allTimeLowDate = p.observed_at;
            allTimeLowRetailer = retailer;
          }
        }
      }
    }
    const cur = g.cheapest;
    const wrap = document.createElement("div");
    wrap.className = "kpis";
    wrap.innerHTML = `
      <div class="kpi">
        <div class="kpi__label">Cheapest now</div>
        <div class="kpi__value kpi__value--good">${cur ? formatAUD2.format(cur.price) : "—"}</div>
        <div class="kpi__sub">${cur ? (RETAILER_LABELS[cur.retailer] || cur.retailer) : "no in-stock price"}</div>
      </div>
      <div class="kpi">
        <div class="kpi__label">All-time low</div>
        <div class="kpi__value">${Number.isFinite(allTimeLow) ? formatAUD2.format(allTimeLow) : "—"}</div>
        <div class="kpi__sub">${
          allTimeLowDate
            ? `${formatDate(allTimeLowDate)} • ${RETAILER_LABELS[allTimeLowRetailer] || allTimeLowRetailer}`
            : `${totalPoints} observation${totalPoints === 1 ? "" : "s"} so far`
        }</div>
      </div>
    `;
    return wrap;
  }

  function renderHistoryChart(g, histories) {
    const wrap = document.createElement("div");
    wrap.className = "chart";
    wrap.innerHTML = `<h4>Price history</h4>`;

    // Flatten: one series per retailer with at least 2 points
    const series = histories
      .map(({ retailer, data }) => {
        if (!data || !Array.isArray(data.history)) return null;
        const points = data.history.filter((p) => typeof p.price_aud === "number");
        if (points.length < 1) return null;
        return { retailer, points };
      })
      .filter(Boolean);

    if (series.length === 0) {
      const e = document.createElement("div");
      e.className = "chart__empty";
      e.textContent = "No price history yet — once weekly runs accumulate, a trend chart will appear here.";
      wrap.appendChild(e);
      return wrap;
    }

    // Build chart bounds
    const allPoints = series.flatMap((s) => s.points);
    const tMin = Math.min(...allPoints.map((p) => Date.parse(p.observed_at)));
    const tMax = Math.max(...allPoints.map((p) => Date.parse(p.observed_at)));
    const pMin = Math.min(...allPoints.map((p) => p.price_aud));
    const pMax = Math.max(...allPoints.map((p) => p.price_aud));
    const tSpan = Math.max(1, tMax - tMin);
    const pSpan = Math.max(1, pMax - pMin);

    const W = 600;
    const H = 110;
    const padX = 40;
    const padY = 12;
    const colors = ["#1f6feb", "#1a7f37", "#b54708", "#d1242f", "#7c3aed", "#0ea5e9"];

    const x = (t) => padX + ((Date.parse(t) - tMin) / tSpan) * (W - padX - 8);
    const y = (p) => H - padY - ((p - pMin) / pSpan) * (H - padY * 2);

    let svg = `<svg class="chart__svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
    // y-axis labels (pMin and pMax)
    svg += `<text x="4" y="${y(pMax) + 4}" font-size="10" fill="currentColor" opacity="0.6">$${pMax.toFixed(0)}</text>`;
    svg += `<text x="4" y="${y(pMin) + 4}" font-size="10" fill="currentColor" opacity="0.6">$${pMin.toFixed(0)}</text>`;
    series.forEach((s, i) => {
      const color = colors[i % colors.length];
      const pts = s.points
        .slice()
        .sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at));
      if (pts.length === 1) {
        const p = pts[0];
        svg += `<circle cx="${x(p.observed_at)}" cy="${y(p.price_aud)}" r="4" fill="${color}"></circle>`;
      } else {
        const path = pts
          .map((p, idx) => `${idx === 0 ? "M" : "L"} ${x(p.observed_at).toFixed(1)} ${y(p.price_aud).toFixed(1)}`)
          .join(" ");
        svg += `<path d="${path}" fill="none" stroke="${color}" stroke-width="2"></path>`;
        pts.forEach((p) => {
          svg += `<circle cx="${x(p.observed_at)}" cy="${y(p.price_aud)}" r="2.5" fill="${color}"></circle>`;
        });
      }
    });
    svg += `</svg>`;

    // Legend
    const legend = series
      .map((s, i) => {
        const c = colors[i % colors.length];
        const lbl = RETAILER_LABELS[s.retailer] || s.retailer;
        return `<span style="display:inline-flex; align-items:center; gap:6px; margin-right:14px; font-size:12px; color:var(--text-dim);"><span style="width:10px; height:10px; border-radius:2px; background:${c};"></span>${escapeHtml(lbl)}</span>`;
      })
      .join("");

    wrap.innerHTML = `<h4>Price history</h4>${svg}<div style="margin-top:6px;">${legend}</div>`;
    return wrap;
  }

  function showModal() {
    document.getElementById("modal").hidden = false;
    document.body.style.overflow = "hidden";
  }

  function hideModal() {
    document.getElementById("modal").hidden = true;
    document.body.style.overflow = "";
  }

  /* ---------- Comparison flow ---------- */

  function toggleCompareMode(on) {
    state.compareMode = on;
    document.body.classList.toggle("compare-mode", on);
    const btn = document.getElementById("compare-toggle");
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.textContent = on ? "Compare ✕" : "Compare";
    if (!on) {
      state.selected.clear();
    }
    updateCompareBar();
    render();
  }

  function toggleSelected(key, checked) {
    if (checked) state.selected.add(key);
    else state.selected.delete(key);
    document.querySelectorAll(".card").forEach((c) => {
      c.classList.toggle("is-selected", state.selected.has(c.dataset.key));
    });
    updateCompareBar();
  }

  function updateCompareBar() {
    const bar = document.getElementById("compare-bar");
    if (!state.compareMode) {
      bar.hidden = true;
      return;
    }
    bar.hidden = false;
    document.getElementById("compare-count").textContent = state.selected.size;
    document.getElementById("compare-go").disabled = state.selected.size < 2;
  }

  function openCompare() {
    if (state.selected.size < 2) return;
    const products = Array.from(state.selected)
      .map((k) => state.productMap.get(k))
      .filter(Boolean);
    const body = document.getElementById("modal-body");
    body.innerHTML = renderCompareTable(products);
    showModal();
  }

  function renderCompareTable(products) {
    const rows = [
      {
        label: "",
        render: (p) => {
          const src = imgSrc(p);
          const img = src
            ? `<img src="${src}" alt="${escapeHtml(p.title)}">`
            : `<span style="color:var(--text-dim); font-size:12px;">no image</span>`;
          return `<div class="cmp-img">${img}</div>`;
        },
      },
      { label: "Name", render: (p) => `<div class="cmp-name">${escapeHtml(p.title)}</div>` },
      { label: "Category", render: (p) => CATEGORY_LABELS[p.category] || p.category },
      { label: "Size", render: (p) => p.size || "—" },
      {
        label: "Cheapest",
        render: (p) =>
          p.cheapest
            ? `<div class="cmp-price-best">${formatAUD2.format(p.cheapest.price)}</div><div class="cmp-retailers">${RETAILER_LABELS[p.cheapest.retailer] || p.cheapest.retailer}</div>`
            : "—",
      },
      {
        label: "In stock",
        render: (p) => {
          const n = p.offers.filter((o) => o.in_stock).length;
          return `${n} of ${p.offers.length}`;
        },
      },
      {
        label: "All retailers",
        render: (p) =>
          `<div class="cmp-retailers">${p.offers
            .map((o) => {
              const label = RETAILER_LABELS[o.retailer] || o.retailer;
              const price = o.price != null ? formatAUD.format(o.price) : "—";
              return `${escapeHtml(label)}: ${price}`;
            })
            .join("<br>")}</div>`,
      },
      {
        label: "",
        render: (p) =>
          `<a href="#" data-key="${escapeAttr(p.product_key)}" class="cmp-open" style="color:var(--accent);">View details →</a>`,
      },
    ];

    const headerCells = products.map(() => "<th></th>").join("");
    const body = rows
      .map((row) => {
        const cells = products.map((p) => `<td>${row.render(p)}</td>`).join("");
        return `<tr><th class="cmp-axis">${row.label}</th>${cells}</tr>`;
      })
      .join("");

    const html = `
      <h2 style="margin: 0 0 6px;">Compare</h2>
      <p style="color:var(--text-dim); font-size:13px; margin:0 0 14px;">${products.length} products selected</p>
      <div class="cmp">
        <table class="cmp-table">
          <thead><tr><th class="cmp-axis"></th>${headerCells}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    `;
    setTimeout(() => {
      document.querySelectorAll(".cmp-open").forEach((a) => {
        a.addEventListener("click", (ev) => {
          ev.preventDefault();
          openDetail(a.dataset.key);
        });
      });
    }, 0);
    return html;
  }

  /* ---------- Setup hint when no data ---------- */

  function renderSetupHint() {
    const root = document.getElementById("app");
    root.innerHTML = `
      <div class="setup">
        <h2>No data yet</h2>
        <p>The first weekly scrape hasn't produced any listings yet. Trigger it now:</p>
        <ol>
          <li>Open <a href="https://github.com/cheeroo2020/trackify/actions/workflows/track.yml" target="_blank" rel="noopener">Actions → track</a></li>
          <li>Click <b>Run workflow</b> → <b>Run workflow</b>.</li>
          <li>Wait ~2 minutes, then refresh this page.</li>
        </ol>
        <p style="color: var(--text-dim); font-size: 12.5px;">
          The Action commits scraped prices into <code>data/latest.json</code>; this page reads that file.
        </p>
      </div>
    `;
  }

  /* ---------- Utils ---------- */

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[c]);
  }
  function escapeAttr(s) {
    return escapeHtml(s);
  }

  /* ---------- Wire up ---------- */

  function wireControls() {
    document.querySelectorAll(".filters .chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".filters .chip").forEach((b) => {
          b.classList.toggle("is-active", b === btn);
          b.setAttribute("aria-selected", b === btn ? "true" : "false");
        });
        state.filter = btn.dataset.filter;
        render();
      });
    });

    document.getElementById("search").addEventListener("input", (ev) => {
      state.query = ev.target.value;
      render();
    });

    document.getElementById("sort").addEventListener("change", (ev) => {
      state.sort = ev.target.value;
      render();
    });

    document.getElementById("compare-toggle").addEventListener("click", () => {
      toggleCompareMode(!state.compareMode);
    });

    document.getElementById("compare-go").addEventListener("click", openCompare);
    document.getElementById("compare-clear").addEventListener("click", () => {
      state.selected.clear();
      document.querySelectorAll(".card").forEach((c) => c.classList.remove("is-selected"));
      document.querySelectorAll(".card__check").forEach((c) => (c.checked = false));
      updateCompareBar();
    });

    document.querySelectorAll("[data-close]").forEach((el) => {
      el.addEventListener("click", hideModal);
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") hideModal();
    });
  }

  async function main() {
    wireControls();
    const latest = await safeFetch("data/latest.json", null);
    if (!Array.isArray(latest) || latest.length === 0) {
      renderSetupHint();
      document.getElementById("updated").textContent = "no runs yet";
      return;
    }
    state.productMap = groupByProduct(latest);
    state.products = Array.from(state.productMap.values());
    const newest = latest.reduce(
      (a, l) => (l.observed_at && l.observed_at > a ? l.observed_at : a),
      ""
    );
    document.getElementById("updated").textContent = formatDate(newest);
    renderStats();
    render();
  }

  main();
})();
