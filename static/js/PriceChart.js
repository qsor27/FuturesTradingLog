/**
 * PriceChart.js - TradingView Lightweight Charts integration
 * Provides OHLC candlestick charts with trade execution overlays
 */

class PriceChart {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        
        if (!this.container) {
            throw new Error(`Container with id '${containerId}' not found`);
        }
        
        // Default options
        this.options = {
            instrument: 'MNQ',
            timeframe: '1m',
            days: 1,
            width: this.container.clientWidth,
            height: 400,
            layout: {
                background: { color: '#1a1a1a' },
                textColor: '#e5e5e5',
            },
            grid: {
                vertLines: { color: '#333333' },
                horzLines: { color: '#333333' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: '#404040',
            },
            timeScale: {
                borderColor: '#404040',
                timeVisible: true,
                secondsVisible: false,
            },
            ...options
        };
        
        this.chart = null;
        this.candlestickSeries = null;
        this.volumeSeries = null;
        this.markers = [];
        
        this.init();
    }
    
    init() {
        // Create chart
        this.chart = LightweightCharts.createChart(this.container, this.options);
        
        // Create candlestick series
        this.candlestickSeries = this.chart.addCandlestickSeries({
            upColor: '#4CAF50',
            downColor: '#F44336',
            borderDownColor: '#F44336',
            borderUpColor: '#4CAF50',
            wickDownColor: '#F44336',
            wickUpColor: '#4CAF50',
        });
        
        // Create volume series
        this.volumeSeries = this.chart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: 'left',
            scaleMargins: {
                top: 0.8,
                bottom: 0,
            },
        });
        
        // Handle resize
        this.setupResizeHandler();
        
        // Load initial data
        this.loadData();
    }
    
    setupResizeHandler() {
        const resizeObserver = new ResizeObserver(entries => {
            if (entries.length === 0 || entries[0].target !== this.container) {
                return;
            }
            
            const newRect = entries[0].contentRect;
            this.chart.applyOptions({
                width: newRect.width,
                height: newRect.height
            });
        });
        
        resizeObserver.observe(this.container);
    }
    
    async loadData() {
        try {
            this.showLoading(true);
            
            // Fetch OHLC data
            const response = await fetch(
                `/api/chart-data/${this.options.instrument}?timeframe=${this.options.timeframe}&days=${this.options.days}`
            );
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Failed to fetch chart data');
            }
            
            this.setData(data.data);
            
        } catch (error) {
            console.error('Error loading chart data:', error);
            this.showError(error.message);
        } finally {
            this.showLoading(false);
        }
    }
    
    setData(data) {
        if (!data || data.length === 0) {
            this.showError('No data available for this instrument and timeframe');
            return;
        }
        
        // Process data for candlestick series
        const candlestickData = data.map(item => ({
            time: item.time,
            open: item.open,
            high: item.high,
            low: item.low,
            close: item.close
        }));
        
        // Process data for volume series
        const volumeData = data.map(item => ({
            time: item.time,
            value: item.volume || 0,
            color: item.close >= item.open ? '#4CAF50' : '#F44336'
        }));
        
        // Set data
        this.candlestickSeries.setData(candlestickData);
        this.volumeSeries.setData(volumeData);
        
        // Fit content
        this.chart.timeScale().fitContent();
        
        console.log(`Loaded ${data.length} candles for ${this.options.instrument}`);
    }
    
    async loadTradeMarkers(tradeId) {
        try {
            const response = await fetch(`/api/trade-markers/${tradeId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success && data.markers) {
                this.addTradeMarkers(data.markers);
            }
            
        } catch (error) {
            console.error('Error loading trade markers:', error);
        }
    }
    
    addTradeMarkers(markers) {
        // Add markers to existing list
        this.markers = this.markers.concat(markers);
        
        // Update series markers
        this.candlestickSeries.setMarkers(this.markers);
    }
    
    addExecutionMarkers(executions) {
        // Clear existing execution markers
        this.clearExecutionMarkers();
        
        // Convert executions to chart markers
        const executionMarkers = executions.map(execution => {
            const timestamp = new Date(execution.timestamp).getTime() / 1000;
            
            return {
                time: timestamp,
                position: execution.type === 'entry' ? 'belowBar' : 'aboveBar',
                color: execution.type === 'entry' ? '#4CAF50' : '#F44336',
                shape: execution.type === 'entry' ? 'arrowUp' : 'arrowDown',
                text: `${execution.type.toUpperCase()}: ${execution.quantity}@${execution.price.toFixed(2)}`,
                id: `execution_${execution.execution_id}`,
                execution: execution
            };
        });
        
        // Add execution markers to existing markers
        this.executionMarkers = executionMarkers;
        const allMarkers = [...this.markers, ...this.executionMarkers];
        this.candlestickSeries.setMarkers(allMarkers);
        
        // Setup marker click handler for highlighting
        this.setupMarkerClickHandler();
    }
    
    clearExecutionMarkers() {
        this.executionMarkers = [];
        this.candlestickSeries.setMarkers(this.markers);
    }
    
    setupMarkerClickHandler() {
        // Handle marker clicks for table synchronization
        this.chart.subscribeClick((param) => {
            if (param.point && this.executionMarkers) {
                const clickedMarker = this.executionMarkers.find(marker => 
                    Math.abs(marker.time - param.time) < 60 // Within 1 minute tolerance
                );
                
                if (clickedMarker) {
                    this.highlightExecution(clickedMarker.execution);
                }
            }
        });
    }
    
    highlightExecution(execution) {
        // Dispatch custom event for table synchronization
        const event = new CustomEvent('executionHighlight', {
            detail: { execution }
        });
        document.dispatchEvent(event);
        
        // Visual highlight on chart
        this.highlightMarker(execution.execution_id);
    }
    
    highlightMarker(executionId) {
        // Find and temporarily highlight the marker
        const marker = this.executionMarkers.find(m => 
            m.execution.execution_id === executionId
        );
        
        if (marker) {
            // Create temporary highlight marker
            const highlightMarker = {
                ...marker,
                color: '#FFD700', // Gold highlight
                size: 2
            };
            
            // Replace marker temporarily
            const tempMarkers = this.executionMarkers.map(m => 
                m.execution.execution_id === executionId ? highlightMarker : m
            );
            
            this.candlestickSeries.setMarkers([...this.markers, ...tempMarkers]);
            
            // Reset after 2 seconds
            setTimeout(() => {
                this.candlestickSeries.setMarkers([...this.markers, ...this.executionMarkers]);
            }, 2000);
        }
    }
    
    clearMarkers() {
        this.markers = [];
        this.candlestickSeries.setMarkers([]);
    }
    
    updateTimeframe(timeframe) {
        this.options.timeframe = timeframe;
        this.loadData();
    }
    
    updateDays(days) {
        this.options.days = days;
        this.loadData();
    }
    
    updateInstrument(instrument) {
        this.options.instrument = instrument;
        this.clearMarkers();
        this.loadData();
    }
    
    showLoading(show) {
        const loadingEl = this.container.querySelector('.chart-loading');
        if (loadingEl) {
            loadingEl.style.display = show ? 'block' : 'none';
        }
    }
    
    showError(message) {
        const errorEl = this.container.querySelector('.chart-error');
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.style.display = 'block';
        } else {
            console.error('Chart error:', message);
        }
    }
    
    destroy() {
        if (this.chart) {
            this.chart.remove();
            this.chart = null;
        }
    }
}

// Chart factory function
function createPriceChart(containerId, options = {}) {
    return new PriceChart(containerId, options);
}

// Auto-initialize charts with data-chart attributes
document.addEventListener('DOMContentLoaded', function() {
    const chartContainers = document.querySelectorAll('[data-chart]');
    
    chartContainers.forEach(container => {
        const options = {
            instrument: container.dataset.instrument || 'MNQ',
            timeframe: container.dataset.timeframe || '1m',
            days: parseInt(container.dataset.days) || 1
        };
        
        try {
            const chart = new PriceChart(container.id, options);
            
            // Store chart instance on container for external access
            container.chartInstance = chart;
            
            // Load trade markers if trade ID is specified
            if (container.dataset.tradeId) {
                chart.loadTradeMarkers(parseInt(container.dataset.tradeId));
            }
            
        } catch (error) {
            console.error('Failed to initialize chart:', error);
        }
    });
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { PriceChart, createPriceChart };
}