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

  const formatDate = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" });
  };

  const state = {
    products: [],
    filter: "all",
    query: "",
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
    // Sort offers: in-stock + has-price first, then by price asc, nulls last.
    for (const g of map.values()) {
      g.offers.sort((a, b) => {
        const aHas = a.price != null;
        const bHas = b.price != null;
        if (aHas !== bHas) return aHas ? -1 : 1;
        if (aHas && bHas) return a.price - b.price;
        return 0;
      });
    }
    return Array.from(map.values());
  }

  function imgSrc(g) {
    if (g.image_path) return g.image_path;
    if (g.image_url) return g.image_url;
    return null;
  }

  function renderCard(g, tmpl) {
    const node = tmpl.content.cloneNode(true);
    const card = node.querySelector(".card");
    const imgwrap = node.querySelector(".card__imgwrap");
    const img = node.querySelector(".card__img");
    const cat = node.querySelector(".card__cat");
    const title = node.querySelector(".card__title");
    const meta = node.querySelector(".card__meta");
    const offers = node.querySelector(".offers");

    card.dataset.category = g.category;

    const cheapest = g.offers.find((o) => o.price != null);
    const primaryUrl = cheapest ? cheapest.url : g.offers[0]?.url || "#";
    imgwrap.setAttribute("href", primaryUrl);

    const src = imgSrc(g);
    if (src) {
      img.src = src;
      img.alt = g.title;
      img.addEventListener("error", () => {
        img.dataset.missing = "1";
        imgwrap.dataset.missing = "1";
      }, { once: true });
    } else {
      img.dataset.missing = "1";
      imgwrap.dataset.missing = "1";
      img.alt = "";
    }

    cat.textContent = CATEGORY_LABELS[g.category] || g.category;

    title.textContent = g.title;
    const metaBits = [];
    if (g.size) metaBits.push(g.size);
    metaBits.push(`${g.offers.length} retailer${g.offers.length === 1 ? "" : "s"}`);
    meta.textContent = metaBits.join(" • ");

    const cheapestPrice = cheapest ? cheapest.price : null;
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

    return node;
  }

  function render() {
    const root = document.getElementById("app");
    const empty = document.getElementById("empty");
    root.innerHTML = "";

    const q = state.query.trim().toLowerCase();
    const filtered = state.products.filter((g) => {
      if (state.filter !== "all" && g.category !== state.filter) return false;
      if (!q) return true;
      return g.title.toLowerCase().includes(q) || g.product_key.toLowerCase().includes(q);
    });

    // Sort within view: category > price asc
    filtered.sort((a, b) => {
      if (a.category !== b.category) return a.category.localeCompare(b.category);
      const ap = a.offers[0]?.price ?? Infinity;
      const bp = b.offers[0]?.price ?? Infinity;
      return ap - bp;
    });

    if (filtered.length === 0) {
      empty.hidden = false;
      return;
    }
    empty.hidden = true;

    const tmpl = document.getElementById("card-template");
    const frag = document.createDocumentFragment();
    for (const g of filtered) frag.appendChild(renderCard(g, tmpl));
    root.appendChild(frag);
  }

  function renderSetupHint() {
    const root = document.getElementById("app");
    root.innerHTML = `
      <div class="setup">
        <h2>No data yet</h2>
        <p>The first weekly scrape hasn't run. Either wait until Monday's cron, or trigger it now:</p>
        <ol>
          <li>Open <a href="https://github.com/cheeroo2020/trackify/actions/workflows/track.yml" target="_blank" rel="noopener">Actions → track</a></li>
          <li>Click <b>Run workflow</b> → <b>Run workflow</b>.</li>
          <li>Wait ~2 minutes, then refresh this page.</li>
        </ol>
        <p style="color: var(--text-dim); font-size: 12.5px;">
          The Action commits scraped prices into <code>data/latest.json</code> in this repo;
          this page just reads that file.
        </p>
      </div>
    `;
  }

  function wireControls() {
    document.querySelectorAll(".chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".chip").forEach((b) => {
          b.classList.toggle("is-active", b === btn);
          b.setAttribute("aria-selected", b === btn ? "true" : "false");
        });
        state.filter = btn.dataset.filter;
        render();
      });
    });
    const search = document.getElementById("search");
    search.addEventListener("input", () => {
      state.query = search.value;
      render();
    });
  }

  async function main() {
    const latest = await safeFetch("data/latest.json", null);
    if (!Array.isArray(latest) || latest.length === 0) {
      renderSetupHint();
      document.getElementById("updated").textContent = "no runs yet";
      return;
    }
    state.products = groupByProduct(latest);
    const newest = latest.reduce(
      (a, l) => (l.observed_at && l.observed_at > a ? l.observed_at : a),
      ""
    );
    document.getElementById("updated").textContent = formatDate(newest);
    wireControls();
    render();
  }

  main();
})();
