(function () {
  const ID = "local-position-history-card";
  const MODAL_ID = "local-position-history-modal";
  const LIST_PATCH_MARKER_ID = "local-position-history-list-patch";
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

  function numberText(value, digits = 4) {
    const number = numberValue(value);
    if (!Number.isFinite(number)) return "--";
    return number.toLocaleString("zh-CN", {
      minimumFractionDigits: 0,
      maximumFractionDigits: digits,
    });
  }

  function signed(value, formatter) {
    const number = numberValue(value);
    if (!Number.isFinite(number)) return '<span class="hist-muted">--</span>';
    const className = number > 0 ? "hist-up" : number < 0 ? "hist-down" : "hist-flat";
    const prefix = number > 0 ? "+" : "";
    return `<span class="${className}">${prefix}${formatter(value)}</span>`;
  }

  function currentFundCode() {
    let match = location.pathname.match(/^\/dashboard\/funds\/([^/?#]+)/);
    if (match) return decodeURIComponent(match[1]);
    match = location.pathname.match(/^\/dashboard\/fund-detail\/([^/?#]+)/);
    if (match) return decodeURIComponent(match[1]);
    const params = new URLSearchParams(location.search);
    return params.get("fund_code") || params.get("code") || "";
  }

  function isPositionsPage() {
    return location.pathname === "/dashboard/positions";
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
      #${ID} .hist-head,
      #${MODAL_ID} .hist-head {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 12px;
      }
      #${ID} .hist-title,
      #${MODAL_ID} .hist-title {
        font-size: 16px;
        font-weight: 700;
        color: var(--hist-text);
      }
      #${ID} .hist-note,
      #${MODAL_ID} .hist-note {
        color: var(--hist-muted);
        font-size: 12px;
        line-height: 1.7;
      }
      #${ID} .hist-grid,
      #${MODAL_ID} .hist-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
      }
      #${ID} .hist-grid.three,
      #${MODAL_ID} .hist-grid.three {
        grid-template-columns: 1fr 1fr 1fr;
      }
      #${ID} .hist-panel,
      #${MODAL_ID} .hist-panel {
        border: 1px solid var(--hist-border);
        border-radius: 12px;
        background: var(--hist-panel);
        padding: 10px 12px;
      }
      #${ID} svg,
      #${MODAL_ID} svg {
        width: 100%;
        height: 160px;
        display: block;
        overflow: visible;
      }
      #${ID} .hist-row,
      #${MODAL_ID} .hist-row {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        color: var(--hist-muted);
        font-size: 12px;
        line-height: 1.9;
      }
      #${ID} .hist-row strong,
      #${MODAL_ID} .hist-row strong { color: var(--hist-text); }
      #${ID} .hist-muted,
      #${MODAL_ID} .hist-muted { color: var(--hist-muted); }
      #${ID} .hist-up,
      #${MODAL_ID} .hist-up { color: #cf1322; font-weight: 700; }
      #${ID} .hist-down,
      #${MODAL_ID} .hist-down { color: #389e0d; font-weight: 700; }
      #${ID} .hist-flat,
      #${MODAL_ID} .hist-flat { color: var(--hist-muted); font-weight: 700; }
      #${ID} .hist-table-wrap,
      #${MODAL_ID} .hist-table-wrap {
        margin-top: 10px;
        overflow-x: auto;
      }
      #${ID} table,
      #${MODAL_ID} table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
        color: var(--hist-text);
      }
      #${ID} th,
      #${ID} td,
      #${MODAL_ID} th,
      #${MODAL_ID} td {
        padding: 8px 10px;
        border-bottom: 1px solid var(--hist-border);
        text-align: right;
        white-space: nowrap;
      }
      #${ID} th:first-child,
      #${ID} td:first-child,
      #${ID} th:nth-child(2),
      #${ID} td:nth-child(2),
      #${MODAL_ID} th:first-child,
      #${MODAL_ID} td:first-child,
      #${MODAL_ID} th:nth-child(2),
      #${MODAL_ID} td:nth-child(2) {
        text-align: left;
      }
      #${ID} th,
      #${MODAL_ID} th {
        color: var(--hist-muted);
        font-weight: 600;
        background: rgba(127,127,127,.06);
      }
      .local-history-link {
        display: inline-flex;
        align-items: center;
        margin-left: 8px;
        padding: 2px 8px;
        border: 1px solid #1677ff;
        border-radius: 999px;
        color: #1677ff;
        background: rgba(22,119,255,.08);
        font-size: 12px;
        line-height: 18px;
        cursor: pointer;
        vertical-align: middle;
      }
      .local-history-link:hover {
        color: #0958d9;
        border-color: #0958d9;
        background: rgba(22,119,255,.14);
      }
      #${MODAL_ID} {
        --hist-bg: #ffffff;
        --hist-panel: #fafafa;
        --hist-border: #e8e8e8;
        --hist-text: #1a1a1a;
        --hist-muted: #8c8c8c;
        position: fixed;
        inset: 0;
        z-index: 9999;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        background: rgba(0,0,0,.45);
      }
      #${MODAL_ID}.hidden {
        display: none;
      }
      #${MODAL_ID}.dark-mode {
        --hist-bg: #141414;
        --hist-panel: #1f1f1f;
        --hist-border: #303030;
        --hist-text: rgba(255,255,255,.88);
        --hist-muted: rgba(255,255,255,.56);
      }
      #${MODAL_ID} .hist-modal-panel {
        width: min(1180px, 96vw);
        max-height: 88vh;
        overflow: auto;
        border-radius: 16px;
        background: var(--hist-bg);
        color: var(--hist-text);
        box-shadow: 0 18px 60px rgba(0,0,0,.25);
      }
      #${MODAL_ID} .hist-modal-head {
        position: sticky;
        top: 0;
        z-index: 1;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 16px;
        border-bottom: 1px solid var(--hist-border);
        background: var(--hist-bg);
      }
      #${MODAL_ID} .hist-modal-body {
        padding: 0 16px 16px;
      }
      #${MODAL_ID} .hist-modal-close {
        border: 0;
        border-radius: 8px;
        padding: 6px 10px;
        color: var(--hist-text);
        background: rgba(127,127,127,.12);
        cursor: pointer;
      }
      @media (max-width: 900px) {
        #${ID} .hist-grid,
        #${ID} .hist-grid.three,
        #${MODAL_ID} .hist-grid,
        #${MODAL_ID} .hist-grid.three { grid-template-columns: 1fr; }
        #${ID} .hist-head,
        #${MODAL_ID} .hist-head { display: block; }
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

  function ensureModal() {
    ensureStyles();
    let modal = document.getElementById(MODAL_ID);
    if (!modal) {
      modal = document.createElement("div");
      modal.id = MODAL_ID;
      modal.className = "hidden";
      modal.innerHTML = `
        <div class="hist-modal-panel">
          <div class="hist-modal-head">
            <div class="hist-title">持仓快照趋势</div>
            <button type="button" class="hist-modal-close">关闭</button>
          </div>
          <div class="hist-modal-body"></div>
        </div>
      `;
      modal.addEventListener("click", (event) => {
        if (event.target === modal || event.target.closest(".hist-modal-close")) closeModal();
      });
      document.body.appendChild(modal);
    }
    modal.classList.toggle("dark-mode", isDarkMode());
    return modal;
  }

  function removeCard() {
    const card = document.getElementById(ID);
    if (card) card.remove();
  }

  function closeModal() {
    const modal = document.getElementById(MODAL_ID);
    if (modal) modal.classList.add("hidden");
  }

  function svgLine(points, field, color, formatter = money) {
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
        <text x="${pad}" y="14" fill="var(--hist-muted)" font-size="12">${formatter(max)}</text>
        <text x="${pad}" y="${height - 4}" fill="var(--hist-muted)" font-size="12">${formatter(min)}</text>
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

  function changeTable(points) {
    if (!points.length) {
      return '<div class="hist-note">还没有支付宝持仓快照。导入一次截图后，这里会开始记录。</div>';
    }
    const hasShare = points.some((point) => Number.isFinite(numberValue(point.share)));
    const rows = points.slice().reverse().map((point) => `
      <tr>
        <td>${point.date || "--"}</td>
        <td>${point.change_label || "--"}</td>
        <td>${numberText(point.share)}</td>
        <td>${signed(point.share_delta, (value) => numberText(value))}</td>
        <td>${money(point.holding_value)}</td>
        <td>${signed(point.holding_value_delta, money)}</td>
        <td>${money(point.holding_profit)}</td>
        <td>${signed(point.holding_profit_delta, money)}</td>
      </tr>
    `).join("");
    const note = hasShare
      ? "份额变化来自每次支付宝截图识别到的 share 字段；加仓/减仓按本次份额减上次份额判断。"
      : "当前历史快照没有识别到份额；以后截图或 JSON 里有 share 字段后会自动记录份额变化。";
    return `
      <div class="hist-table-wrap">
        <table>
          <thead>
            <tr>
              <th>日期</th>
              <th>状态</th>
              <th>份额</th>
              <th>份额变化</th>
              <th>持仓市值</th>
              <th>市值变化</th>
              <th>持有收益</th>
              <th>收益变化</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div class="hist-note" style="margin-top: 8px">${note}</div>
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
    const dark = isDarkMode();
    const card = document.getElementById(ID);
    if (card) card.classList.toggle("dark-mode", dark);
    const modal = document.getElementById(MODAL_ID);
    if (modal) modal.classList.toggle("dark-mode", dark);
  }

  function historyContent(data) {
    const points = Array.isArray(data.points) ? data.points : [];
    return `
      <div class="hist-head">
        <div>
          <div class="hist-title">持仓快照趋势</div>
          <div class="hist-note">${data.fund_code || ""} ${data.fund_name || ""}；来自每次支付宝持仓截图，不读取支付宝昨日收益。</div>
        </div>
        <div class="hist-note">记录数：${points.length}</div>
      </div>
      <div class="hist-grid three">
        <div class="hist-panel">
          <div class="hist-row"><span>持仓市值变化</span><strong>支付宝快照</strong></div>
          ${svgLine(points, "holding_value", "#1677ff")}
        </div>
        <div class="hist-panel">
          <div class="hist-row"><span>持有收益变化</span><strong>支付宝快照</strong></div>
          ${svgLine(points, "holding_profit", "#cf1322")}
        </div>
        <div class="hist-panel">
          <div class="hist-row"><span>持仓份额变化</span><strong>支付宝快照</strong></div>
          ${svgLine(points, "share", "#722ed1", (value) => numberText(value))}
        </div>
      </div>
      <div class="hist-panel" style="margin-top: 10px">
        ${latestRow(points)}
      </div>
      <div class="hist-panel" style="margin-top: 10px">
        <div class="hist-row"><span>持仓变化明细</span><strong>按截图日期倒序</strong></div>
        ${changeTable(points)}
      </div>
    `;
  }

  function render(data) {
    const card = ensureCard();
    card.innerHTML = historyContent(data);
    syncDarkMode();
  }

  async function openHistoryModal(fundCode) {
    const modal = ensureModal();
    const body = modal.querySelector(".hist-modal-body");
    body.innerHTML = '<div class="hist-note" style="padding: 16px">正在读取持仓变化...</div>';
    modal.classList.remove("hidden");
    try {
      const data = await getJson("/api/local/position-history/?fund_code=" + encodeURIComponent(fundCode));
      body.innerHTML = historyContent(data);
      syncDarkMode();
    } catch (error) {
      body.innerHTML = '<div class="hist-note" style="padding: 16px">读取失败，请稍后刷新页面再试。</div>';
    }
  }

  function fundCodeFromText(text) {
    const match = String(text || "").match(/\b(\d{6})\b/);
    return match ? match[1] : "";
  }

  function patchPositionsList() {
    if (!isPositionsPage()) return;
    ensureStyles();
    document.querySelectorAll(".ant-table-tbody tr, .ant-list-item").forEach((row) => {
      if (row.dataset && row.dataset.localHistoryPatched === "1") return;
      const code = fundCodeFromText(row.textContent);
      if (!code) return;
      const target = Array.from(row.querySelectorAll("td, .ant-list-item-meta-title, .ant-list-item-meta-description"))
        .find((node) => fundCodeFromText(node.textContent) === code) || row;
      if (target.querySelector && target.querySelector(".local-history-link")) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "local-history-link";
      button.textContent = "持仓变化";
      button.title = "查看每日份额、市值和收益快照变化";
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        openHistoryModal(code);
      });
      target.appendChild(button);
      if (row.dataset) row.dataset.localHistoryPatched = "1";
    });
  }

  async function refresh() {
    patchPositionsList();
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

  function setupListObserver() {
    const observer = new MutationObserver(() => {
      if (!isPositionsPage() || document.getElementById(LIST_PATCH_MARKER_ID)) return;
      const marker = document.createElement("span");
      marker.id = LIST_PATCH_MARKER_ID;
      marker.hidden = true;
      document.body.appendChild(marker);
      setTimeout(() => {
        patchPositionsList();
        marker.remove();
      }, 100);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function start() {
    setupDarkModeObserver();
    setupListObserver();
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
