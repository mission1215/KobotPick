// kobotPick/frontEnd/js/main_dashboard.js

// API Base URL: 배포/로컬 모두 대응 & 끝의 슬래시 제거
const API_BASE_URL = (
  window.KOBOT_API_BASE_URL ||
  "https://kobotpick.onrender.com/api/v1/"
).replace(/\/+$/, ""); 

const REFRESH_MS = 60000; // 1분마다 새로고침 (유사 실시간)
const REQUEST_TIMEOUT_MS = 20000; // API 최대 대기 20초
const PICKS_TIMEOUT_MS = 12000; // 추천 목록 로딩은 빠르게 타임아웃 후 폴백
const FAVORITES_KEY = 'kobot-favorites';
let lastPicks = [];
let lastRenderedPicks = [];
const FALLBACK_PICKS = [
    { ticker: 'AAPL', name: 'Apple Inc.', country: 'US', score: 50 },
    { ticker: 'TSLA', name: 'Tesla, Inc.', country: 'US', score: 50 },
    { ticker: 'NVDA', name: 'NVIDIA Corp.', country: 'US', score: 50 },
    { ticker: 'MSFT', name: 'Microsoft Corp.', country: 'US', score: 50 },
    { ticker: 'AMZN', name: 'Amazon.com, Inc.', country: 'US', score: 50 },
    { ticker: '005930.KS', name: 'Samsung Electronics', country: 'KR', score: 50 },
    { ticker: '000660.KS', name: 'SK hynix', country: 'KR', score: 50 },
    { ticker: '035420.KS', name: 'NAVER Corp.', country: 'KR', score: 50 },
    { ticker: '051910.KS', name: 'LG Chem', country: 'KR', score: 50 },
    { ticker: '207940.KS', name: 'Samsung Biologics', country: 'KR', score: 50 },
    { ticker: 'SPY', name: 'SPDR S&P 500 ETF', country: 'ETF', score: 50 },
    { ticker: 'QQQ', name: 'Invesco QQQ Trust', country: 'ETF', score: 50 },
    { ticker: 'VTI', name: 'Vanguard Total Stock Market ETF', country: 'ETF', score: 50 },
    { ticker: 'IWM', name: 'iShares Russell 2000 ETF', country: 'ETF', score: 50 },
    { ticker: 'ARKK', name: 'ARK Innovation ETF', country: 'ETF', score: 50 },
].map((p) => ({
    ...p,
    rec: {
        current_price: null,
        currency: p.country === 'KR' ? 'KRW' : 'USD',
        recommendation: { action: 'HOLD', buy_price: null, sell_price: null },
    },
}));
// 검색 보조용 이름/티커 매핑 (공백/구두점 제거 후 비교)
const NAME_TICKER_MAP = {
    APPLE: 'AAPL',
    APPLEINC: 'AAPL',
    TESLA: 'TSLA',
    TESLAINC: 'TSLA',
    NVIDIA: 'NVDA',
    NVIDIACORP: 'NVDA',
    MSFT: 'MSFT',
    MICROSOFT: 'MSFT',
    MICROSOFTCORP: 'MSFT',
    AMAZON: 'AMZN',
    AMAZONCOM: 'AMZN',
    AMZN: 'AMZN',
    SAMSUNG: '005930.KS',
    삼성전자: '005930.KS',
    삼성: '005930.KS',
    삼성전자우: '005935.KS',
    SKHYNIX: '000660.KS',
    SK하이닉스: '000660.KS',
    NAVER: '035420.KS',
    LG화학: '051910.KS',
};

const TEXT = {
    ko: {
        loading: '추천 종목을 분석 중입니다...',
        us: '🇺🇸 해외 추천 Top 5',
        kr: '🇰🇷 국내 추천 Top 5',
        etf: '📊 ETF 추천 Top 5',
        news: '주요 뉴스',
        disclaimer: '이 정보는 AI 알고리즘에 의한 참고용이며, 투자 결정 및 책임은 본인에게 있습니다.',
        heroTitle: '오늘의 AI 추천 포트폴리오',
        heroSub: '해외/국내/ETF 추천을 한 번에 확인하세요.',
        live: 'Live',
    },
    en: {
        loading: 'Analyzing today’s picks...',
        us: '🇺🇸 US Top 5',
        kr: '🇰🇷 Korea Top 5',
        etf: '📊 ETF Top 5',
        news: 'Top News',
        disclaimer: 'AI-generated suggestions for reference only. Invest at your own risk.',
        heroTitle: 'Today’s AI Picks Portfolio',
        heroSub: 'See US, Korea, and ETF picks in one view.',
        live: 'Live',
    },
    ja: {
        loading: '銘柄を分析中です...',
        us: '🇺🇸 米国おすすめ Top 5',
        kr: '🇰🇷 韓国おすすめ Top 5',
        etf: '📊 ETFおすすめ Top 5',
        news: 'ニュース',
        disclaimer: '本情報はAIによる参考用であり、投資判断は自己責任です。',
        heroTitle: '今日のAIポートフォリオ',
        heroSub: '米国・韓国・ETFを一目で確認。',
        live: 'Live',
    },
    zh: {
        loading: '正在分析推荐股票...',
        us: '🇺🇸 美国推荐 Top 5',
        kr: '🇰🇷 韩国推荐 Top 5',
        etf: '📊 ETF 推荐 Top 5',
        news: '新闻',
        disclaimer: '本信息仅供参考，投资风险自担。',
        heroTitle: '今日 AI 推荐组合',
        heroSub: '同时查看美股、韩股和 ETF 推荐。',
        live: 'Live',
    },
};

const CACHE_KEYS = {
    picks: 'kobot-cache-picks',
    snapshot: 'kobot-cache-snapshot',
    headlines: 'kobot-cache-headlines',
};

const CACHE_TTL_MS = {
    picks: 15 * 60 * 1000, // 15분
    snapshot: 5 * 60 * 1000, // 5분
    headlines: 30 * 60 * 1000, // 30분
};

let currentLang = localStorage.getItem('kobot-lang') || 'ko';

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

function loadCache(key, ttlMs) {
    try {
        const raw = localStorage.getItem(key);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed?.ts || Date.now() - parsed.ts > ttlMs) return null;
        return parsed.data;
    } catch {
        return null;
    }
}

function saveCache(key, data) {
    try {
        localStorage.setItem(
            key,
            JSON.stringify({
                ts: Date.now(),
                data,
            })
        );
    } catch {
        // localStorage가 막힌 경우 무시
    }
}

function isFavorite(ticker) {
    return loadFavorites().includes(ticker);
}

function toggleFavorite(ticker) {
    const list = loadFavorites();
    const idx = list.indexOf(ticker);
    if (idx >= 0) {
        list.splice(idx, 1);
    } else {
        list.push(ticker);
    }
    saveFavorites(list);
    renderFavorites();
}

document.addEventListener('DOMContentLoaded', () => {
    applyLanguage(currentLang);

    const langSelect = document.getElementById('lang-select');
    if (langSelect) {
        langSelect.value = currentLang;
        langSelect.addEventListener('change', (e) => {
            currentLang = e.target.value;
            localStorage.setItem('kobot-lang', currentLang);
            applyLanguage(currentLang);
            fetchAndRenderPicks();
        });
    }

    const searchInput = document.getElementById('ticker-search');
    const searchBtn = document.getElementById('search-btn');
    const doSearch = () => {
        const val = searchInput?.value?.trim();
        if (!val) return;
        const isNumberCode = /^[0-9]{6}$/.test(val);
        const upper = isNumberCode ? `${val}.KS` : val.toUpperCase();
        const normalizedKey = upper.replace(/[^A-Z0-9가-힣]/g, '');

        // 1) 최근 picks에서 티커/이름 매칭
        const found = lastPicks.find(
            (p) =>
                p.ticker.toUpperCase() === upper ||
                p.name.toLowerCase().includes(val.toLowerCase())
        );
        // 2) 사전 매핑
        const mapped = NAME_TICKER_MAP[normalizedKey];

        const target = found?.ticker || mapped || upper;
        window.location.href = `detail.html?ticker=${encodeURIComponent(target)}`;
    };
    if (searchBtn && searchInput) {
        searchBtn.addEventListener('click', doSearch);
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') doSearch();
        });
    }

    // 초기 데이터 로딩
    renderCachedPicks();
    renderCachedSnapshot();
    renderCachedHeadlines();
    fetchAndRenderPicks();
    fetchSnapshot();
    fetchHeadlines();
    renderFavorites();

    // 주기적 갱신
    setInterval(fetchAndRenderPicks, REFRESH_MS);
    setInterval(fetchSnapshot, REFRESH_MS);
    setInterval(fetchHeadlines, REFRESH_MS * 3);
});

// fetch에 타임아웃을 걸어 API 지연 시 무한 대기하지 않도록 함
async function fetchWithTimeout(url, { timeout = REQUEST_TIMEOUT_MS, ...options } = {}) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    try {
        const response = await fetch(url, { ...options, signal: controller.signal });
        return response;
    } finally {
        clearTimeout(id);
    }
}

function renderPickSections(items, { usContainer, krContainer, etfContainer }) {
    if (!usContainer || !krContainer) return;

    usContainer.innerHTML = '';
    krContainer.innerHTML = '';
    if (etfContainer) etfContainer.innerHTML = '';
    usContainer.dataset.hasData = '1';
    krContainer.dataset.hasData = '1';
    if (etfContainer) etfContainer.dataset.hasData = '1';

    const renderCard = (target, item) => {
        const card = document.createElement('div');
        card.className = 'stock-card';
        card.setAttribute(
            'onclick',
            `location.href='detail.html?ticker=${encodeURIComponent(item.ticker)}'`
        );

        const rec = item.rec?.recommendation;
        const price = item.rec?.current_price;
        const buy = rec?.buy_price;
        const sell = rec?.sell_price;
        const action = rec?.action || 'HOLD';
        const currency = item.rec?.currency || (item.country === 'KR' ? 'KRW' : 'USD');
        const formattedPrice = formatPrice(price, currency);
        const formattedBuy = formatPrice(buy, currency);
        const formattedSell = formatPrice(sell, currency);

        card.innerHTML = `
            <div class="card-top">
                <div class="name top-name">${item.name}</div>
                <div class="badge">${item.country}</div>
                <button class="fav-btn" type="button">${isFavorite(item.ticker) ? '★' : '☆'}</button>
            </div>
            <div class="ticker subtle-ticker">${item.ticker}</div>
            <div class="price-block">
                <div class="price">${formattedPrice}</div>
                <div class="action ${action.toLowerCase()}">${action}</div>
            </div>
            <div class="targets">
                <div>Buy <span>${formattedBuy}</span></div>
                <div>Sell <span>${formattedSell}</span></div>
            </div>
            <div class="score">Score ${item.score}</div>
        `;
        target.appendChild(card);
        const favBtn = card.querySelector('.fav-btn');
        if (favBtn) {
            favBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleFavorite(item.ticker);
                const on = isFavorite(item.ticker);
                favBtn.textContent = on ? '★' : '☆';
            });
        }
    };

    const ensureByCountry = (country) => {
        const list = items.filter((p) => p.country === country);
        if (list.length >= 5) return list.slice(0, 5);
        const used = new Set(list.map((p) => p.ticker));
        const fallback = [];
        for (const f of FALLBACK_PICKS.filter((p) => p.country === country)) {
            if (!used.has(f.ticker)) {
                fallback.push(f);
            }
            if (list.length + fallback.length >= 5) break;
        }
        return list.concat(fallback).slice(0, 5);
    };

    ensureByCountry('US').forEach((p) => renderCard(usContainer, p));
    ensureByCountry('KR').forEach((p) => renderCard(krContainer, p));
    if (etfContainer) ensureByCountry('ETF').forEach((p) => renderCard(etfContainer, p));
}

function renderCachedPicks() {
    const loadingElement = document.getElementById('loading');
    const usPicksContainer = document.getElementById('us-picks');
    const krPicksContainer = document.getElementById('kr-picks');
    const etfPicksContainer = document.getElementById('etf-picks');
    const cached = loadCache(CACHE_KEYS.picks, CACHE_TTL_MS.picks);
    if (!cached || !cached.length || !usPicksContainer || !krPicksContainer) return;
    lastRenderedPicks = cached;
    lastPicks = cached.map(({ ticker, name }) => ({ ticker, name }));
    if (loadingElement) loadingElement.style.display = 'none';
    renderPickSections(cached, {
        usContainer: usPicksContainer,
        krContainer: krPicksContainer,
        etfContainer: etfPicksContainer,
    });
}

async function fetchAndRenderPicks() {
    const loadingElement = document.getElementById('loading');
    const usPicksContainer = document.getElementById('us-picks');
    const krPicksContainer = document.getElementById('kr-picks');
    const etfPicksContainer = document.getElementById('etf-picks');

    if (!loadingElement || !usPicksContainer || !krPicksContainer) return;

    loadingElement.style.display = 'block';
    loadingElement.innerText = TEXT[currentLang].loading;

    const hasExistingData = usPicksContainer.dataset.hasData === '1';
    if (!hasExistingData) {
        showSkeleton(usPicksContainer, 5);
        showSkeleton(krPicksContainer, 5);
        if (etfPicksContainer) showSkeleton(etfPicksContainer, 5);
    }

    try {
        const enriched = await getPicksWithRecommendations(PICKS_TIMEOUT_MS);
        lastRenderedPicks = enriched;
        lastPicks = enriched.map(({ ticker, name }) => ({ ticker, name }));
        saveCache(CACHE_KEYS.picks, enriched);
        renderPickSections(enriched, {
            usContainer: usPicksContainer,
            krContainer: krPicksContainer,
            etfContainer: etfPicksContainer,
        });
    } catch (error) {
        console.error('Error fetching picks:', error);
        const cached = loadCache(CACHE_KEYS.picks, CACHE_TTL_MS.picks);
        if (lastRenderedPicks.length) {
            lastPicks = lastRenderedPicks.map(({ ticker, name }) => ({ ticker, name }));
            renderPickSections(lastRenderedPicks, {
                usContainer: usPicksContainer,
                krContainer: krPicksContainer,
                etfContainer: etfPicksContainer,
            });
        } else if (cached?.length) {
            lastRenderedPicks = cached;
            lastPicks = cached.map(({ ticker, name }) => ({ ticker, name }));
            renderPickSections(cached, {
                usContainer: usPicksContainer,
                krContainer: krPicksContainer,
                etfContainer: etfPicksContainer,
            });
        } else {
            renderPickSections(FALLBACK_PICKS, {
                usContainer: usPicksContainer,
                krContainer: krPicksContainer,
                etfContainer: etfPicksContainer,
            });
            lastRenderedPicks = FALLBACK_PICKS;
            lastPicks = FALLBACK_PICKS.map(({ ticker, name }) => ({ ticker, name }));
        }
    } finally {
        loadingElement.style.display = 'none';
    }
}

// picks/full 우선 사용해 API 호출 수를 줄이고, 실패 시 기존 방식으로 폴백
async function getPicksWithRecommendations(timeoutMs = REQUEST_TIMEOUT_MS) {
    try {
        const resFull = await fetchWithTimeout(`${API_BASE_URL}/picks/full`, {
            timeout: timeoutMs,
        });
        if (resFull.ok) {
            const data = await resFull.json();
            if (Array.isArray(data) && data.length && data[0].rec) {
                lastPicks = data.map(({ ticker, name }) => ({ ticker, name }));
                return data;
            }
        }
    } catch (err) {
        console.warn('picks/full fallback -> individual calls', err);
    }

    // 기존 방식 폴백: picks 후 개별 recommendation 병렬 호출
    const response = await fetchWithTimeout(`${API_BASE_URL}/picks`, { timeout: timeoutMs });
    if (!response.ok) throw new Error('Failed to fetch Kobot Picks');
    const picks = await response.json();
    lastPicks = picks || [];

    const enriched = await Promise.all(
        picks.map(async (pick) => {
            try {
                const recRes = await fetchWithTimeout(
                    `${API_BASE_URL}/recommendation/${encodeURIComponent(pick.ticker)}`,
                    { timeout: timeoutMs }
                );
                if (!recRes.ok) {
                    throw new Error(`recommendation error: ${recRes.status}`);
                }
                const rec = await recRes.json();
                return { ...pick, rec };
            } catch (err) {
                console.error(`Error fetching recommendation for ${pick.ticker}:`, err);
                return { ...pick, rec: null };
            }
        })
    );
    return enriched;
}

async function renderFavorites() {
    const box = document.getElementById('favorites-list');
    if (!box) return;
    const favs = loadFavorites();
    if (!favs.length) {
        box.innerHTML = '<p class="muted">즐겨찾기한 종목이 없습니다.</p>';
        return;
    }
    box.innerHTML = '<div class="snapshot-skeleton"></div>';
    try {
        const results = await Promise.all(
            favs.map(async (ticker) => {
                const res = await fetchWithTimeout(
                    `${API_BASE_URL}/recommendation/${encodeURIComponent(ticker)}`,
                    { timeout: 12000 }
                );
                if (!res.ok) throw new Error(res.status);
                return await res.json();
            })
        );
        box.innerHTML = '';
        results.forEach((item) => {
            const currency = item.currency || 'USD';
            const formattedPrice = formatPrice(item.current_price, currency);
            const action = item.recommendation?.action || 'HOLD';
            const card = document.createElement('div');
            card.className = 'stock-card';
            card.setAttribute(
                'onclick',
                `location.href='detail.html?ticker=${encodeURIComponent(item.ticker)}'`
            );
            card.innerHTML = `
                <div class="card-top">
                    <div class="name top-name">${item.name}</div>
                    <div class="badge">${item.country}</div>
                    <button class="fav-btn" type="button">${isFavorite(item.ticker) ? '★' : '☆'}</button>
                </div>
                <div class="ticker subtle-ticker">${item.ticker}</div>
                <div class="price-block">
                    <div class="price">${formattedPrice}</div>
                    <div class="action ${action.toLowerCase()}">${action}</div>
                </div>
            `;
            box.appendChild(card);
            const favBtn = card.querySelector('.fav-btn');
            if (favBtn) {
                favBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    toggleFavorite(item.ticker);
                    const on = isFavorite(item.ticker);
                    favBtn.textContent = on ? '★' : '☆';
                });
            }
        });
    } catch (err) {
        console.error('favorites render error', err);
        box.innerHTML = '<p class="snapshot-error">즐겨찾기 목록을 불러오지 못했습니다.</p>';
    }
}

function formatPrice(value, currency = 'USD') {
    if (value === undefined || value === null || Number.isNaN(value)) return '-';
    try {
        if (currency === 'KRW') {
            return `${Math.round(value).toLocaleString('ko-KR')}원`;
        }
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 2,
        }).format(value);
    } catch {
        return currency === 'KRW' ? `₩${value}` : `$${value}`;
    }
}

function applyLanguage(lang) {
    const t = TEXT[lang] || TEXT.ko;
    const setText = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.innerText = text;
    };
    setText('section-us', t.us);
    setText('section-kr', t.kr);
    setText('section-etf', t.etf);
    setText('disclaimer', t.disclaimer);
    setText('hero-title', t.heroTitle);
    setText('hero-sub', t.heroSub);
    setText('loading', t.loading);
    setText('hero-live', t.live);
    setText('eyebrow-text', 'Kobot Pick');
}

function showSkeleton(container, count) {
    if (!container) return;
    const skeleton = [];
    for (let i = 0; i < count; i++) {
        skeleton.push(`
            <div class="stock-card skeleton">
                <div class="skeleton-line wide"></div>
                <div class="skeleton-line"></div>
                <div class="skeleton-line mid"></div>
                <div class="skeleton-line short"></div>
            </div>
        `);
    }
    container.innerHTML = skeleton.join('');
}

function renderSnapshotContent(box, data) {
    if (!box) return;
    box.dataset.hasData = '1';
    const entries = [
        { key: 'SPX', label: 'S&P 500' },
        { key: 'NASDAQ', label: 'Nasdaq' },
        { key: 'KOSPI', label: 'KOSPI' },
        { key: 'USDKRW', label: 'USD/KRW' },
    ];
    const html = entries
        .map((e) => {
            const v = data?.[e.key];
            if (!v) return '';
            const cls = v.change >= 0 ? 'pos' : 'neg';
            const price =
                e.key === 'USDKRW'
                    ? `${Math.round(v.price).toLocaleString('ko-KR')}원`
                    : v.price.toFixed(2);
            const pct = v.change_pct.toFixed(2);
            return `
                <div class="snapshot-item">
                    <div class="snap-label">${e.label}</div>
                    <div class="snap-value ${cls}">${price}</div>
                    <div class="snap-change ${cls}">
                        ${v.change >= 0 ? '+' : ''}${pct}%
                    </div>
                </div>
            `;
        })
        .join('');
    box.innerHTML = html || '<div class="snapshot-error">시장 지표 데이터를 불러오지 못했습니다.</div>';
}

function renderCachedSnapshot() {
    const box = document.getElementById('market-snapshot');
    const cached = loadCache(CACHE_KEYS.snapshot, CACHE_TTL_MS.snapshot);
    if (box && cached) {
        renderSnapshotContent(box, cached);
    }
}

async function fetchSnapshot() {
    const box = document.getElementById('market-snapshot');
    if (!box) return;
    const hasData = box.dataset.hasData === '1';
    if (!hasData) {
        box.innerHTML = '<div class="snapshot-skeleton"></div>';
    }
    try {
        const res = await fetchWithTimeout(`${API_BASE_URL}/market/snapshot`, { timeout: 12000 });
        if (!res.ok) throw new Error(`snapshot error ${res.status}`);
        const data = await res.json();
        saveCache(CACHE_KEYS.snapshot, data);
        renderSnapshotContent(box, data);
    } catch (err) {
        console.error('snapshot error', err);
        const cached = loadCache(CACHE_KEYS.snapshot, CACHE_TTL_MS.snapshot);
        if (cached) {
            renderSnapshotContent(box, cached);
        } else {
            box.innerHTML = '<div class="snapshot-error">시장 지표를 불러오지 못했습니다.</div>';
        }
    }
}

function renderHeadlinesContent(track, data) {
    if (!track) return;
    track.dataset.hasData = '1';
    const items = (data || [])
        .slice(0, 6)
        .map(
            (n) => `
            <a class="headline-item"
               href="${n.link}"
               target="_blank"
               rel="noopener noreferrer">
                ${n.title}
            </a>
        `
        )
        .join('');
    track.innerHTML = items || `<span class="headline-empty">${TEXT[currentLang].news}</span>`;
}

function renderCachedHeadlines() {
    const track = document.getElementById('headline-track');
    const cached = loadCache(CACHE_KEYS.headlines, CACHE_TTL_MS.headlines);
    if (track && cached?.length) {
        renderHeadlinesContent(track, cached);
    }
}

async function fetchHeadlines() {
    const track = document.getElementById('headline-track');
    if (!track) return;
    const hasData = track.dataset.hasData === '1';
    if (!hasData) {
        track.innerHTML = '';
    }
    try {
        const res = await fetchWithTimeout(`${API_BASE_URL}/market/headlines`, { timeout: 12000 });
        if (!res.ok) throw new Error(`headline error ${res.status}`);
        const data = await res.json();
        saveCache(CACHE_KEYS.headlines, data);
        renderHeadlinesContent(track, data);
    } catch (err) {
        console.error('headline error', err);
        const cached = loadCache(CACHE_KEYS.headlines, CACHE_TTL_MS.headlines);
        if (cached?.length) {
            renderHeadlinesContent(track, cached);
        } else {
            track.innerHTML = `<span class="headline-empty">뉴스를 불러오지 못했습니다.</span>`;
        }
    }
}
