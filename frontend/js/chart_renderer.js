// kobotPick/frontEnd/js/chart_renderer.js

function renderCandleChart(ticker, historicalData) {
    const chartContainer = document.getElementById('chart-area');
    chartContainer.innerHTML = ''; // 초기화

    if (!historicalData || historicalData.length === 0) {
        chartContainer.innerText = "차트 데이터를 불러올 수 없습니다.";
        return;
    }

    // Lightweight Charts를 사용한 캔들 차트 렌더링
    const chart = LightweightCharts.createChart(chartContainer, {
        width: chartContainer.clientWidth,
        height: chartContainer.clientHeight,
        layout: { backgroundColor: '#0d1117', textColor: '#E0E0E0' },
        grid: {
            vertLines: { color: 'rgba(255,255,255,0.05)' },
            horzLines: { color: 'rgba(255,255,255,0.05)' },
        },
        timeScale: {
            timeVisible: true,
            secondsVisible: false,
            barSpacing: 6,       // 캔들 간격
            rightOffset: 0,      // 오른쪽 여백 최소화
            fixLeftEdge: true,
            fixRightEdge: true,
        },
        rightPriceScale: { borderVisible: false },
    });

    const candleSeries = chart.addCandlestickSeries({
        upColor: '#00BCD4',
        downColor: '#FF6F61',
        borderVisible: false,
        wickUpColor: '#00BCD4',
        wickDownColor: '#FF6F61',
    });

    const chartData = historicalData.map(d => ({
        time: d.date.split('T')[0], // 날짜만 사용
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
    }));
    candleSeries.setData(chartData);
    chart.timeScale().fitContent();
    chart.timeScale().scrollToPosition(-5, false); // 오른쪽 치우침 완화

    // 리사이즈 대응
    window.addEventListener('resize', () => {
        chart.applyOptions({ width: chartContainer.clientWidth });
    });
}
