/**
 * ModernChartComponent - Pure JSON Data Bridge Chart Implementation
 * 
 * A completely self-contained chart component built specifically for the JSON Data Bridge
 * architecture. No dependencies on legacy code or template literals.
 */
import { ComponentBase } from '../core/ComponentBase.js';
import { DataBridge } from '../core/DataBridge.js';
import { ComponentRegistry } from '../core/ComponentRegistry.js';

export class ModernChartComponent extends ComponentBase {
    constructor(element) {
        super(element);
        
        this.chart = null;
        this.candlestickSeries = null;
        this.volumeSeries = null;
        this.priceLines = [];
        this.markers = [];
        
        // Chart configuration
        this.chartOptions = {
            width: 0,
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
                mode: 0, // Normal crosshair mode
            },
            rightPriceScale: {
                borderColor: '#404040',
            },
            timeScale: {
                borderColor: '#404040',
                timeVisible: true,
                secondsVisible: false,
                tickMarkFormatter: (time, tickMarkType, locale) => {
                    // Format time labels based on timeframe
                    const date = new Date(time * 1000);
                    const timeframe = this.config?.timeframe || '1h';
                    
                    if (timeframe.includes('m')) {
                        // Minutes: show time only for intraday
                        return date.toLocaleTimeString('en-US', { 
                            hour: '2-digit', 
                            minute: '2-digit', 
                            hour12: false 
                        });
                    } else if (timeframe.includes('h')) {
                        // Hours: show date and time
                        return date.toLocaleDateString('en-US', { 
                            month: 'short', 
                            day: 'numeric' 
                        }) + ' ' + date.toLocaleTimeString('en-US', { 
                            hour: '2-digit', 
                            minute: '2-digit', 
                            hour12: false 
                        });
                    } else {
                        // Days: show date only
                        return date.toLocaleDateString('en-US', { 
                            month: 'short', 
                            day: 'numeric' 
                        });
                    }
                }
            },
        };
        
        this.candlestickOptions = {
            upColor: '#4CAF50',
            downColor: '#F44336',
            borderDownColor: '#F44336',
            borderUpColor: '#4CAF50',
            wickDownColor: '#F44336',
            wickUpColor: '#4CAF50',
        };
        
        this.volumeOptions = {
            color: '#9c27b0',
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: '',
            scaleMargins: {
                top: 0.8,
                bottom: 0,
            },
        };
    }
    
    async setup() {
        if (!this.config) {
            throw new Error('Chart configuration is required');
        }
        
        this.log('Initializing modern chart with config:', this.config);
        
        // Wait for TradingView library
        await this.waitForTradingViewLibrary();
        
        // Initialize chart
        await this.initializeChart();
        
        // Setup controls
        this.setupControls();
        
        // Load chart data
        await this.loadChartData();
        
        // Load trade markers if specified
        if (this.config.tradeId) {
            await this.loadTradeMarkers();
        }
        
        this.log('Modern chart initialization complete');
    }
    
    async waitForTradingViewLibrary(maxWait = 10000) {
        const startTime = Date.now();
        
        while (!window.LightweightCharts && (Date.now() - startTime) < maxWait) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        if (!window.LightweightCharts) {
            throw new Error('TradingView Lightweight Charts library not available');
        }
        
        this.log('TradingView library available');
    }
    
    async initializeChart() {
        try {
            // Set chart width to container width
            this.chartOptions.width = this.element.clientWidth || 800;
            this.chartOptions.height = this.config.height || 400;
            
            // Create chart
            this.chart = window.LightweightCharts.createChart(this.element, this.chartOptions);
            
            // Add candlestick series
            this.candlestickSeries = this.chart.addCandlestickSeries(this.candlestickOptions);
            
            // Add volume series if enabled
            if (this.config.showVolume !== false) {
                this.volumeSeries = this.chart.addHistogramSeries(this.volumeOptions);
            }
            
            // Handle resize
            this.setupResize();
            
            // Setup crosshair tracking for tooltips
            this.setupCrosshairTracking();
            
            this.log('Chart components initialized successfully');
            
        } catch (error) {
            this.logError('Chart initialization failed:', error);
            this.showError('Chart initialization failed: ' + error.message);
            throw error;
        }
    }
    
    setupResize() {
        // Handle container resize
        const resizeObserver = new ResizeObserver(entries => {
            if (this.chart && entries.length > 0) {
                const { width, height } = entries[0].contentRect;
                this.chart.applyOptions({ width: width, height: height });
            }
        });
        
        resizeObserver.observe(this.element);
        
        // Store observer for cleanup
        this.resizeObserver = resizeObserver;
    }
    
    setupCrosshairTracking() {
        // Create tooltip element
        this.createTooltip();
        
        // Subscribe to crosshair move events
        this.chart.subscribeCrosshairMove((param) => {
            this.updateTooltip(param);
        });
        
        this.log('Crosshair tracking enabled');
    }
    
    createTooltip() {
        // Create tooltip container
        const container = this.element.closest('.chart-component') || this.element.parentElement;
        
        this.tooltip = document.createElement('div');
        this.tooltip.className = 'chart-tooltip';
        this.tooltip.style.cssText = `
            position: absolute;
            display: none;
            background: rgba(32, 32, 32, 0.95);
            color: #e5e5e5;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 8px 12px;
            font-size: 12px;
            font-family: monospace;
            z-index: 1000;
            pointer-events: none;
            white-space: nowrap;
            backdrop-filter: blur(5px);
        `;
        
        container.appendChild(this.tooltip);
        this.log('Tooltip element created');
    }
    
    updateTooltip(param) {
        if (!this.tooltip || !param.time) {
            if (this.tooltip) {
                this.tooltip.style.display = 'none';
            }
            return;
        }
        
        // Get data for this time
        const candleData = param.seriesData.get(this.candlestickSeries);
        const volumeData = this.volumeSeries ? param.seriesData.get(this.volumeSeries) : null;
        
        if (!candleData) {
            this.tooltip.style.display = 'none';
            return;
        }
        
        // Format the time/date
        const date = new Date(param.time * 1000);
        const timeframe = this.config?.timeframe || '1h';
        
        let dateTimeStr;
        if (timeframe.includes('m')) {
            // Minutes: show full date and time
            dateTimeStr = date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric',
                year: 'numeric'
            }) + ' ' + date.toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit', 
                hour12: false 
            });
        } else if (timeframe.includes('h')) {
            // Hours: show date and time
            dateTimeStr = date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric',
                year: 'numeric'
            }) + ' ' + date.toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit', 
                hour12: false 
            });
        } else {
            // Days: show date only
            dateTimeStr = date.toLocaleDateString('en-US', { 
                weekday: 'short',
                month: 'short', 
                day: 'numeric',
                year: 'numeric'
            });
        }
        
        // Format OHLC data
        const o = candleData.open?.toFixed(2) || 'N/A';
        const h = candleData.high?.toFixed(2) || 'N/A';
        const l = candleData.low?.toFixed(2) || 'N/A';
        const c = candleData.close?.toFixed(2) || 'N/A';
        const v = volumeData?.value ? Math.round(volumeData.value).toLocaleString() : '';
        
        // Build tooltip content
        let content = `
            <div style="font-weight: bold; margin-bottom: 4px;">${dateTimeStr}</div>
            <div>O: ${o}</div>
            <div>H: ${h}</div>
            <div>L: ${l}</div>
            <div>C: ${c}</div>
        `;
        
        if (v) {
            content += `<div style="margin-top: 2px;">Vol: ${v}</div>`;
        }
        
        this.tooltip.innerHTML = content;
        
        // Position tooltip
        const containerRect = this.element.getBoundingClientRect();
        const tooltipWidth = 180; // Estimated width
        const tooltipHeight = v ? 100 : 80; // Estimated height
        
        let x = param.point.x + 15;
        let y = param.point.y - 10;
        
        // Keep tooltip within container bounds
        if (x + tooltipWidth > containerRect.width) {
            x = param.point.x - tooltipWidth - 15;
        }
        if (y + tooltipHeight > containerRect.height) {
            y = param.point.y - tooltipHeight + 10;
        }
        
        this.tooltip.style.left = x + 'px';
        this.tooltip.style.top = y + 'px';
        this.tooltip.style.display = 'block';
    }
    
    setupControls() {
        // Find and setup timeframe controls
        this.findAndSetupTimeframeControl();
        this.findAndSetupDaysControl();
        this.findAndSetupVolumeToggle();
    }
    
    findAndSetupTimeframeControl() {
        const container = this.element.closest('.chart-component') || this.element.parentElement;
        const timeframeSelect = container?.querySelector('.timeframe-select');
        
        if (timeframeSelect) {
            this.addEventListener(timeframeSelect, 'change', (e) => {
                this.handleTimeframeChange(e.target.value);
            });
            this.log('Timeframe control connected');
        }
    }
    
    findAndSetupDaysControl() {
        const container = this.element.closest('.chart-component') || this.element.parentElement;
        const daysSelect = container?.querySelector('.days-select');
        
        if (daysSelect) {
            this.addEventListener(daysSelect, 'change', (e) => {
                this.handleDaysChange(parseInt(e.target.value));
            });
            this.log('Days control connected');
        }
    }
    
    findAndSetupVolumeToggle() {
        const container = this.element.closest('.chart-component') || this.element.parentElement;
        const volumeToggle = container?.querySelector('.volume-checkbox');
        
        if (volumeToggle) {
            this.addEventListener(volumeToggle, 'change', (e) => {
                this.handleVolumeToggle(e.target.checked);
            });
            this.log('Volume toggle connected');
        }
    }
    
    async handleTimeframeChange(newTimeframe) {
        this.log('Timeframe changed to:', newTimeframe);
        this.config.timeframe = newTimeframe;
        await this.loadChartData();
    }
    
    async handleDaysChange(newDays) {
        this.log('Days changed to:', newDays);
        this.config.days = newDays;
        await this.loadChartData();
    }
    
    handleVolumeToggle(showVolume) {
        this.log('Volume toggle changed to:', showVolume);
        
        if (showVolume && !this.volumeSeries) {
            // Add volume series
            this.volumeSeries = this.chart.addHistogramSeries(this.volumeOptions);
            // Re-load data to populate volume
            this.loadChartData();
        } else if (!showVolume && this.volumeSeries) {
            // Remove volume series
            this.chart.removeSeries(this.volumeSeries);
            this.volumeSeries = null;
        }
    }
    
    async loadChartData() {
        try {
            this.showLoading();
            
            const instrument = this.config.instrument;
            const timeframe = this.config.timeframe || '1h';
            const days = this.config.days || 7;
            
            this.log('Loading chart data:', { instrument, timeframe, days });
            
            // Build API URL
            const apiUrl = '/api/chart-data-adaptive/' + encodeURIComponent(instrument) + 
                          '?timeframe=' + encodeURIComponent(timeframe) + 
                          '&days=' + encodeURIComponent(days);
            
            // Fetch data using DataBridge
            const response = await DataBridge.fetchData(apiUrl);
            
            if (!response.success) {
                throw new Error(response.error || 'Failed to load chart data');
            }
            
            if (!response.data || response.data.length === 0) {
                this.showError('No chart data available for ' + instrument);
                return;
            }
            
            // Process and set chart data
            await this.setChartData(response.data);
            
            // Show success message
            this.showSuccess('Loaded ' + response.data.length + ' candles for ' + instrument);
            
            this.hideLoading();
            
        } catch (error) {
            this.logError('Failed to load chart data:', error);
            this.showError('Failed to load chart data: ' + error.message);
            this.hideLoading();
        }
    }
    
    async setChartData(rawData) {
        try {
            // Filter out incomplete/current candles that haven't "printed" yet
            const filteredData = this.filterIncompleteCandles(rawData);
            
            // Process candlestick data
            const candlestickData = filteredData.map(item => ({
                time: item.time,
                open: parseFloat(item.open),
                high: parseFloat(item.high),
                low: parseFloat(item.low),
                close: parseFloat(item.close)
            }));
            
            // Set candlestick data
            this.candlestickSeries.setData(candlestickData);
            
            // Process and set volume data if volume series exists
            if (this.volumeSeries && filteredData[0] && 'volume' in filteredData[0]) {
                const volumeData = filteredData.map(item => ({
                    time: item.time,
                    value: parseFloat(item.volume || 0),
                    color: parseFloat(item.close) >= parseFloat(item.open) ? '#4CAF50' : '#F44336'
                }));
                
                this.volumeSeries.setData(volumeData);
            }
            
            // Fit chart content
            this.chart.timeScale().fitContent();
            
            const originalCount = rawData.length;
            const filteredCount = candlestickData.length;
            const filteredOut = originalCount - filteredCount;
            
            this.log('Chart data set successfully:', filteredCount, 'candles');
            if (filteredOut > 0) {
                this.log('Filtered out', filteredOut, 'incomplete candles');
            }
            
        } catch (error) {
            this.logError('Error setting chart data:', error);
            throw error;
        }
    }
    
    filterIncompleteCandles(rawData) {
        if (!rawData || rawData.length === 0) return rawData;
        
        const timeframe = this.config?.timeframe || '1h';
        const now = Date.now() / 1000; // Current time in Unix timestamp
        
        // Filter candles based on proper timeframe boundaries AND completion
        const filteredData = rawData.filter(item => {
            const candleTime = item.time;
            const candleDate = new Date(candleTime * 1000);
            
            // First check: Does this candle start at a proper timeframe boundary?
            const isValidBoundary = this.isValidTimeframeBoundary(candleDate, timeframe);
            
            if (!isValidBoundary) {
                this.log('Filtering invalid boundary candle at', candleDate.toISOString(), 'for', timeframe);
                return false;
            }
            
            // Second check: Has this candle's timeframe period completed?
            const timeframeDurations = {
                '1m': 60,
                '2m': 120,
                '5m': 300,
                '15m': 900,
                '30m': 1800,
                '1h': 3600
            };
            
            const timeframeDuration = timeframeDurations[timeframe] || 3600;
            const candleEndTime = candleTime + timeframeDuration;
            const isComplete = candleEndTime <= now;
            
            if (!isComplete) {
                this.log('Filtering incomplete candle at', candleDate.toISOString(), 
                        'ends at', new Date(candleEndTime * 1000).toISOString());
                return false;
            }
            
            return true;
        });
        
        return filteredData;
    }
    
    isValidTimeframeBoundary(date, timeframe) {
        switch (timeframe) {
            case '1m':
                // 1-minute: seconds should be 0
                return date.getSeconds() === 0;
            case '2m':
                // 2-minute: should be on even minutes, seconds should be 0
                return date.getSeconds() === 0 && date.getMinutes() % 2 === 0;
            case '5m':
                // 5-minute: minutes should be divisible by 5, seconds should be 0
                return date.getSeconds() === 0 && date.getMinutes() % 5 === 0;
            case '15m':
                // 15-minute: minutes should be 0, 15, 30, or 45, seconds should be 0
                return date.getSeconds() === 0 && date.getMinutes() % 15 === 0;
            case '30m':
                // 30-minute: minutes should be 0 or 30, seconds should be 0
                return date.getSeconds() === 0 && date.getMinutes() % 30 === 0;
            case '1h':
                // 1-hour: minutes and seconds should be 0
                return date.getMinutes() === 0 && date.getSeconds() === 0;
            default:
                // Unknown timeframe, allow all (fallback)
                return true;
        }
    }
    
    async loadTradeMarkers() {
        if (!this.config.tradeId) return;
        
        try {
            this.log('Loading trade markers for trade ID:', this.config.tradeId);
            
            const apiUrl = '/api/trade-markers/' + encodeURIComponent(this.config.tradeId);
            const response = await DataBridge.fetchData(apiUrl);
            
            if (response.markers && response.markers.length > 0) {
                this.setTradeMarkers(response.markers);
                this.log('Trade markers loaded:', response.markers.length);
            }
            
        } catch (error) {
            this.logError('Error loading trade markers:', error);
            // Don't throw - markers are optional
        }
    }
    
    setTradeMarkers(markers) {
        try {
            const chartMarkers = markers.map(marker => ({
                time: marker.time,
                position: marker.type === 'entry' ? 'belowBar' : 'aboveBar',
                color: marker.type === 'entry' ? '#4CAF50' : '#F44336',
                shape: marker.type === 'entry' ? 'arrowUp' : 'arrowDown',
                text: marker.type.toUpperCase() + ': ' + marker.quantity + '@' + marker.price.toFixed(2),
                id: 'marker_' + marker.id
            }));
            
            this.candlestickSeries.setMarkers(chartMarkers);
            this.markers = chartMarkers;
            
        } catch (error) {
            this.logError('Error setting trade markers:', error);
        }
    }
    
    showLoading() {
        const container = this.element.closest('.chart-component');
        if (container) {
            const loadingEl = container.querySelector('.chart-loading');
            if (loadingEl) {
                loadingEl.style.display = 'block';
            }
        }
    }
    
    hideLoading() {
        const container = this.element.closest('.chart-component');
        if (container) {
            const loadingEl = container.querySelector('.chart-loading');
            if (loadingEl) {
                loadingEl.style.display = 'none';
            }
        }
    }
    
    cleanup() {
        // Clean up resize observer
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }
        
        // Clean up tooltip
        if (this.tooltip) {
            this.tooltip.remove();
            this.tooltip = null;
        }
        
        // Clean up chart
        if (this.chart) {
            this.chart.remove();
            this.chart = null;
        }
        
        // Clear references
        this.candlestickSeries = null;
        this.volumeSeries = null;
        this.priceLines = [];
        this.markers = [];
    }
    
    // Public API methods
    
    async refresh() {
        await this.loadChartData();
    }
    
    async updateTimeframe(timeframe) {
        await this.handleTimeframeChange(timeframe);
    }
    
    async updateDays(days) {
        await this.handleDaysChange(days);
    }
    
    toggleVolume(showVolume) {
        this.handleVolumeToggle(showVolume);
    }
    
    getChartData() {
        return {
            candlestick: this.candlestickSeries?.data?.() || [],
            volume: this.volumeSeries?.data?.() || [],
            markers: this.markers || []
        };
    }
}

// Register the component for automatic initialization
ComponentRegistry.register('[data-component="modern-chart"]', ModernChartComponent);