// frontEnd/js/main_dashboard.js

// 기본 API 엔드포인트 (커스터마이징 가능)
const API_BASE_URL = (window.KOBOT_API_BASE_URL || "https://kobotpick.onrender.com/api/v1").replace(/\/+$/, "");

const REQUEST_TIMEOUT_MS = 20000;
const PICKS_REFRESH_MS = 60000;

// 기본 표시용 목록 (API 실패 시)
const FALLBACK_PICKS = [
  { ticker: "AAPL", name: "Apple Inc.", country: "US", score: 50 },
  { ticker: "TSLA", name: "Tesla, Inc.", country: "US", score: 50 },
  { ticker: "NVDA", name: "NVIDIA Corp.", country: "US", score: 50 },
  { ticker: "MSFT", name: "Microsoft Corp.", country: "US", score: 50 },
  { ticker: "AMZN", name: "Amazon.com, Inc.", country: "US", score: 50 },
  { ticker: "005930.KS", name: "Samsung Electronics", country: "KR", score: 50 },
  { ticker: "000660.KS", name: "SK hynix", country: "KR", score: 50 },
  { ticker: "035420.KS", name: "NAVER Corp.", country: "KR", score: 50 },
  { ticker: "051910.KS", name: "LG Chem", country: "KR", score: 50 },
  { ticker: "207940.KS", name: "Samsung Biologics", country: "KR", score: 50 },
  { ticker: "SPY", name: "SPDR S&P 500 ETF", country: "ETF", score: 50 },
  { ticker: "QQQ", name: "Invesco QQQ Trust", country: "ETF", score: 50 },
  { ticker: "VTI", name: "Vanguard Total Stock Market ETF", country: "ETF", score: 50 },
  { ticker: "IWM", name: "iShares Russell 2000 ETF", country: "ETF", score: 50 },
  { ticker: "ARKK", name: "ARK Innovation ETF", country: "ETF", score: 50 },
];

document.addEventListener("DOMContentLoaded", () => {
  wakeUpServer();
  loadDashboard();
  setInterval(loadDashboard, PICKS_REFRESH_MS);
});

async function wakeUpServer() {
  try {
    await fetch(`${API_BASE_URL}/market/snapshot`, { cache: "no-store", signal: AbortSignal.timeout(4000) });
  } catch {
    // 콜드스타트 실패는 무시
  }
}

async function loadDashboard() {
  const loading = document.getElementById("loading");
  if (loading) {
    loading.style.display = "block";
    loading.innerText = "실시간 데이터를 불러오는 중입니다...";
  }

  try {
    const picks = await fetchPicksWithRec();
    renderSections(picks);
  } catch (err) {
    console.error("fetch dashboard error", err);
    renderSections(FALLBACK_PICKS);
  } finally {
    if (loading) loading.style.display = "none";
  }
}

async function fetchPicksWithRec() {
  const picksRes = await fetchWithTimeout(`${API_BASE_URL}/picks`, { timeout: REQUEST_TIMEOUT_MS });
  if (!picksRes.ok) throw new Error(`picks error ${picksRes.status}`);
  const picks = await picksRes.json();
  if (!Array.isArray(picks) || !picks.length) throw new Error("empty picks");

  // 개별 recommendation 병렬 호출
  const enriched = await Promise.all(
    picks.map(async (p) => {
      try {
        const recRes = await fetchWithTimeout(`${API_BASE_URL}/recommendation/${encodeURIComponent(p.ticker)}`, {
          timeout: REQUEST_TIMEOUT_MS,
        });
        if (!recRes.ok) throw new Error(`rec error ${recRes.status}`);
        const rec = await recRes.json();
        return { ...p, rec };
      } catch (e) {
        console.warn("rec fallback", p.ticker, e);
        return { ...p, rec: null };
      }
    })
  );
  return enriched;
}

async function fetchWithTimeout(url, { timeout = REQUEST_TIMEOUT_MS, ...options } = {}) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(id);
  }
}

function renderSections(items) {
  const usBox = document.getElementById("us-picks");
  const krBox = document.getElementById("kr-picks");
  const etfBox = document.getElementById("etf-picks");
  if (!usBox || !krBox) return;
  usBox.innerHTML = "";
  krBox.innerHTML = "";
  if (etfBox) etfBox.innerHTML = "";

  const renderCard = (target, item) => {
    const rec = item.rec?.recommendation;
    const price = item.rec?.current_price;
    const buy = rec?.buy_price;
    const sell = rec?.sell_price;
    const action = rec?.action || "HOLD";
    const currency = item.rec?.currency || (item.ticker.endsWith(".KS") ? "KRW" : "USD");
    const card = document.createElement("div");
    card.className = "stock-card";
    card.onclick = () => (window.location.href = `/detail.html?ticker=${encodeURIComponent(item.ticker)}`);
    card.innerHTML = `
      <div class="card-top">
        <div class="name">${item.name || item.ticker}</div>
        <div class="badge">${item.country}</div>
      </div>
      <div class="ticker">${item.ticker}</div>
      <div class="price-block">
        <div class="price">${formatPrice(price, currency)}</div>
        <div class="action ${action.toLowerCase()}">${action}</div>
      </div>
      <div class="targets">
        <div>Buy <span>${formatPrice(buy, currency)}</span></div>
        <div>Sell <span>${formatPrice(sell, currency)}</span></div>
      </div>
      <div class="score">Score ${item.score ?? "-"}</div>
    `;
    target.appendChild(card);
  };

  items.filter((p) => p.country === "US").slice(0, 5).forEach((p) => renderCard(usBox, p));
  items.filter((p) => p.country === "KR").slice(0, 5).forEach((p) => renderCard(krBox, p));
  if (etfBox) items.filter((p) => p.country === "ETF").slice(0, 5).forEach((p) => renderCard(etfBox, p));
}

function formatPrice(val, currency = "USD") {
  if (val === null || val === undefined || Number.isNaN(val)) return "준비중";
  try {
    if (currency === "KRW") return `${Math.round(val).toLocaleString("ko-KR")}원`;
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(val);
  } catch {
    return `${val}`;
  }
}
