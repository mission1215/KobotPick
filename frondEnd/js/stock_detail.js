// kobotPick/frontEnd/js/stock_detail.js

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1/recommendation/';
const TEXT = {
    ko: { newsEmpty: '관련 뉴스를 불러올 수 없습니다.', profileEmpty: '기업 정보를 불러올 수 없습니다.' },
    en: { newsEmpty: 'No related news available.', profileEmpty: 'Company profile unavailable.' },
    ja: { newsEmpty: '関連ニュースを取得できませんでした。', profileEmpty: '企業情報を取得できませんでした。' },
    zh: { newsEmpty: '无法获取相关新闻。', profileEmpty: '无法获取公司信息。' },
};
let currentLang = localStorage.getItem('kobot-lang') || 'ko';

document.addEventListener('DOMContentLoaded', () => {
    const langSelect = document.getElementById('lang-select-detail');
    if (langSelect) {
        langSelect.value = currentLang;
        langSelect.addEventListener('change', (e) => {
            currentLang = e.target.value;
            localStorage.setItem('kobot-lang', currentLang);
            fetchStockData();
        });
    }
    fetchStockData();
});

async function fetchStockData() {
    const urlParams = new URLSearchParams(window.location.search);
    const ticker = urlParams.get('ticker') || 'AAPL';

    const loadingElement = document.getElementById('loading');
    const contentElement = document.getElementById('content');
    const skeleton = document.getElementById('skeleton-detail');
    loadingElement.style.display = 'block';
    skeleton.style.display = 'block';
    contentElement.style.display = 'none';

    try {
        const response = await fetch(API_BASE_URL + ticker);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || `HTTP error! status: ${response.status}`);
        }

        renderData(data);
    } catch (error) {
        console.error("Error fetching data:", error);
        loadingElement.innerHTML = `데이터 로딩 실패: ${error.message}. 티커: ${ticker}`;
        skeleton.style.display = 'none';
        return;
    } finally {
        loadingElement.style.display = 'none';
        skeleton.style.display = 'none';
        contentElement.style.display = 'block';
    }
}

function renderData(data) {
    document.getElementById('company-name').innerText = data.name;
    document.getElementById('ticker-pill').innerText = data.ticker;
    const friendlyDate = formatDateFriendly(data.last_updated);
    const currency = data.currency || 'USD';
    document.getElementById('current-price').innerText = `${data.name} | 현재가: ${formatPrice(data.current_price, currency)} | 업데이트: ${friendlyDate}`;

    const rec = data.recommendation;
    document.getElementById('buy-price').innerText = `${formatPrice(rec.buy_price, currency)}`;
    document.getElementById('sell-price').innerText = `${formatPrice(rec.sell_price, currency)}`;
    document.getElementById('stop-loss').innerText = `${formatPrice(rec.stop_loss, currency)}`;
    document.getElementById('action').innerText = rec.action;
    document.getElementById('rationale-text').innerText = rec.rationale;

    renderFundamentals(data.fundamentals);
    renderProfile(data.profile);
    renderNews(data.news);

    // 차트는 DOM이 표시된 이후 렌더링 (display none 상태에서 렌더하면 width=0 이슈)
    requestAnimationFrame(() => renderCandleChart(data.ticker, data.historical));
}

function renderFundamentals(fundamentals) {
    const grid = document.getElementById('fundamentals-grid');
    const items = [
        { label: '시가총액', value: formatNumber(fundamentals?.market_cap) },
        { label: '배당수익률', value: formatPercent(fundamentals?.dividend_yield) },
        { label: 'PER', value: formatNumber(fundamentals?.per, 2) },
        { label: 'PBR', value: formatNumber(fundamentals?.pbr, 2) },
        { label: 'ROE', value: formatPercent(fundamentals?.roe) },
        { label: 'PSR', value: formatNumber(fundamentals?.psr, 2) },
    ];

    grid.innerHTML = items.map(({ label, value }) => `
        <div class="grid-item">
            <span class="grid-label">${label}</span>
            <span class="grid-value">${value}</span>
        </div>
    `).join('');
}

function formatNumber(val, digits = 1) {
    if (val === null || val === undefined) return '-';
    if (Math.abs(val) >= 1e12) return (val / 1e12).toFixed(digits) + 'T';
    if (Math.abs(val) >= 1e9) return (val / 1e9).toFixed(digits) + 'B';
    if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(digits) + '억'; // KR flavor
    if (Math.abs(val) >= 1e6) return (val / 1e6).toFixed(digits) + 'M';
    return Number(val).toFixed(digits);
}

function formatPercent(val, digits = 2) {
    if (val === null || val === undefined) return '-';
    return (val * 100).toFixed(digits) + '%';
}

function renderNews(newsItems) {
    const list = document.getElementById('news-list');
    if (!newsItems || newsItems.length === 0) {
        list.innerHTML = `<li class="news-empty">${TEXT[currentLang].newsEmpty}</li>`;
        return;
    }
    list.innerHTML = newsItems.map(n => `
        <li class="news-item">
            <a href="${n.link}" target="_blank" rel="noopener noreferrer">${n.title}</a>
            <div class="news-meta">${n.publisher || ''} ${formatTime(n.published_at)}</div>
        </li>
    `).join('');
}

function formatTime(ts) {
    if (!ts) return '';
    const t = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
    return t.toISOString().slice(0,16).replace('T',' ');
}

function renderProfile(profile) {
    const list = document.getElementById('profile-list');
    if (!profile) {
        list.innerHTML = `<li class="news-empty">${TEXT[currentLang].profileEmpty}</li>`;
        return;
    }
    const fields = [
        { label: '섹터', value: profile.sector },
        { label: '산업', value: profile.industry },
        { label: '직원수', value: profile.employees ? profile.employees.toLocaleString() : null },
        { label: '거래소', value: profile.exchange },
        { label: '통화', value: profile.currency },
        { label: '웹사이트', value: profile.website, link: true },
        { label: '개요', value: profile.summary }
    ].filter(item => item.value);

    if (fields.length === 0) {
        list.innerHTML = `<li class="news-empty">${TEXT[currentLang].profileEmpty}</li>`;
        return;
    }

    list.innerHTML = fields.map(f => `
        <li class="profile-item">
            <span class="profile-label">${f.label}</span>
            <span class="profile-value">
                ${f.link ? `<a href="${f.value}" target="_blank" rel="noopener noreferrer">${f.value}</a>` : f.value}
            </span>
        </li>
    `).join('');
}

function formatPrice(value, currency = 'USD') {
    if (value === undefined || value === null || Number.isNaN(value)) return '-';
    try {
        if (currency === 'KRW') {
            return `${Math.round(value).toLocaleString('ko-KR')}원`;
        }
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value);
    } catch {
        return currency === 'KRW' ? `₩${value}` : `$${value}`;
    }
}

function formatDateFriendly(isoString) {
    if (!isoString) return '';
    const d = new Date(isoString);
    const datePart = d.toLocaleDateString('ko-KR', { year: 'numeric', month: 'short', day: 'numeric' });
    const timePart = d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
    return `${datePart} ${timePart}`;
}
