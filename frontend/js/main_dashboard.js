// frontEnd/js/main_dashboard.js

// 기본 API 엔드포인트 (커스터마이징 가능)
const API_BASE_URL = (window.KOBOT_API_BASE_URL || "https://kobotpick.onrender.com/api/v1").replace(/\/+$/, "");
const LANG_STORAGE_KEY = "kobot-lang";
const FAVORITES_KEY = "kobot-favorites";
let currentLang = localStorage.getItem(LANG_STORAGE_KEY) || "ko";
const HEADLINE_SUBTEXT = {
  ko: "빠르게 훑어보는 오늘의 주요 헤드라인",
  en: "Quick scan of today's key headlines",
  ja: "今日の主要ヘッドラインをすばやくチェック",
  zh: "快速浏览今日要闻",
};

const REQUEST_TIMEOUT_MS = 45000; // 서버 콜드/부하 시 여유를 둠
const MAX_REC_CONCURRENCY = 5; // recommendation 병렬 호출 제한
const INITIAL_ITEMS_PER_SECTION = 2;
const MAX_ITEMS_PER_SECTION = 15; // 섹션별 최대 사용 (백엔드가 10개 공급)
const MORE_STATE = { us: false, kr: false, etf: false };
const PICKS_REFRESH_MS = 120000; // 자주 새로고침해도 캐시 효과가 줄어들므로 2분으로 완화
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

const HEADLINE_FALLBACK = {
  ko: [
    { title: "미국 증시, 기술주 강세 지속", link: "https://finance.naver.com/news/" },
    { title: "반도체 업황 회복 기대감", link: "https://finance.naver.com/news/" },
  ],
  en: [
    { title: "U.S. tech leads gains as Nasdaq closes higher", link: "https://finance.yahoo.com" },
    { title: "Chip recovery optimism grows among investors", link: "https://finance.yahoo.com" },
  ],
};

document.addEventListener("DOMContentLoaded", () => {
  wakeUpServer();
  showDashboardSkeleton();
  loadDashboard();
  loadMarketSnapshot();
  loadHeadlines();
  setInterval(loadDashboard, PICKS_REFRESH_MS);
  setInterval(loadMarketSnapshot, SNAPSHOT_REFRESH_MS);
  setInterval(loadHeadlines, HEADLINE_REFRESH_MS);

  const langSelect = document.getElementById("lang-select");
  if (langSelect) {
    langSelect.value = currentLang;
    langSelect.addEventListener("change", (e) => {
      currentLang = e.target.value || "ko";
      localStorage.setItem(LANG_STORAGE_KEY, currentLang);
      loadHeadlines();
      const sub = document.querySelector(".headline-sub");
      if (sub) sub.textContent = HEADLINE_SUBTEXT[currentLang] || HEADLINE_SUBTEXT.en;
    });
  }
  const sub = document.querySelector(".headline-sub");
  if (sub) sub.textContent = HEADLINE_SUBTEXT[currentLang] || HEADLINE_SUBTEXT.en;

  const searchInput = document.getElementById("search-input");
  const searchIcon = document.querySelector(".search-icon");
  const goSearch = () => {
    if (!searchInput) return;
    const raw = searchInput.value.trim();
    if (!raw) return;
    const normalized = /^[0-9]{6}$/.test(raw) ? `${raw}.KS` : raw.toUpperCase();
    // GA4 검색 이벤트 전송
    if (typeof gtag === "function") {
      gtag("event", "search", {
        search_term: raw,
        normalized_ticker: normalized,
      });
    }
    window.location.href = `/detail.html?ticker=${encodeURIComponent(normalized)}`;
  };
  if (searchInput) {
    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") goSearch();
    });
  }
  if (searchIcon) {
    searchIcon.style.cursor = "pointer";
    searchIcon.addEventListener("click", goSearch);
  }
  const favScroll = document.getElementById("fav-scroll");
  if (favScroll) {
    favScroll.addEventListener("click", () => {
      const target = document.getElementById("fav-section");
      if (target) target.scrollIntoView({ behavior: "smooth" });
    });
  }
});

async function wakeUpServer() {
  try {
    await fetch(`${API_BASE_URL}/market/snapshot`, { cache: "no-store", signal: AbortSignal.timeout(4000) });
  } catch {
    // 콜드스타트 실패는 무시
  }
}

async function loadDashboard(retried = false) {
  const loading = document.getElementById("loading");
  if (loading) {
    loading.style.display = "block";
    loading.innerText = "실시간 데이터를 불러오는 중입니다...";
  }

  try {
    const picks = await fetchPicksWithRec();
    // 초기 노출 3개씩만 추천 상세 호출
    const { initialTargets } = sliceSections(picks);
    await fetchRecommendations(initialTargets);
    renderSections(picks);
  } catch (err) {
    if (err?.name === "AbortError") {
      console.warn("fetch dashboard aborted (timeout)", err);
    } else {
      console.error("fetch dashboard error", err);
    }
    if (!retried && err?.name === "AbortError") {
      // 한 번만 재시도
      await new Promise((r) => setTimeout(r, 400));
      return loadDashboard(true);
    }
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
  track.innerHTML =
    currentLang === "ko"
      ? `<span class="headline-empty">헤드라인을 불러오는 중...</span>`
      : `<span class="headline-empty">Loading headlines...</span>`;
  try {
    const res = await fetchWithTimeout(
      `${API_BASE_URL}/market/headlines?lang=${encodeURIComponent(currentLang)}`,
      { timeout: REQUEST_TIMEOUT_MS }
    );
    if (!res.ok) throw new Error(`headlines error ${res.status}`);
    const data = await res.json();
    renderHeadlines(data);
  } catch (err) {
    console.warn("headlines fallback", err);
    const fb = HEADLINE_FALLBACK[currentLang] || HEADLINE_FALLBACK.en;
    renderHeadlines(fb);
  }
}

async function fetchPicksWithRec() {
  const picksRes = await fetchWithTimeout(`${API_BASE_URL}/picks`, { timeout: REQUEST_TIMEOUT_MS });
  if (!picksRes.ok) throw new Error(`picks error ${picksRes.status}`);
  const picks = await picksRes.json();
  if (!Array.isArray(picks) || !picks.length) throw new Error("empty picks");
  // 추천은 초기 2개씩만 먼저 호출, 나머지는 더보기 시 호출
  return picks.map((p) => ({ ...p, rec: null }));
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

function sliceSections(items) {
  const usItems = items.filter((p) => p.country === "US").slice(0, MAX_ITEMS_PER_SECTION);
  const krItems = items.filter((p) => p.country === "KR").slice(0, MAX_ITEMS_PER_SECTION);
  const etfItems = items.filter((p) => p.country === "ETF").slice(0, MAX_ITEMS_PER_SECTION);
  const initialTargets = [
    ...usItems.slice(0, INITIAL_ITEMS_PER_SECTION),
    ...krItems.slice(0, INITIAL_ITEMS_PER_SECTION),
    ...etfItems.slice(0, INITIAL_ITEMS_PER_SECTION),
  ].filter(Boolean);
  return { usItems, krItems, etfItems, initialTargets };
}

async function fetchRecommendations(targets = []) {
  const pending = targets.filter((t) => t && !t.rec);
  if (!pending.length) return;
  let cursor = 0;
  const worker = async () => {
    while (cursor < pending.length) {
      const idx = cursor++;
      const p = pending[idx];
      try {
        const recRes = await fetchWithTimeout(`${API_BASE_URL}/recommendation/${encodeURIComponent(p.ticker)}`, {
          timeout: REQUEST_TIMEOUT_MS,
        });
        if (!recRes.ok) throw new Error(`rec error ${recRes.status}`);
        const rec = await recRes.json();
        pending[idx].rec = rec;
      } catch (e) {
        console.warn("rec fallback", p.ticker, e);
        pending[idx].rec = null;
      }
    }
  };
  const workers = Array.from({ length: Math.min(MAX_REC_CONCURRENCY, pending.length) }, worker);
  await Promise.all(workers);
}

// ✅ [추가] 광고 초기화 함수
function loadAdSense() {
  try {
    const ads = document.querySelectorAll(".adsbygoogle");
    ads.forEach((ad) => {
      if (!ad.getAttribute("data-adsbygoogle-status")) {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
      }
    });
  } catch (e) {
    console.warn("AdSense load error:", e);
  }
}

function renderSections(items) {
  const usBox = document.getElementById("us-picks");
  const krBox = document.getElementById("kr-picks");
  const etfBox = document.getElementById("etf-picks");
  const favBox = document.getElementById("favorites-list");
  if (!usBox || !krBox) return;
  usBox.innerHTML = "";
  krBox.innerHTML = "";
  if (etfBox) etfBox.innerHTML = "";
  if (favBox) favBox.innerHTML = "";

  const favorites = loadFavorites();
  const renderCard = (target, item) => {
    const rec = item.rec?.recommendation;
    const price = item.rec?.current_price;
    const buy = rec?.buy_price;
    const sell = rec?.sell_price;
    const action = rec?.action || "HOLD";
    const currency = item.rec?.currency || (item.ticker.endsWith(".KS") ? "KRW" : "USD");
    const favOn = favorites.includes(item.ticker);
    const card = document.createElement("div");
    card.className = "stock-card";
    card.onclick = () => (window.location.href = `/detail.html?ticker=${encodeURIComponent(item.ticker)}`);
    card.innerHTML = `
      <div class="card-top">
        <div class="name-row">
          <div class="name">${item.name || item.ticker}</div>
          <div class="badge">${item.country}</div>
        </div>
        <button class="card-fav ${favOn ? "on" : ""}" data-ticker="${item.ticker}" aria-label="관심 목록 추가">★</button>
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
    const favBtn = card.querySelector(".card-fav");
    if (favBtn) {
      favBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleFavorite(item.ticker);
        favBtn.classList.toggle("on", isFavorite(item.ticker));
        renderFavoritesSection(items);
      });
    }
    target.appendChild(card);
    loadAdSense()
  };

  const renderList = (target, list) => {
    if (!target) return;
    target.innerHTML = "";
    list.forEach((p) => renderCard(target, p));
  };

  const { usItems, krItems, etfItems } = sliceSections(items);

  renderList(usBox, usItems.slice(0, INITIAL_ITEMS_PER_SECTION));
  renderList(krBox, krItems.slice(0, INITIAL_ITEMS_PER_SECTION));
  if (etfBox) renderList(etfBox, etfItems.slice(0, INITIAL_ITEMS_PER_SECTION));

  const setupMore = (key, allItems) => {
    const btn = document.querySelector(`.more-btn[data-section="${key}"]`);
    const area = document.getElementById(`${key}-more-area`);
    const listEl = document.getElementById(`${key}-more-list`);
    if (!btn || !area || !listEl) return;
    if (allItems.length <= INITIAL_ITEMS_PER_SECTION) {
      btn.style.display = "none";
      return;
    }
    btn.style.display = "block";
    btn.onclick = async () => {
      const expanded = MORE_STATE[key];
      if (expanded) {
        area.hidden = true;
        listEl.innerHTML = "";
        MORE_STATE[key] = false;
        btn.textContent = "더보기";
        return;
      }
      area.hidden = false;
      btn.disabled = true;
      btn.textContent = "로딩 중...";
      await fetchRecommendations(allItems.slice(INITIAL_ITEMS_PER_SECTION));
      renderList(listEl, allItems.slice(INITIAL_ITEMS_PER_SECTION));
      MORE_STATE[key] = true;
      btn.textContent = "간단히 보기";
      btn.disabled = false;
    };
  };

  setupMore("us", usItems);
  setupMore("kr", krItems);
  setupMore("etf", etfItems);

  renderFavoritesSection(items);
}

function showDashboardSkeleton() {
  const usBox = document.getElementById("us-picks");
  const krBox = document.getElementById("kr-picks");
  const etfBox = document.getElementById("etf-picks");
  [usBox, krBox, etfBox].forEach((box) => {
    if (!box) return;
    box.innerHTML = "";
    renderSkeletonCards(box, 2);
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
      (n) => `
        <a class="headline-card" href="${n.link}" target="_blank" rel="noopener noreferrer">
          <div class="headline-title">${n.title}</div>
          <div class="headline-meta">${n.publisher || "Top News"}</div>
        </a>
      `
    )
    .join("");
}

function loadFavorites() {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}
function saveFavorites(list) {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify(list));
}
function isFavorite(ticker) {
  return loadFavorites().includes(ticker);
}
function toggleFavorite(ticker) {
  const list = loadFavorites();
  const idx = list.indexOf(ticker);
  if (idx >= 0) list.splice(idx, 1);
  else list.push(ticker);
  saveFavorites(list);
}

function renderFavoritesSection(items) {
  const box = document.getElementById("favorites-list");
  if (!box) return;
  const favs = loadFavorites();
  if (!favs.length) {
    box.classList.add("empty-state");
    box.innerHTML = "아직 추가된 종목이 없습니다.";
    return;
  }
  const dict = Object.fromEntries(items.map((i) => [i.ticker, i]));
  box.classList.remove("empty-state");
  const buildPrice = (item) => {
    if (!item) return "준비중";
    const currency = item.rec?.currency || (item.ticker?.endsWith(".KS") ? "KRW" : "USD");
    const price = item.rec?.current_price ?? item.price;
    return formatPrice(price, currency);
  };
  box.innerHTML = favs
    .map((t) => {
      const item = dict[t];
      const name = item?.name || t;
      const change = typeof item?.change_pct === "number" ? item.change_pct.toFixed(2) : null;
      return `
        <div class="fav-card" data-ticker="${t}">
          <div class="fav-card-top">
            <div class="fav-pill">
              <span class="fav-ticker">${t}</span>
              <span class="fav-country">${item?.country || "-"}</span>
            </div>
            <button class="fav-remove" aria-label="삭제">×</button>
          </div>
          <div class="fav-name">${name}</div>
          <div class="fav-meta">
            <span class="fav-price">${buildPrice(item)}</span>
            ${
              change !== null
                ? `<span class="fav-change ${item.change_pct >= 0 ? "up" : "down"}">${change}%</span>`
                : ""
            }
            <span class="fav-score">Score ${item?.score ?? "-"}</span>
          </div>
        </div>
      `;
    })
    .join("");
  box.querySelectorAll(".fav-card").forEach((card) => {
    const t = card.getAttribute("data-ticker");
    card.addEventListener("click", () => {
      window.location.href = `/detail.html?ticker=${encodeURIComponent(t)}`;
    });
    const btn = card.querySelector(".fav-remove");
    if (btn) {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleFavorite(t);
        renderFavoritesSection(items);
        refreshCardFavoriteStates();
      });
    }
  });
}

function refreshCardFavoriteStates() {
  document.querySelectorAll(".card-fav").forEach((btn) => {
    const t = btn.getAttribute("data-ticker");
    btn.classList.toggle("on", isFavorite(t));
  });
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
