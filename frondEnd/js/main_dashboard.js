// public/js/main_dashboard.js  ← 이 파일만 교체하면 끝!

const API_BASE = "https://kobotpick.onrender.com/api/v1";

async function wakeUp() {
    for (let i = 0; i < 5; i++) {
        try {
            await fetch("https://kobotpick.onrender.com/warmup", { cache: "no-store" });
            console.log("서버 깨움 성공");
            return;
        } catch {
            await new Promise(r => setTimeout(r, 3000));
        }
    }
}

async function fetchPicks() {
    const loading = document.getElementById('loading');
    loading.innerHTML = "실시간 데이터 불러오는 중... (최대 30초)";

    for (let i = 0; i < 6; i++) {
        try {
            const res = await fetch(`${API_BASE}/picks`, { cache: "no-store" });
            if (res.ok) {
                const data = await res.json();
                // 점수 평균이 65 이상이면 진짜 데이터로 판단
                const avgScore = data.reduce((a, b) => a + b.score, 0) / data.length;
                if (data.length > 0 && avgScore > 65) {
                    renderPicks(data);
                    loading.style.display = "none";
                    return;
                }
            }
        } catch (e) {
            console.log("시도 중...", e);
        }
        loading.innerHTML = `실시간 데이터 로딩... (${(i+1)*5}초 경과)`;
        await new Promise(r => setTimeout(r, 5000));
    }

    // 그래도 실패하면 최소한 보기 좋게
    loading.innerHTML = "서버가 느려 기본 데이터를 보여드려요<br>새로고침(F5) 해보세요";
    renderFallback();
}

function renderPicks(data) {
    ["us-picks", "kr-picks", "etf-picks"].forEach(id => {
        const container = document.getElementById(id);
        container.innerHTML = "";
        data.filter(p => 
            (id === "us-picks" && !p.ticker.includes(".KS") && p.country !== "ETF") ||
            (id === "kr-picks" && p.ticker.includes(".KS")) ||
            (id === "etf-picks" && p.country === "ETF")
        ).slice(0, 5).forEach(p => {
            const card = document.createElement("div");
            card.className = "stock-card";
            card.innerHTML = `
                <div class="card-header">
                    <div class="ticker">${p.ticker}</div>
                    <div class="score-badge">${p.score}</div>
                </div>
                <div class="company-name">${p.name || p.ticker}</div>
            `;
            card.onclick = () => location.href = `/detail.html?ticker=${p.ticker}`;
            container.appendChild(card);
        });
    });
}

function renderFallback() {
    const fallback = [
        {ticker:"NVDA",name:"NVIDIA",score:88,country:"US"},
        {ticker:"TSLA",name:"Tesla",score:83,country:"US"},
        {ticker:"005930.KS",name:"삼성전자",score:86,country:"KR"},
        {ticker:"000660.KS",name:"SK하이닉스",score:84,country:"KR"},
        {ticker:"QQQ",name:"Invesco QQQ",score:81,country:"ETF"},
    ];
    renderPicks(fallback);
}

// 페이지 로드 시 바로 실행
document.addEventListener("DOMContentLoaded", async () => {
    wakeUp();
    fetchPicks();
    setInterval(fetchPicks, 300000); // 5분마다 갱신
});