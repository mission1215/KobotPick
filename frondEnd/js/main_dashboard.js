// frontEnd/js/main_dashboard.js

// 기본 API 엔드포인트 (커스터마이징 가능)
const API_BASE_URL = (window.KOBOT_API_BASE_URL || "https://kobotpick.onrender.com/api/v1").replace(/\/+$/, "");

const REQUEST_TIMEOUT_MS = 20000;
const PICKS_REFRESH_MS = 60000;
const SNAPSHOT_REFRESH_MS = 60000;
const HEADLINE_REFRESH_MS = 300000;

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

const HEADLINE_FALLBACK = [
  { title: "미국 증시, 기술주 강세 지속", link: "https://finance.yahoo.com" },
  { title: "반도체 업황 회복 기대감", link: "https://finance.yahoo.com" },
];

document.addEventListener("DOMContentLoaded", () => {
  wakeUpServer();
  showDashboardSkeleton();
  loadDashboard();
  loadMarketSnapshot();
  loadHeadlines();
  setInterval(loadDashboard, PICKS_REFRESH_MS);
  setInterval(loadMarketSnapshot, SNAPSHOT_REFRESH_MS);
  setInterval(loadHeadlines, HEADLINE_REFRESH_MS);
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

async function loadMarketSnapshot() {
  const box = document.getElementById("market-snapshot");
  if (!box) return;
  box.innerHTML = `
    <div class="snapshot-skeleton"></div>
    <div class="snapshot-skeleton"></div>
    <div class="snapshot-skeleton"></div>
  `;

  try {
    const res = await fetchWithTimeout(`${API_BASE_URL}/market/snapshot`, { timeout: REQUEST_TIMEOUT_MS });
    if (!res.ok) throw new Error(`snapshot error ${res.status}`);
    const data = await res.json();
    renderSnapshot(data);
  } catch (err) {
    console.warn("snapshot fallback", err);
    renderSnapshot(null);
  }
}

async function loadHeadlines() {
  const track = document.getElementById("headline-track");
  if (!track) return;
  track.innerHTML = `<span class="headline-empty">헤드라인을 불러오는 중...</span>`;
  try {
    const res = await fetchWithTimeout(`${API_BASE_URL}/market/headlines`, { timeout: REQUEST_TIMEOUT_MS });
    if (!res.ok) throw new Error(`headlines error ${res.status}`);
    const data = await res.json();
    renderHeadlines(data);
  } catch (err) {
    console.warn("headlines fallback", err);
    renderHeadlines(HEADLINE_FALLBACK);
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

function showDashboardSkeleton() {
  const usBox = document.getElementById("us-picks");
  const krBox = document.getElementById("kr-picks");
  const etfBox = document.getElementById("etf-picks");
  [usBox, krBox, etfBox].forEach((box) => {
    if (!box) return;
    box.innerHTML = "";
    renderSkeletonCards(box, 5);
  });
  const track = document.getElementById("headline-track");
  if (track) {
    track.innerHTML = `<span class="headline-empty">헤드라인을 준비 중...</span>`;
  }
}

function renderSkeletonCards(target, count = 3) {
  for (let i = 0; i < count; i += 1) {
    const card = document.createElement("div");
    card.className = "stock-card skeleton-card";
    card.innerHTML = `
      <div class="skeleton-line wide"></div>
      <div class="skeleton-line short"></div>
      <div class="skeleton-line mid"></div>
      <div class="skeleton-line short"></div>
    `;
    target.appendChild(card);
  }
}

function renderSnapshot(data) {
  const box = document.getElementById("market-snapshot");
  if (!box) return;
  if (!data || Object.keys(data).length === 0) {
    box.innerHTML = `<div class="snapshot-error">지표를 불러올 수 없습니다.</div>`;
    return;
  }
  box.innerHTML = Object.entries(data)
    .map(([label, info]) => {
      const change = info?.change_pct ?? 0;
      const cls = change >= 0 ? "pos" : "neg";
      const price = info?.price ?? 0;
      const changeText = `${change > 0 ? "+" : ""}${change.toFixed(2)}%`;
      return `
        <div class="snapshot-item">
          <div class="snap-label">${label}</div>
          <div class="snap-value ${cls}">${price.toLocaleString()}</div>
          <div class="snap-change ${cls}">${changeText}</div>
        </div>
      `;
    })
    .join("");
}

function renderHeadlines(items) {
  const track = document.getElementById("headline-track");
  if (!track) return;
  if (!items || items.length === 0) {
    track.innerHTML = `<span class="headline-empty">헤드라인을 불러올 수 없습니다.</span>`;
    return;
  }
  track.innerHTML = items
    .map(
      (n, idx) => `
        <a class="headline-card" href="${n.link}" target="_blank" rel="noopener noreferrer">
          <div class="headline-chip">N${idx + 1}</div>
          <div class="headline-title">${n.title}</div>
          <div class="headline-meta">${n.publisher || "Top News"}</div>
        </a>
      `
    )
    .join("");
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
