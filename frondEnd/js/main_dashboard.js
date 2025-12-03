// public/js/main_dashboard.js  ← 이 파일에 통째로 덮어쓰기!

const API_BASE_URL = "https://kobotpick.onrender.com/api/v1";
const FAVORITES_KEY = 'kobot-favorites';

setTimeout(() => {
    fetch("https://kobotpick.onrender.com/warmup").catch(()=> {});
}, 1000);
setTimeout(() => {
    fetch("https://kobotpick.onrender.com/warmup").catch(()=> {});
}, 6000);

// 1. 서버 깨우기 (최대 6번 시도)
async function wakeUpServer() {
    for (let i = 0; i < 6; i++) {
        try {
            await fetch("https://kobotpick.onrender.com/warmup", { cache: "no-store" });
            console.log("서버 깨움 성공");
            return;
        } catch (e) {
            console.log(`웨이크업 시도 ${i + 1}/6`);
            await new Promise(r => setTimeout(r, 4000));
        }
    }
}

// 2. 실제 추천 목록 가져오기 (최대 40초까지 기다림)
async function fetchPicks() {
    const loading = document.getElementById('loading');
    
    for (let attempt = 1; attempt <= 8; attempt++) {
        try {
            const res = await fetch(`${API_BASE_URL}/picks`, { cache: "no-store" });
            if (res.ok) {
                const data = await res.json();
                // 점수가 전부 50이면 아직 진짜 데이터 아님 → 다시 시도
                const allFifty = data.every(p => p.score === 50);
                if (data.length > 0 && !allFifty) {
                    renderPicks(data);
                    loading.style.display = "none";
                    return;
                }
            }
        } catch (e) {
            console.log(`추천 데이터 시도 ${attempt}/8 실패`);
        }
        loading.innerHTML = `서버 깨우는 중... (${attempt * 5}초 경과)<br>조금만 더 기다려 주세요`;
        await new Promise(r => setTimeout(r, 5000));
    }

    // 40초 넘어도 안 되면 fallback
    console.warn("실제 데이터 실패 → fallback 데이터 표시");
    renderFallbackPicks();
    loading.innerHTML = "서버가 느려 기본 데이터를 보여드려요<br>새로고침(F5) 해보세요";
}

// 3. 실제 데이터 렌더링
function renderPicks(picks) {
    const us = document.getElementById('us-picks');
    const kr = document.getElementById('kr-picks');
    const etf = document.getElementById('etf-picks');

    us.innerHTML = ''; kr.innerHTML = ''; etf.innerHTML = '';

    picks.forEach(p => {
        const card = createStockCard(p);
        if (p.country === 'US') us.appendChild(card);
        else if (p.country === 'KR') kr.appendChild(card);
        else if (p.country === 'ETF') etf.appendChild(card);
    });
}

// 4. fallback 데이터 (점수 50도 예쁘게 보여주기
function renderFallbackPicks() {
    const fallback = [
        {ticker:"NVDA",name:"NVIDIA Corp.",country:"US",score:87},
        {ticker:"TSLA",name:"Tesla, Inc.",country:"US",score:82},
        {ticker:"AAPL",name:"Apple Inc.",country:"US",score:79},
        {ticker:"MSFT",name:"Microsoft",country:"US",score:76},
        {ticker:"AMZN",name:"Amazon",country:"US",score:74},
        {ticker:"005930.KS",name:"삼성전자",country:"KR",score:85},
        {ticker:"000660.KS",name:"SK하이닉스",country:"KR",score:83},
        {ticker:"035420.KS",name:"NAVER",country:"KR",score:78},
        {ticker:"005380.KS",name:"현대차",country:"KR",score:75},
        {ticker:"000270.KS",name:"기아",country:"KR",score:73},
        {ticker:"SPY",name:"SPDR S&P 500",country:"ETF",score:80},
        {ticker:"QQQ",name:"Invesco QQQ",country:"ETF",score:82},
        {ticker:"TIGER",name:"TIGER 미국테크TOP10",country:"ETF",score:79},
    ];
    renderPicks(fallback);
}

// 5. 카드 하나 만들기
function createStockCard(p) {
    const card = document.createElement('div');
    card.className = 'stock-card';
    card.innerHTML = `
        <div class="card-header">
            <div class="ticker">${p.ticker}</div>
            <div class="score-badge">${p.score}</div>
        </div>
        <div class="company-name">${p.name}</div>
        <div class="country-flag">${p.country==='US'?'US':p.country==='KR'?'KR':'ETF'}</div>
    `;
    card.onclick = () => location.href = `/detail.html?ticker=${p.ticker}`;
    return card;
}

// 6. 시장 지표 & 뉴스 (간단히)
async function fetchSnapshot() {
    try {
        const res = await fetch(`${API_BASE_URL}/market/snapshot`);
        if (res.ok) {
            const data = await res.json();
            document.getElementById('market-snapshot').innerHTML = `
                <div>S&P 500: ${data.SPX?.price?.toFixed(2) ?? '-'} (${data.SPX?.change_pct?.toFixed(2) ?? '0'}%)</div>
                <div>NASDAQ: ${data.NASDAQ?.price?.toFixed(2) ?? '-'} (${data.NASDAQ?.change_pct?.toFixed(2) ?? '0'}%)</div>
                <div>KOSPI: ${data.KOSPI?.price?.toFixed(0) ?? '-'} (${data.KOSPI?.change_pct?.toFixed(2) ?? '0'}%)</div>
                <div>USD/KRW: ${data.USDKRW?.price?.toFixed(0) ?? '-'}원</div>
            `;
        }
    } catch (e) {}
}

async function fetchHeadlines() {
    try {
        const res = await fetch(`${API_BASE_URL}/market/headlines`);
        if (res.ok) {
            const news = await res.json();
            const track = document.getElementById('headline-track');
            track.innerHTML = news.map(n => `<a href="${n.link}" target="_blank">${n.title}</a>`).join(' · ');
        }
    } catch (e) {}
}

// 검색 기능
document.getElementById('search-btn').onclick = () => {
    const query = document.getElementById('ticker-search').value.trim().toUpperCase();
    if (query) location.href = `/detail.html?ticker=${query}`;
};
document.getElementById('ticker-search').onkeypress = e => {
    if (e.key === 'Enter') document.getElementById('search-btn').click();
};

// 페이지 로드 완료 후 실행
document.addEventListener("DOMContentLoaded", async () => {
    wakeUpServer();
    fetchSnapshot();
    fetchHeadlines();
    fetchPicks();

    // 3분마다 자동 갱신
    setInterval(() => {
        fetchPicks();
        fetchSnapshot();
        fetchHeadlines();
    }, 180000);
});