// kobotPick/frontEnd/js/stock_detail.js

// 1) 공통 API Base URL (배포/로컬 둘 다 지원)
const API_BASE_URL =
  (window.KOBOT_API_BASE_URL?.replace(/\/+$/, "")) ||
  "http://127.0.0.1:8000/api/v1";

const FAVORITES_KEY = "kobot-favorites";

const TEXT = {
    ko: {
        newsEmpty: "관련 뉴스를 불러올 수 없습니다.",
        profileEmpty: "기업 정보를 불러올 수 없습니다.",
    },
    en: {
        newsEmpty: "No related news available.",
        profileEmpty: "Company profile unavailable.",
    },
    ja: {
        newsEmpty: "関連ニュースを取得できませんでした。",
        profileEmpty: "企業情報を取得できませんでした。",
    },
    zh: {
        newsEmpty: "无法获取相关新闻。",
        profileEmpty: "无法获取公司信息。",
    },
};

let currentLang = localStorage.getItem("kobot-lang") || "ko";

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

function toggleFavorite(ticker, btn) {
    const list = loadFavorites();
    const idx = list.indexOf(ticker);
    if (idx >= 0) {
        list.splice(idx, 1);
    } else {
        list.push(ticker);
    }
    saveFavorites(list);
    if (btn) {
        const on = isFavorite(ticker);
        btn.textContent = on ? "★ 즐겨찾기" : "☆ 즐겨찾기";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const langSelect = document.getElementById("lang-select-detail");
    if (langSelect) {
        langSelect.value = currentLang;
        langSelect.addEventListener("change", (e) => {
            currentLang = e.target.value;
            localStorage.setItem("kobot-lang", currentLang);
            fetchStockData();
        });
    }
    fetchStockData();
});

async function fetchStockData() {
    const urlParams = new URLSearchParams(window.location.search);
    // ?ticker=TSLA 또는 ?symbol=TSLA 둘 다 대응
    const ticker =
        urlParams.get("ticker") ||
        urlParams.get("symbol") ||
        "AAPL";

    const loadingElement = document.getElementById("loading");
    const contentElement = document.getElementById("content");
    const skeleton = document.getElementById("skeleton-detail");

    if (loadingElement) loadingElement.style.display = "block";
    if (skeleton) skeleton.style.display = "block";
    if (contentElement) contentElement.style.display = "none";

    try {
        const res = await fetch(
            `${API_BASE_URL}/recommendation/${encodeURIComponent(ticker)}`
        );

        let data = null;
        try {
            data = await res.json();
        } catch {
            // JSON 파싱 실패해도 에러 메시지는 아래에서 처리
        }

        if (!res.ok) {
            const msg =
                (data && (data.detail || data.message)) ||
                `HTTP error! status: ${res.status}`;
            throw new Error(msg);
        }

        renderData(data);
    } catch (error) {
        console.error("Error fetching data:", error);
        if (loadingElement) {
            loadingElement.innerHTML = `데이터 로딩 실패: ${error.message}. 티커: ${ticker}`;
        }
        if (skeleton) skeleton.style.display = "none";
        if (contentElement) contentElement.style.display = "none";
        return;
    } finally {
        if (loadingElement) loadingElement.style.display = "none";
        if (skeleton) skeleton.style.display = "none";
        if (contentElement) contentElement.style.display = "block";
    }
}

function renderData(data) {
    document.getElementById("company-name").innerText = data.name;
    document.getElementById("ticker-pill").innerText = data.ticker;
    const favBtn = document.getElementById("fav-toggle");
    if (favBtn) {
        const on = isFavorite(data.ticker);
        favBtn.textContent = on ? "★ 즐겨찾기" : "☆ 즐겨찾기";
        favBtn.onclick = (e) => {
            e.preventDefault();
            toggleFavorite(data.ticker, favBtn);
        };
    }

    const friendlyDate = formatDateFriendly(data.last_updated);
    const currency = data.currency || "USD";

    document.getElementById(
        "current-price"
    ).innerText = `${data.name} | 현재가: ${formatPrice(
        data.current_price,
        currency
    )} | 업데이트: ${friendlyDate}`;

    const rec = data.recommendation;
    document.getElementById("buy-price").innerText = `${formatPrice(
        rec.buy_price,
        currency
    )}`;
    document.getElementById("sell-price").innerText = `${formatPrice(
        rec.sell_price,
        currency
    )}`;
    document.getElementById("stop-loss").innerText = `${formatPrice(
        rec.stop_loss,
        currency
    )}`;
    document.getElementById("action").innerText = rec.action;
    document.getElementById("rationale-text").innerText = rec.rationale;

    renderFundamentals(data.fundamentals);
    renderProfile(data.profile);
    renderNews(data.news);

    // 차트는 DOM 표시 후 렌더링
    requestAnimationFrame(() =>
        renderCandleChart(data.ticker, data.historical)
    );
}

function renderFundamentals(fundamentals) {
    const grid = document.getElementById("fundamentals-grid");
    const items = [
        { label: "시가총액", value: formatNumber(fundamentals?.market_cap) },
        { label: "배당수익률", value: formatPercent(fundamentals?.dividend_yield) },
        { label: "PER", value: formatNumber(fundamentals?.per, 2) },
        { label: "PBR", value: formatNumber(fundamentals?.pbr, 2) },
        { label: "ROE", value: formatPercent(fundamentals?.roe) },
        { label: "PSR", value: formatNumber(fundamentals?.psr, 2) },
    ];

    grid.innerHTML = items
        .map(
            ({ label, value }) => `
        <div class="grid-item">
            <span class="grid-label">${label}</span>
            <span class="grid-value">${value}</span>
        </div>
    `
        )
        .join("");
}

function formatNumber(val, digits = 1) {
    if (val === null || val === undefined) return "-";
    if (Math.abs(val) >= 1e12) return (val / 1e12).toFixed(digits) + "T";
    if (Math.abs(val) >= 1e9) return (val / 1e9).toFixed(digits) + "B";
    if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(digits) + "억"; // KR flavor
    if (Math.abs(val) >= 1e6) return (val / 1e6).toFixed(digits) + "M";
    return Number(val).toFixed(digits);
}

function formatPercent(val, digits = 2) {
    if (val === null || val === undefined) return "-";
    return (val * 100).toFixed(digits) + "%";
}

function renderNews(newsItems) {
    const list = document.getElementById("news-list");
    if (!newsItems || newsItems.length === 0) {
        list.innerHTML = `<li class="news-empty">${TEXT[currentLang].newsEmpty}</li>`;
        return;
    }
    list.innerHTML = newsItems
        .map(
            (n) => `
        <li class="news-item">
            <a href="${n.link}" target="_blank" rel="noopener noreferrer">${n.title}</a>
            <div class="news-meta">${
                n.publisher || ""
            } ${formatTime(n.published_at)}</div>
        </li>
    `
        )
        .join("");
}

function formatTime(ts) {
    if (!ts) return "";
    const t = typeof ts === "number" ? new Date(ts * 1000) : new Date(ts);
    return t.toISOString().slice(0, 16).replace("T", " ");
}

function renderProfile(profile) {
    const list = document.getElementById("profile-list");
    if (!profile) {
        list.innerHTML = `<li class="news-empty">${TEXT[currentLang].profileEmpty}</li>`;
        return;
    }
    const fields = [
        { label: "섹터", value: profile.sector },
        { label: "산업", value: profile.industry },
        {
            label: "직원수",
            value: profile.employees
                ? profile.employees.toLocaleString()
                : null,
        },
        { label: "거래소", value: profile.exchange },
        { label: "통화", value: profile.currency },
        { label: "웹사이트", value: profile.website, link: true },
        { label: "개요", value: profile.summary },
    ].filter((item) => item.value);

    if (fields.length === 0) {
        list.innerHTML = `<li class="news-empty">${TEXT[currentLang].profileEmpty}</li>`;
        return;
    }

    list.innerHTML = fields
        .map(
            (f) => `
        <li class="profile-item">
            <span class="profile-label">${f.label}</span>
            <span class="profile-value">
                ${
                    f.link
                        ? `<a href="${f.value}" target="_blank" rel="noopener noreferrer">${f.value}</a>`
                        : f.value
                }
            </span>
        </li>
    `
        )
        .join("");
}

function formatPrice(value, currency = "USD") {
    if (value === undefined || value === null || Number.isNaN(value))
        return "-";
    try {
        if (currency === "KRW") {
            return `${Math.round(value).toLocaleString("ko-KR")}원`;
        }
        return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: "USD",
            maximumFractionDigits: 2,
        }).format(value);
    } catch {
        return currency === "KRW" ? `₩${value}` : `$${value}`;
    }
}

function formatDateFriendly(isoString) {
    if (!isoString) return "";
    const d = new Date(isoString);
    const datePart = d.toLocaleDateString("ko-KR", {
        year: "numeric",
        month: "short",
        day: "numeric",
    });
    const timePart = d.toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit",
    });
    return `${datePart} ${timePart}`;
}
