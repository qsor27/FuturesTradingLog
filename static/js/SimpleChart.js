/**
 * SimpleChart.js - Minimal working chart implementation with caching
 * Auto-initializes on page load and caches data in database
 */

class SimpleChart {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.options = {
            instrument: options.instrument || 'MNQ',
            timeframe: options.timeframe || '1h',
            days: options.days || 1,
            ...options
        };
        
        this.chart = null;
        this.candlestickSeries = null;
        
        this.init();
    }
    
    async init() {
        try {
            if (!this.container) {
                console.error(`Container ${this.containerId} not found`);
                return;
            }
            
            // Create chart
            this.chart = LightweightCharts.createChart(this.container, {
                width: this.container.clientWidth || 800,
                height: 400,
                layout: {
                    backgroundColor: '#1a1a1a',
                    textColor: '#ffffff',
                },
                grid: {
                    vertLines: { color: '#2c2c2c' },
                    horzLines: { color: '#2c2c2c' },
                },
                timeScale: {
                    timeVisible: true,
                    secondsVisible: false,
                }
            });
            
            this.candlestickSeries = this.chart.addSeries(LightweightCharts.CandlestickSeries, {
                upColor: '#26a69a',
                downColor: '#ef5350',
                borderVisible: false,
                wickUpColor: '#26a69a',
                wickDownColor: '#ef5350',
            });
            
            // Load data automatically
            await this.loadData();
            
        } catch (error) {
            console.error('Chart initialization failed:', error);
        }
    }
    
    async loadData() {
        try {
            const response = await fetch(`/api/chart-data/${this.options.instrument}?timeframe=${this.options.timeframe}&days=${this.options.days}`);
            const data = await response.json();
            
            if (data && data.data && data.data.length > 0) {
                const chartData = data.data.map((item, index) => {
                    const date = new Date(item.time * 1000);
                    let timeString;
                    
                    if (this.options.timeframe === '1d') {
                        timeString = date.toISOString().slice(0, 10); // YYYY-MM-DD for daily
                    } else {
                        // Include seconds to avoid duplicate timestamps for intraday data
                        timeString = date.toISOString().slice(0, 19); // YYYY-MM-DDTHH:MM:SS
                    }
                    
                    return {
                        time: timeString,
                        open: parseFloat(item.open),
                        high: parseFloat(item.high),
                        low: parseFloat(item.low),
                        close: parseFloat(item.close)
                    };
                }).sort((a, b) => a.time.localeCompare(b.time));
                
                this.candlestickSeries.setData(chartData);
                this.chart.timeScale().fitContent();
                
                console.log(`Loaded ${chartData.length} candles for ${this.options.instrument}`);
                return true;
            } else {
                console.warn('No data available');
                return false;
            }
        } catch (error) {
            console.error('Failed to load chart data:', error);
            return false;
        }
    }
    
    updateTimeframe(timeframe) {
        this.options.timeframe = timeframe;
        return this.loadData();
    }
    
    updateDays(days) {
        this.options.days = days;
        return this.loadData();
    }
}

// Auto-initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    const chartContainers = document.querySelectorAll('[data-chart]');
    
    chartContainers.forEach(container => {
        const instrument = container.dataset.instrument || 'MNQ';
        const timeframe = container.dataset.timeframe || '1h';
        const days = parseInt(container.dataset.days) || 1;
        
        const chart = new SimpleChart(container.id, {
            instrument,
            timeframe,
            days
        });
        
        // Store chart instance on container for external access
        container.chartInstance = chart;
        
        // Setup event handlers
        const timeframeSelect = document.getElementById('timeframeSelect');
        const daysSelect = document.getElementById('daysSelect');
        
        if (timeframeSelect) {
            timeframeSelect.addEventListener('change', function() {
                chart.updateTimeframe(this.value);
            });
        }
        
        if (daysSelect) {
            daysSelect.addEventListener('change', function() {
                chart.updateDays(parseInt(this.value));
            });
        }
    });
});