(function () {
  const ID = "local-estimate-source-badge";
  const API = "/api/local/estimate-sources/";

  function ensureBadge() {
    let badge = document.getElementById(ID);
    if (badge) {
      return badge;
    }
    badge = document.createElement("div");
    badge.id = ID;
    badge.style.cssText = [
      "position:fixed",
      "right:14px",
      "bottom:14px",
      "z-index:99999",
      "padding:8px 12px",
      "border-radius:999px",
      "background:rgba(22,24,29,.88)",
      "color:#fff",
      "font-size:12px",
      "line-height:1.4",
      "box-shadow:0 8px 24px rgba(0,0,0,.18)",
      "backdrop-filter:blur(8px)",
      "max-width:78vw",
      "white-space:nowrap",
    ].join(";");
    badge.textContent = "估值源检查中";
    document.body.appendChild(badge);
    return badge;
  }

  function authHeaders() {
    const token = localStorage.getItem("access_token") || "local-auto-login";
    return {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    };
  }

  function formatSummary(data) {
    const counts = data.counts || {};
    const parts = Object.keys(counts).map((name) => name + " " + counts[name]);
    if (!parts.length) {
      return "估值源: 暂无持仓";
    }
    const fallback = data.fallback_count ? "，兜底 " + data.fallback_count : "";
    return "估值源: " + parts.join(" / ") + fallback;
  }

  async function refreshBadge() {
    if (!location.pathname.startsWith("/dashboard")) {
      return;
    }
    const badge = ensureBadge();
    try {
      const response = await fetch(API, { headers: authHeaders() });
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      const data = await response.json();
      badge.textContent = formatSummary(data);
      badge.title = "养基宝优先；养基宝没有数据时临时使用兜底源，下次刷新会继续重试养基宝。";
    } catch (error) {
      badge.textContent = "估值源: 读取失败";
      badge.title = String(error);
    }
  }

  window.addEventListener("load", refreshBadge);
  window.addEventListener("popstate", refreshBadge);
  setInterval(refreshBadge, 60000);
})();
