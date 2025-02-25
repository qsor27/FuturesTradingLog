function initChart(containerId, tradeId) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error('Chart container not found');
        return;
    }

    const width = container.clientWidth;
    const height = container.clientHeight;
    
    const chart = createChart(container, {
        width: width,
        height: height,
        layout: {
            background: { type: 'solid', color: '#ffffff' },
            textColor: '#333',
        },
        grid: {
            vertLines: { color: '#f0f0f0' },
            horzLines: { color: '#f0f0f0' },
        },
        crosshair: {
            mode: 'normal',
        },
        rightPriceScale: {
            borderColor: '#dcddde',
        },
        timeScale: {
            borderColor: '#dcddde',
            timeVisible: true,
            secondsVisible: false
        },
    });
    
    const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderVisible: false,
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350'
    });
    
    // Load the market data
    fetch(`/trade/${tradeId}/market-data`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Error loading market data:', data.error);
                return;
            }

            console.log('Received market data:', data);

            // Convert the market data to the format expected by lightweight-charts
            const chartData = data.market_data.map(bar => ({
                time: new Date(bar.timestamp).getTime() / 1000,
                open: bar.open,
                high: bar.high,
                low: bar.low,
                close: bar.close
            }));

            // Set the candlestick data
            candlestickSeries.setData(chartData);

            // Add trade markers
            const tradeTime = new Date(data.trade_time).getTime() / 1000;
            candlestickSeries.setMarkers([
                {
                    time: tradeTime,
                    position: 'aboveBar',
                    color: '#2196F3',
                    shape: 'arrowDown',
                    text: 'TRADE'
                }
            ]);

            // Fit content
            chart.timeScale().fitContent();
        })
        .catch(error => {
            console.error('Error loading trade data:', error);
        });

    return chart;
}