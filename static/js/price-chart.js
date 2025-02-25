// Initialize lightweight charts
function initPriceChart(tradeId) {
    const chartContainer = document.getElementById('chart-container');
    if (!chartContainer) return;

    // Create chart with updated options
    const chart = LightweightCharts.createChart(chartContainer, {
        width: chartContainer.clientWidth,
        height: chartContainer.clientHeight,
        layout: {
            background: { color: '#ffffff' },
            textColor: '#333',
        },
        grid: {
            vertLines: { color: '#f0f0f0' },
            horzLines: { color: '#f0f0f0' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                labelBackgroundColor: '#333',
            },
            horzLine: {
                labelBackgroundColor: '#333',
            },
        },
        rightPriceScale: {
            borderColor: '#d1d5db',
            scaleMargins: {
                top: 0.2,  // Increased for marker space
                bottom: 0.2,
            },
            autoScale: true,
        },
        timeScale: {
            borderColor: '#d1d5db',
            timeVisible: true,
            secondsVisible: false,
            tickMarkFormatter: (time) => {
                const date = new Date(time * 1000);
                return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            },
        },
        localization: {
            timeFormatter: (time) => {
                const date = new Date(time * 1000);
                return date.toLocaleString([], {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                });
            },
            priceFormatter: price => price.toFixed(2),
        },
    });

    // Create candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderUpColor: '#26a69a',
        borderDownColor: '#ef5350',
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350',
    });

    // Load initial data and setup trade markers
    fetch(`/trade/${tradeId}/market-data`)
        .then(response => response.json())
        .then(data => {
            if (data.bars && Array.isArray(data.bars)) {
                // Convert timestamps to seconds for chart
                const chartData = data.bars.map(bar => ({
                    time: new Date(bar.time).getTime() / 1000,
                    open: bar.open,
                    high: bar.high,
                    low: bar.low,
                    close: bar.close
                }));

                // Set chart data
                candlestickSeries.setData(chartData);

                // Add trade markers and price lines
                const tradeInfo = data.trade;
                if (tradeInfo) {
                    const markers = [];
                    const isLong = tradeInfo.side_of_market === 'Long';
                    const entryTime = new Date(tradeInfo.entry_time).getTime() / 1000;
                    
                    // Entry marker
                    markers.push({
                        time: entryTime,
                        position: isLong ? 'belowBar' : 'aboveBar',
                        color: isLong ? '#26a69a' : '#ef5350',
                        shape: isLong ? 'arrowUp' : 'arrowDown',
                        text: `Entry ${tradeInfo.entry_price}`,
                        size: 3,
                    });

                    // Entry price line
                    candlestickSeries.createPriceLine({
                        price: tradeInfo.entry_price,
                        color: isLong ? '#26a69a' : '#ef5350',
                        lineWidth: 2,
                        lineStyle: LightweightCharts.LineStyle.Dotted,
                        axisLabelVisible: true,
                        title: `Entry ${tradeInfo.entry_price}`,
                    });

                    // Exit marker and price line (if trade is closed)
                    if (tradeInfo.exit_time) {
                        const exitTime = new Date(tradeInfo.exit_time).getTime() / 1000;
                        markers.push({
                            time: exitTime,
                            position: isLong ? 'aboveBar' : 'belowBar',
                            color: isLong ? '#ef5350' : '#26a69a',
                            shape: isLong ? 'arrowDown' : 'arrowUp',
                            text: `Exit ${tradeInfo.exit_price}`,
                            size: 3,
                        });

                        candlestickSeries.createPriceLine({
                            price: tradeInfo.exit_price,
                            color: isLong ? '#ef5350' : '#26a69a',
                            lineWidth: 2,
                            lineStyle: LightweightCharts.LineStyle.Dotted,
                            axisLabelVisible: true,
                            title: `Exit ${tradeInfo.exit_price}`,
                        });

                        // Set visible range to include both entry and exit plus margin
                        const timeRange = {
                            from: entryTime - 900,  // 15 minutes before entry
                            to: exitTime + 900,     // 15 minutes after exit
                        };
                        chart.timeScale().setVisibleRange(timeRange);
                    }

                    // Set the markers
                    candlestickSeries.setMarkers(markers);

                    // Ensure price scale shows all markers
                    chart.timeScale().fitContent();
                }
            }
        })
        .catch(error => {
            console.error('Error loading chart data:', error);
        });

    // Enhanced tooltip
    chart.subscribeCrosshairMove(param => {
        if (param.time) {
            const price = param.seriesPrices.get(candlestickSeries);
            if (price) {
                const date = new Date(param.time * 1000);
                const tooltip = document.getElementById('chart-tooltip');
                if (tooltip) {
                    tooltip.innerHTML = `
                        <div class="font-bold text-gray-700">
                            ${date.toLocaleString([], {
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit'
                            })}
                        </div>
                        <div class="grid grid-cols-2 gap-1 text-sm">
                            <div>Open:</div><div class="text-right">${price.open.toFixed(2)}</div>
                            <div>High:</div><div class="text-right">${price.high.toFixed(2)}</div>
                            <div>Low:</div><div class="text-right">${price.low.toFixed(2)}</div>
                            <div>Close:</div><div class="text-right">${price.close.toFixed(2)}</div>
                        </div>
                    `;
                    tooltip.style.display = 'block';
                }
            }
        } else {
            const tooltip = document.getElementById('chart-tooltip');
            if (tooltip) {
                tooltip.style.display = 'none';
            }
        }
    });

    // Handle window resize
    function handleResize() {
        chart.applyOptions({
            width: chartContainer.clientWidth,
            height: chartContainer.clientHeight
        });
    }

    window.addEventListener('resize', handleResize);

    // Return cleanup function
    return function cleanup() {
        window.removeEventListener('resize', handleResize);
        chart.remove();
    };
}