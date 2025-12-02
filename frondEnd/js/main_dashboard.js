// kobotPick/frontEnd/js/main_dashboard.js

// API Base URL: 배포/로컬 모두 대응 & 끝의 슬래시 제거
const API_BASE_URL = (
  window.KOBOT_API_BASE_URL ||
  "https://kobotpick.onrender.com/api/v1/"
).replace(/\/+$/, ""); 

const REFRESH_MS = 60000; // 1분마다 새로고침 (유사 실시간)

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

let currentLang = localStorage.getItem('kobot-lang') || 'ko';

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

    // 초기 데이터 로딩
    fetchAndRenderPicks();
    fetchSnapshot();
    fetchHeadlines();

    // 주기적 갱신
    setInterval(fetchAndRenderPicks, REFRESH_MS);
    setInterval(fetchSnapshot, REFRESH_MS);
    setInterval(fetchHeadlines, REFRESH_MS * 3);
});

async function fetchAndRenderPicks() {
    const loadingElement = document.getElementById('loading');
    const usPicksContainer = document.getElementById('us-picks');
    const krPicksContainer = document.getElementById('kr-picks');
    const etfPicksContainer = document.getElementById('etf-picks');

    if (!loadingElement || !usPicksContainer || !krPicksContainer) return;

    loadingElement.style.display = 'block';
    loadingElement.innerText = TEXT[currentLang].loading;

    showSkeleton(usPicksContainer, 5);
    showSkeleton(krPicksContainer, 5);
    if (etfPicksContainer) showSkeleton(etfPicksContainer, 5);

    try {
        // 메인 picks 호출
        const response = await fetch(`${API_BASE_URL}/picks`);
        if (!response.ok) throw new Error('Failed to fetch Kobot Picks');
        const picks = await response.json();

        // 상세 추천 데이터 병렬 호출
        const enriched = await Promise.all(
            picks.map(async (pick) => {
                try {
                    const recRes = await fetch(
                        `${API_BASE_URL}/recommendation/${encodeURIComponent(pick.ticker)}`
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

        // 섹션 클리어
        usPicksContainer.innerHTML = '';
        krPicksContainer.innerHTML = '';
        if (etfPicksContainer) etfPicksContainer.innerHTML = '';

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
        };

        enriched
            .filter((p) => p.country === 'US')
            .forEach((p) => renderCard(usPicksContainer, p));
        enriched
            .filter((p) => p.country === 'KR')
            .forEach((p) => renderCard(krPicksContainer, p));
        enriched
            .filter((p) => p.country === 'ETF')
            .forEach((p) => etfPicksContainer && renderCard(etfPicksContainer, p));
    } catch (error) {
        console.error('Error fetching picks:', error);
        usPicksContainer.innerHTML =
            `<p style="color:red; text-align: center;">추천 목록 로드 실패: ${error.message}</p>`;
        krPicksContainer.innerHTML = '';
        if (etfPicksContainer) etfPicksContainer.innerHTML = '';
    } finally {
        loadingElement.style.display = 'none';
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

async function fetchSnapshot() {
    const box = document.getElementById('market-snapshot');
    if (!box) return;
    box.innerHTML = '<div class="snapshot-skeleton"></div>';
    try {
        const res = await fetch(`${API_BASE_URL}/market/snapshot`);
        if (!res.ok) throw new Error(`snapshot error ${res.status}`);
        const data = await res.json();
        const entries = [
            { key: 'SPX', label: 'S&P 500' },
            { key: 'NASDAQ', label: 'Nasdaq' },
            { key: 'KOSPI', label: 'KOSPI' },
            { key: 'USDKRW', label: 'USD/KRW' },
        ];
        box.innerHTML = entries
            .map((e) => {
                const v = data[e.key];
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
    } catch (err) {
        console.error('snapshot error', err);
        box.innerHTML = '<div class="snapshot-error">시장 지표를 불러오지 못했습니다.</div>';
    }
}

async function fetchHeadlines() {
    const track = document.getElementById('headline-track');
    if (!track) return;
    track.innerHTML = '';
    try {
        const res = await fetch(`${API_BASE_URL}/market/headlines`);
        if (!res.ok) throw new Error(`headline error ${res.status}`);
        const data = await res.json();
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
        track.innerHTML =
            items || `<span class="headline-empty">${TEXT[currentLang].news}</span>`;
    } catch (err) {
        console.error('headline error', err);
        track.innerHTML = `<span class="headline-empty">뉴스를 불러오지 못했습니다.</span>`;
    }
}