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
        console.log('🚀 Initializing PriceChart...');
        console.log(`📦 LightweightCharts available: ${typeof LightweightCharts}`);
        console.log(`📊 Container element:`, this.container);
        console.log(`⚙️ Chart options:`, this.options);
        
        // Check if TradingView library is available
        if (typeof LightweightCharts === 'undefined') {
            const error = 'TradingView Lightweight Charts library not loaded';
            console.error(`❌ ${error}`);
            this.showError(error);
            return;
        }
        
        try {
            // Create chart
            console.log('📈 Creating chart...');
            this.chart = LightweightCharts.createChart(this.container, this.options);
            console.log('✅ Chart created successfully');
            
            // Create candlestick series
            console.log('🕯️ Adding candlestick series...');
            this.candlestickSeries = this.chart.addCandlestickSeries({
                upColor: '#4CAF50',
                downColor: '#F44336',
                borderDownColor: '#F44336',
                borderUpColor: '#4CAF50',
                wickDownColor: '#F44336',
                wickUpColor: '#4CAF50',
            });
            console.log('✅ Candlestick series added');
            
            // Create volume series
            console.log('📊 Adding volume series...');
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
            console.log('✅ Volume series added');
            
            // Handle resize
            console.log('🔄 Setting up resize handler...');
            this.setupResizeHandler();
            
            // Load initial data
            console.log('📡 Loading initial data...');
            this.loadData();
            
        } catch (error) {
            console.error('❌ Error during chart initialization:', error);
            this.showError(`Chart initialization failed: ${error.message}`);
        }
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
            console.log(`🔍 Loading chart data for ${this.options.instrument}, timeframe: ${this.options.timeframe}, days: ${this.options.days}`);
            
            // First try the requested timeframe
            let url = `/api/chart-data/${this.options.instrument}?timeframe=${this.options.timeframe}&days=${this.options.days}`;
            console.log(`📡 Fetching from: ${url}`);
            
            let response = await fetch(url);
            console.log(`📊 Response status: ${response.status} ${response.statusText}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            let data = await response.json();
            console.log(`📈 API Response:`, {
                success: data.success,
                count: data.count,
                hasData: !!(data.data && data.data.length > 0),
                instrument: data.instrument,
                timeframe: data.timeframe
            });
            
            if (!data.success) {
                const errorMsg = data.error || 'Failed to fetch chart data';
                console.error(`❌ API returned error: ${errorMsg}`);
                throw new Error(errorMsg);
            }
            
            // If no data for requested timeframe, try to find alternative
            if (!data.data || data.data.length === 0) {
                console.warn(`⚠️ No data for ${this.options.timeframe}, checking available timeframes...`);
                
                try {
                    const timeframesResponse = await fetch(`/api/available-timeframes/${this.options.instrument}`);
                    if (timeframesResponse.ok) {
                        const timeframesData = await timeframesResponse.json();
                        console.log(`🔍 Available timeframes:`, timeframesData);
                        
                        if (timeframesData.success && timeframesData.best_timeframe) {
                            console.log(`🔄 Switching from ${this.options.timeframe} to ${timeframesData.best_timeframe}`);
                            
                            // Update options and retry
                            this.options.timeframe = timeframesData.best_timeframe;
                            
                            // Retry with best available timeframe
                            url = `/api/chart-data/${this.options.instrument}?timeframe=${this.options.timeframe}&days=${this.options.days}`;
                            response = await fetch(url);
                            
                            if (response.ok) {
                                data = await response.json();
                                console.log(`🎯 Fallback successful: ${data.count} records with ${this.options.timeframe}`);
                                
                                // Update UI to show we switched timeframes
                                this.updateTimeframeSelect(this.options.timeframe);
                            }
                        }
                    }
                } catch (fallbackError) {
                    console.error(`❌ Error checking available timeframes: ${fallbackError}`);
                }
            }
            
            if (!data.data || data.data.length === 0) {
                console.warn(`⚠️ No data available for ${this.options.instrument} in any timeframe`);
                this.showError(`No market data available for ${this.options.instrument}. Try updating data or check a different instrument.`);
                return;
            }
            
            console.log(`✅ Received ${data.data.length} data points, calling setData...`);
            this.setData(data.data);
            
        } catch (error) {
            console.error('❌ Error loading chart data:', error);
            this.showError(`Failed to load chart: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }
    
    setData(data) {
        if (!data || data.length === 0) {
            this.showError('No data available for this instrument and timeframe');
            return;
        }
        
        console.log(`Processing ${data.length} data points for chart...`);
        console.log('Sample raw data:', data[0]);
        
        // Process data for candlestick series with proper timestamp handling
        const candlestickData = data.map(item => {
            // Ensure timestamp is a proper number and valid
            let timestamp = item.time;
            if (typeof timestamp === 'string') {
                timestamp = parseInt(timestamp);
            }
            
            // Validate OHLC data
            const ohlcData = {
                time: timestamp,
                open: parseFloat(item.open),
                high: parseFloat(item.high),
                low: parseFloat(item.low),
                close: parseFloat(item.close)
            };
            
            // Validate the data point
            if (isNaN(ohlcData.open) || isNaN(ohlcData.high) || isNaN(ohlcData.low) || isNaN(ohlcData.close)) {
                console.warn('Invalid OHLC data point:', item);
                return null;
            }
            
            if (ohlcData.high < ohlcData.low) {
                console.warn('Invalid OHLC: high < low', ohlcData);
                return null;
            }
            
            return ohlcData;
        }).filter(item => item !== null); // Remove invalid entries
        
        // Process data for volume series
        const volumeData = data.map(item => {
            let timestamp = item.time;
            if (typeof timestamp === 'string') {
                timestamp = parseInt(timestamp);
            }
            
            return {
                time: timestamp,
                value: Math.max(0, parseInt(item.volume) || 0),
                color: parseFloat(item.close) >= parseFloat(item.open) ? '#4CAF50' : '#F44336'
            };
        });
        
        console.log(`Processed candlestick data: ${candlestickData.length} points`);
        console.log('Sample processed data:', candlestickData[0]);
        
        if (candlestickData.length === 0) {
            this.showError('No valid data points after processing');
            return;
        }
        
        try {
            // Set data to series
            this.candlestickSeries.setData(candlestickData);
            this.volumeSeries.setData(volumeData);
            
            // Fit content to show all data
            this.chart.timeScale().fitContent();
            
            console.log(`Successfully loaded ${candlestickData.length} candles for ${this.options.instrument}`);
            
            // Force a redraw
            this.chart.applyOptions({});
            
        } catch (error) {
            console.error('Error setting chart data:', error);
            this.showError(`Chart error: ${error.message}`);
        }
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
    
    updateTimeframeSelect(timeframe) {
        // Update the timeframe select dropdown to reflect the current timeframe
        const timeframeSelect = document.querySelector(`[data-chart-id="${this.containerId}"].timeframe-select`);
        if (timeframeSelect) {
            timeframeSelect.value = timeframe;
            console.log(`🔄 Updated timeframe select to: ${timeframe}`);
        }
    }
    
    showLoading(show) {
        const loadingEl = this.container.querySelector('.chart-loading');
        if (loadingEl) {
            loadingEl.style.display = show ? 'block' : 'none';
        }
    }
    
    showError(message) {
        console.error('Chart error:', message);
        
        const errorEl = this.container.querySelector('.chart-error');
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.style.display = 'block';
        } else {
            // Create error element if it doesn't exist
            const errorDiv = document.createElement('div');
            errorDiv.className = 'chart-error';
            errorDiv.style.cssText = `
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                padding: 20px;
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
                border-radius: 4px;
                z-index: 1000;
                max-width: 80%;
                text-align: center;
                font-size: 14px;
            `;
            errorDiv.textContent = message;
            this.container.appendChild(errorDiv);
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
    console.log('🎯 DOM loaded, searching for chart containers...');
    
    const chartContainers = document.querySelectorAll('[data-chart]');
    console.log(`🔍 Found ${chartContainers.length} chart containers`);
    
    if (chartContainers.length === 0) {
        console.warn('⚠️ No chart containers found with [data-chart] attribute');
        return;
    }
    
    chartContainers.forEach((container, index) => {
        console.log(`\n📊 Initializing chart ${index + 1}/${chartContainers.length}`);
        console.log(`🏷️ Container ID: ${container.id}`);
        console.log(`📋 Dataset:`, container.dataset);
        
        const options = {
            instrument: container.dataset.instrument || 'MNQ',
            timeframe: container.dataset.timeframe || '1m',
            days: parseInt(container.dataset.days) || 1
        };
        
        console.log(`⚙️ Chart options:`, options);
        
        try {
            const chart = new PriceChart(container.id, options);
            
            // Store chart instance on container for external access
            container.chartInstance = chart;
            console.log(`✅ Chart ${index + 1} initialized successfully`);
            
            // Load trade markers if trade ID is specified
            if (container.dataset.tradeId) {
                console.log(`🎯 Loading trade markers for trade ID: ${container.dataset.tradeId}`);
                chart.loadTradeMarkers(parseInt(container.dataset.tradeId));
            }
            
        } catch (error) {
            console.error(`❌ Failed to initialize chart ${index + 1}:`, error);
            console.error('Stack trace:', error.stack);
        }
    });
    
    console.log(`\n🏁 Chart initialization complete. Total containers processed: ${chartContainers.length}`);
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { PriceChart, createPriceChart };
}