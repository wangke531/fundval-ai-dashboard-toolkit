(function () {
  const ID = "local-position-history-card";
  const REFRESH_MS = 60000;

  function authHeaders() {
    const token = localStorage.getItem("access_token") || "local-auto-login";
    return {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    };
  }

  function numberValue(value) {
    if (value === null || value === undefined || value === "") return NaN;
    return Number(String(value).replace(/,/g, ""));
  }

  function money(value) {
    const number = numberValue(value);
    if (!Number.isFinite(number)) return "--";
    return number.toLocaleString("zh-CN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function currentFundCode() {
    let match = location.pathname.match(/^\/dashboard\/funds\/([^/?#]+)/);
    if (match) return decodeURIComponent(match[1]);
    match = location.pathname.match(/^\/dashboard\/fund-detail\/([^/?#]+)/);
    if (match) return decodeURIComponent(match[1]);
    const params = new URLSearchParams(location.search);
    return params.get("fund_code") || params.get("code") || "";
  }

  async function getJson(url) {
    const response = await fetch(url, { headers: authHeaders() });
    if (!response.ok) throw new Error(url + " HTTP " + response.status);
    return response.json();
  }

  function ensureStyles() {
    if (document.getElementById("local-position-history-style")) return;
    const style = document.createElement("style");
    style.id = "local-position-history-style";
    style.textContent = `
      #${ID} {
        --hist-bg: #ffffff;
        --hist-panel: #fafafa;
        --hist-border: #e8e8e8;
        --hist-text: #1a1a1a;
        --hist-muted: #8c8c8c;
        margin: 16px 0;
        padding: 16px;
        border: 1px solid var(--hist-border);
        border-radius: 14px;
        background: var(--hist-bg);
        color: var(--hist-text);
        box-shadow: 0 1px 8px rgba(0,0,0,.08);
      }
      #${ID}.dark-mode {
        --hist-bg: #141414;
        --hist-panel: #1f1f1f;
        --hist-border: #303030;
        --hist-text: rgba(255,255,255,.88);
        --hist-muted: rgba(255,255,255,.56);
        box-shadow: 0 8px 28px rgba(0,0,0,.35);
      }
      #${ID} .hist-head {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 12px;
      }
      #${ID} .hist-title {
        font-size: 16px;
        font-weight: 700;
        color: var(--hist-text);
      }
      #${ID} .hist-note {
        color: var(--hist-muted);
        font-size: 12px;
        line-height: 1.7;
      }
      #${ID} .hist-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
      }
      #${ID} .hist-panel {
        border: 1px solid var(--hist-border);
        border-radius: 12px;
        background: var(--hist-panel);
        padding: 10px 12px;
      }
      #${ID} svg {
        width: 100%;
        height: 160px;
        display: block;
        overflow: visible;
      }
      #${ID} .hist-row {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        color: var(--hist-muted);
        font-size: 12px;
        line-height: 1.9;
      }
      #${ID} .hist-row strong { color: var(--hist-text); }
      @media (max-width: 900px) {
        #${ID} .hist-grid { grid-template-columns: 1fr; }
        #${ID} .hist-head { display: block; }
      }
    `;
    document.head.appendChild(style);
  }

  function findInsertTarget() {
    const content = document.querySelector(".ant-layout-content") || document.querySelector("main") || document.getElementById("root");
    if (!content) return { parent: document.body, before: document.body.firstChild };
    const firstCard = Array.from(content.querySelectorAll(".ant-card")).find((node) => !node.closest("#" + ID));
    if (firstCard) return { parent: firstCard.parentElement || content, before: firstCard };
    return { parent: content, before: content.firstChild };
  }

  function ensureCard() {
    ensureStyles();
    let card = document.getElementById(ID);
    if (!card) {
      card = document.createElement("section");
      card.id = ID;
    }
    const target = findInsertTarget();
    if (target.parent && card.parentElement !== target.parent) {
      target.parent.insertBefore(card, target.before || null);
    } else if (target.parent && target.before && card.nextSibling !== target.before && card !== target.before) {
      target.parent.insertBefore(card, target.before);
    }
    return card;
  }

  function removeCard() {
    const card = document.getElementById(ID);
    if (card) card.remove();
  }

  function svgLine(points, field, color) {
    const values = points.map((point) => numberValue(point[field])).filter(Number.isFinite);
    if (points.length < 2 || values.length < 2) {
      return '<div class="hist-note">至少两次支付宝持仓截图后显示折线趋势。</div>';
    }
    const width = 560;
    const height = 160;
    const pad = 24;
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (Math.abs(max - min) < 0.01) {
      min -= 1;
      max += 1;
    }
    const coords = points.map((point, index) => {
      const value = numberValue(point[field]);
      const x = pad + (index * (width - pad * 2)) / Math.max(points.length - 1, 1);
      const y = height - pad - ((value - min) * (height - pad * 2)) / (max - min);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    return `
      <svg viewBox="0 0 ${width} ${height}" role="img">
        <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="var(--hist-border)" />
        <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="var(--hist-border)" />
        <polyline points="${coords}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
        <text x="${pad}" y="14" fill="var(--hist-muted)" font-size="12">${money(max)}</text>
        <text x="${pad}" y="${height - 4}" fill="var(--hist-muted)" font-size="12">${money(min)}</text>
      </svg>
    `;
  }

  function latestRow(points) {
    const row = points[points.length - 1] || {};
    return `
      <div class="hist-row"><span>最新日期</span><strong>${row.date || "--"}</strong></div>
      <div class="hist-row"><span>持仓市值</span><strong>${money(row.holding_value)}</strong></div>
      <div class="hist-row"><span>持有收益</span><strong>${money(row.holding_profit)}</strong></div>
      <div class="hist-row"><span>份额</span><strong>${row.share || "--"}</strong></div>
    `;
  }

  function brightness(el) {
    const bg = window.getComputedStyle(el).backgroundColor;
    const match = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    if (!match) return -1;
    const alpha = match[4] !== undefined ? parseFloat(match[4]) : 1;
    if (alpha < 0.1) return -1;
    return parseInt(match[1], 10) * 0.299 + parseInt(match[2], 10) * 0.587 + parseInt(match[3], 10) * 0.114;
  }

  function isDarkMode() {
    const classText = String(document.documentElement.className || "") + " " + String(document.body.className || "");
    if (classText.toLowerCase().includes("dark")) return true;
    const dataTheme = document.documentElement.getAttribute("data-theme") || document.body.getAttribute("data-theme");
    if (String(dataTheme).toLowerCase() === "dark") return true;
    const targets = [document.querySelector(".ant-layout"), document.querySelector(".ant-layout-content"), document.body].filter(Boolean);
    return targets.some((target) => {
      const value = brightness(target);
      return value >= 0 && value < 120;
    });
  }

  function syncDarkMode() {
    const card = document.getElementById(ID);
    if (!card) return;
    card.classList.toggle("dark-mode", isDarkMode());
  }

  function render(data) {
    const card = ensureCard();
    const points = Array.isArray(data.points) ? data.points : [];
    card.innerHTML = `
      <div class="hist-head">
        <div>
          <div class="hist-title">持仓快照趋势</div>
          <div class="hist-note">${data.fund_code || ""} ${data.fund_name || ""}；来自每次支付宝持仓截图，不读取支付宝昨日收益。</div>
        </div>
        <div class="hist-note">记录数：${points.length}</div>
      </div>
      <div class="hist-grid">
        <div class="hist-panel">
          <div class="hist-row"><span>持仓市值变化</span><strong>支付宝快照</strong></div>
          ${svgLine(points, "holding_value", "#1677ff")}
        </div>
        <div class="hist-panel">
          <div class="hist-row"><span>持有收益变化</span><strong>支付宝快照</strong></div>
          ${svgLine(points, "holding_profit", "#cf1322")}
        </div>
      </div>
      <div class="hist-panel" style="margin-top: 10px">
        ${latestRow(points)}
      </div>
    `;
    syncDarkMode();
  }

  async function refresh() {
    const code = currentFundCode();
    if (!code) {
      removeCard();
      return;
    }
    try {
      const data = await getJson("/api/local/position-history/?fund_code=" + encodeURIComponent(code));
      render(data);
    } catch (error) {
      removeCard();
    }
  }

  function setupDarkModeObserver() {
    const observer = new MutationObserver(syncDarkMode);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "style", "data-theme"] });
    observer.observe(document.body, { attributes: true, attributeFilter: ["class", "style", "data-theme"] });
  }

  function start() {
    setupDarkModeObserver();
    refresh();
    setInterval(refresh, REFRESH_MS);
  }

  window.addEventListener("load", start);
  window.addEventListener("popstate", refresh);
  const originalPushState = history.pushState;
  history.pushState = function () {
    originalPushState.apply(this, arguments);
    setTimeout(refresh, 100);
  };
})();
