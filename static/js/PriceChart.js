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
        
        // Store user options for later merging
        this.userOptions = options;
        
        this.chart = null;
        this.candlestickSeries = null;
        this.volumeSeries = null;
        this.markers = [];
        this.priceLines = []; // Store active price lines for position entry prices
        this.volumeVisible = true; // Default volume visibility (will be overridden by settings)
        this.ohlcDisplayEl = null; // OHLC overlay element
        this.crosshairMoveHandler = null; // Store bound handler for cleanup
        this.settingsLoaded = false; // Track if user settings have been applied
        this.state = 'loading'; // Chart state: loading, ready, error
        this.statusElement = null; // Status indicator element
        
        this.init();
    }
    
    buildChartOptions() {
        // Check if TradingView library and its properties are fully loaded
        const crosshairMode = (typeof LightweightCharts !== 'undefined' && 
                              LightweightCharts.CrosshairMode && 
                              LightweightCharts.CrosshairMode.Magnet) ? 
                              LightweightCharts.CrosshairMode.Magnet : 1; // fallback to normal mode
        
        const lineStyle = (typeof LightweightCharts !== 'undefined' && 
                          LightweightCharts.CrosshairLineStyle && 
                          LightweightCharts.CrosshairLineStyle.Solid) ? 
                          LightweightCharts.CrosshairLineStyle.Solid : 0; // fallback to solid

        // Build default options (now that TradingView library is available)
        this.options = {
            instrument: 'MNQ',
            timeframe: '1h', // Default timeframe
            days: 7, // Default to 1 week
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
                mode: crosshairMode,
                vertLine: {
                    visible: true,
                    labelVisible: false,
                    style: lineStyle,
                    color: '#758696',
                    width: 1,
                },
                horzLine: {
                    visible: true,
                    labelVisible: false,
                    style: lineStyle,
                    color: '#758696',
                    width: 1,
                },
            },
            rightPriceScale: {
                borderColor: '#404040',
                autoScale: true,
                scaleMargins: {
                    top: 0.1,
                    bottom: 0.1,
                },
            },
            timeScale: {
                borderColor: '#404040',
                timeVisible: true,
                secondsVisible: false,
            },
            ...this.userOptions
        };
    }
    
    init() {
        console.log('🚀 Initializing PriceChart...');
        console.log(`📦 LightweightCharts available: ${typeof LightweightCharts}`);
        console.log(`📊 Container element:`, this.container);
        
        // Check if TradingView library is available
        if (typeof LightweightCharts === 'undefined') {
            const error = 'TradingView Lightweight Charts library not loaded';
            console.error(`❌ ${error}`);
            this.showError(error);
            return;
        }
        
        // Build chart options now that library is available
        this.buildChartOptions();
        console.log(`⚙️ Chart options:`, this.options);
        
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
            
            // Create volume series (only if initially visible)
            if (this.volumeVisible) {
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
            } else {
                console.log('📊 Volume series skipped (hidden by default)');
            }
            
            // Initialize OHLC overlay
            console.log('💱 Initializing OHLC overlay...');
            this.initOhlcDisplay();
            
            // Subscribe to crosshair events
            console.log('🎯 Setting up crosshair event handlers...');
            this.subscribeToEvents();
            
            // Subscribe to settings updates
            console.log('⚙️ Setting up settings update handler...');
            this.setupSettingsListener();
            
            // Handle resize
            console.log('🔄 Setting up resize handler...');
            this.setupResizeHandler();
            
            // Bind chart controls
            console.log('🎮 Setting up chart controls...');
            PriceChart.bindChartControls(this);
            
            // Load user settings and then data
            console.log('⚙️ Loading user settings...');
            this.loadUserSettings().then(() => {
                console.log('📡 Loading initial data...');
                this.loadData();
            });
            
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
    
    async loadUserSettings() {
        try {
            // Only load settings if ChartSettingsAPI is available and not already loaded
            if (typeof window.chartSettingsAPI !== 'undefined' && !this.settingsLoaded) {
                console.log('⚙️ Loading user chart settings...');
                const settings = await window.chartSettingsAPI.getSettings();
                
                // Apply user settings only if container doesn't have explicit data attributes
                const container = this.container;
                
                // Apply timeframe if not explicitly set
                if (!container.dataset.timeframe && settings.default_timeframe) {
                    this.options.timeframe = settings.default_timeframe;
                    console.log(`🎯 Applied user default timeframe: ${settings.default_timeframe}`);
                }
                
                // Apply data range if not explicitly set 
                if (!container.dataset.days && settings.default_data_range) {
                    this.options.days = window.chartSettingsAPI.convertDataRangeToDays(settings.default_data_range);
                    console.log(`📅 Applied user default data range: ${settings.default_data_range} (${this.options.days} days)`);
                }
                
                // Apply volume visibility
                if (settings.volume_visibility !== undefined) {
                    this.volumeVisible = settings.volume_visibility;
                    console.log(`📊 Applied user volume visibility: ${settings.volume_visibility}`);
                }
                
                this.settingsLoaded = true;
                console.log('✅ User settings applied successfully');
            } else {
                console.log('⚠️ ChartSettingsAPI not available or settings already loaded, using defaults');
            }
        } catch (error) {
            console.error('❌ Error loading user settings:', error);
            // Continue with defaults
        }
    }
    
    async loadData() {
        try {
            const loadingMessage = `Loading ${this.options.timeframe} data...`;
            this.updateStatus('loading', loadingMessage);
            console.log(`📡 Loading chart data for ${this.options.instrument}, timeframe: ${this.options.timeframe}, days: ${this.options.days}`);
            
            // CHART DEBUG: Remove hardcoded dates and use dynamic date range based on days parameter
            console.log(`🔍 CHART DEBUG: Building URL for ${this.options.days} days of data`);
            console.log(`🔍 CHART DEBUG: Current date: ${new Date().toISOString()}`);
            
            const url = `/api/chart-data/${this.options.instrument}?timeframe=${this.options.timeframe}&days=${this.options.days}`;
            console.log(`📡 CHART DEBUG: Fetching from: ${url}`);
            
            // Show loading overlay for larger datasets
            if (this.options.days > 30) {
                this.showLoadingOverlay(`Loading ${this.options.days}-day ${this.options.timeframe} chart...`);
            }
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
            
            try {
                const response = await fetch(url, {
                    signal: controller.signal,
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    throw new Error(`Server error: ${response.status} ${response.statusText}`);
                }
                
                const data = await response.json();
                console.log(`📊 CHART DEBUG: API Response received:`, {
                    success: data.success,
                    instrument: data.instrument,
                    timeframe: data.timeframe,
                    days: data.days,
                    count: data.count,
                    hasData: !!(data.data && data.data.length > 0),
                    firstDataPoint: data.data && data.data.length > 0 ? data.data[0] : null,
                    lastDataPoint: data.data && data.data.length > 0 ? data.data[data.data.length - 1] : null
                });
                
                // CHART DEBUG: Check data timestamps
                if (data.data && data.data.length > 0) {
                    const firstTime = new Date(data.data[0].time * 1000);
                    const lastTime = new Date(data.data[data.data.length - 1].time * 1000);
                    console.log(`🔍 CHART DEBUG: Data time range - First: ${firstTime.toISOString()}, Last: ${lastTime.toISOString()}`);
                    console.log(`🔍 CHART DEBUG: Days difference from today: ${Math.round((new Date() - lastTime) / (1000 * 60 * 60 * 24))} days`);
                }
                
                if (!data.success) {
                    const errorMessage = this.getDetailedErrorMessage(data.error);
                    throw new Error(errorMessage);
                }
                
                if (!data.data || data.data.length === 0) {
                    const noDataMessage = this.getNoDataMessage(data);
                    this.showError(noDataMessage, data.available_timeframes);
                    return;
                }
                
                console.log(`✅ Received ${data.data.length} data points`);
                this.setData(data.data);
                this.updateStatus('ready', `Loaded ${data.count.toLocaleString()} candles`);
                this.hideLoadingOverlay();
                
            } catch (fetchError) {
                clearTimeout(timeoutId);
                if (fetchError.name === 'AbortError') {
                    throw new Error('Request timed out. Please try again.');
                }
                throw fetchError;
            }
            
        } catch (error) {
            console.error('❌ Error loading chart data:', error);
            const friendlyMessage = this.getFriendlyErrorMessage(error);
            this.updateStatus('error', friendlyMessage);
            this.showError(friendlyMessage);
            this.hideLoadingOverlay();
        }
    }
    
    getDetailedErrorMessage(error) {
        if (!error) return 'Unknown server error occurred';
        
        // Map common error patterns to user-friendly messages
        const errorMappings = {
            'no data': 'No market data found for this timeframe',
            'timeout': 'Request timed out - server may be busy',
            'server error': 'Server temporarily unavailable',
            'invalid parameters': 'Invalid chart parameters provided',
            'connection': 'Network connection error'
        };
        
        const lowerError = error.toLowerCase();
        for (const [pattern, message] of Object.entries(errorMappings)) {
            if (lowerError.includes(pattern)) {
                return message;
            }
        }
        
        return error; // Return original if no mapping found
    }
    
    getNoDataMessage(response) {
        const { instrument, timeframe, available_timeframes } = response;
        
        if (available_timeframes && available_timeframes.length > 0) {
            return `No ${timeframe} data available for ${instrument}. Try: ${available_timeframes.slice(0, 3).join(', ')}`;
        }
        
        return `No market data available for ${instrument}. Data may need to be updated.`;
    }
    
    getFriendlyErrorMessage(error) {
        if (error.name === 'AbortError') {
            return 'Request was cancelled or timed out';
        }
        
        if (error.message.includes('fetch')) {
            return 'Unable to connect to server';
        }
        
        if (error.message.includes('JSON')) {
            return 'Server response was invalid';
        }
        
        // Keep the original message if it's already user-friendly
        if (error.message.length < 100 && !error.message.includes('Error:')) {
            return error.message;
        }
        
        return 'An unexpected error occurred while loading the chart';
    }
    
    showLoadingOverlay(message) {
        // Remove existing overlay
        this.hideLoadingOverlay();
        
        const overlay = document.createElement('div');
        overlay.className = 'chart-loading-overlay';
        overlay.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner">
                    <div class="spinner-ring"></div>
                    <div class="spinner-ring"></div>
                    <div class="spinner-ring"></div>
                </div>
                <div class="loading-text">${message}</div>
                <div class="loading-subtext">This may take a few seconds...</div>
            </div>
        `;
        
        overlay.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(3px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2000;
            animation: fadeIn 0.3s ease;
        `;
        
        // Add loading animation styles if not already present
        if (!document.querySelector('#loading-overlay-styles')) {
            const style = document.createElement('style');
            style.id = 'loading-overlay-styles';
            style.textContent = `
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                .loading-content {
                    text-align: center;
                    color: white;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                }
                .loading-spinner {
                    display: inline-block;
                    position: relative;
                    width: 64px;
                    height: 64px;
                    margin-bottom: 20px;
                }
                .spinner-ring {
                    display: block;
                    position: absolute;
                    width: 48px;
                    height: 48px;
                    margin: 6px;
                    border: 3px solid transparent;
                    border-top-color: #fff;
                    border-radius: 50%;
                    animation: spin 1.2s cubic-bezier(0.5, 0, 0.5, 1) infinite;
                }
                .spinner-ring:nth-child(1) { animation-delay: -0.45s; }
                .spinner-ring:nth-child(2) { animation-delay: -0.3s; }
                .spinner-ring:nth-child(3) { animation-delay: -0.15s; }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                .loading-text {
                    font-size: 16px;
                    font-weight: 500;
                    margin-bottom: 8px;
                }
                .loading-subtext {
                    font-size: 12px;
                    opacity: 0.8;
                }
            `;
            document.head.appendChild(style);
        }
        
        this.container.appendChild(overlay);
        this.loadingOverlay = overlay;
    }
    
    hideLoadingOverlay() {
        if (this.loadingOverlay && this.loadingOverlay.parentNode) {
            this.loadingOverlay.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => {
                if (this.loadingOverlay && this.loadingOverlay.parentNode) {
                    this.loadingOverlay.parentNode.removeChild(this.loadingOverlay);
                }
                this.loadingOverlay = null;
            }, 300);
        }
    }
    
    
    
    
    
    setData(data) {
        console.log(`📊 setData called with data:`, data);
        console.log(`📊 Data type:`, typeof data);
        console.log(`📊 Data is array:`, Array.isArray(data));
        console.log(`📊 Data length:`, data ? data.length : 'null/undefined');
        
        // Add smooth data loading transition
        if (this.candlestickSeries) {
            this.container.style.transition = 'opacity 0.3s ease';
            this.container.style.opacity = '0.7';
        }
        
        if (!data || data.length === 0) {
            console.error(`❌ No data available for chart! Data:`, data);
            this.showError('No data available for this instrument and timeframe');
            return;
        }
        
        console.log(`Processing ${data.length} data points for chart...`);
        console.log('Sample raw data:', data[0]);
        console.log('All raw data (first 5):', data.slice(0, 5));
        
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
            console.log(`📊 About to set candlestick data. Series exists:`, !!this.candlestickSeries);
            console.log(`📊 Candlestick data to set:`, candlestickData);
            console.log(`📊 Candlestick data length:`, candlestickData.length);
            
            // Set data to candlestick series
            this.candlestickSeries.setData(candlestickData);
            console.log(`✅ Candlestick data set successfully!`);
            
            // Cache volume data for toggle functionality
            this.cachedVolumeData = volumeData;
            
            // Set volume data only if volume is visible
            if (this.volumeVisible && this.volumeSeries) {
                console.log(`📊 Setting volume data:`, volumeData.slice(0, 3));
                this.volumeSeries.setData(volumeData);
                console.log(`✅ Volume data set successfully!`);
            } else {
                console.log(`📊 Volume not visible or series doesn't exist. Visible: ${this.volumeVisible}, Series: ${!!this.volumeSeries}`);
            }
            
            // Fit content to show all data with auto-scaling
            console.log(`📊 Fitting chart content...`);
            this.chart.timeScale().fitContent();
            console.log(`✅ Chart content fitted!`);
            
            console.log(`🎉 Successfully loaded ${candlestickData.length} candles for ${this.options.instrument}`);
            
            // Force a redraw with smooth transition
            console.log(`📊 Forcing chart redraw...`);
            this.chart.applyOptions({});
            console.log(`✅ Chart redraw complete!`);
            
            // Restore opacity with animation
            if (this.container) {
                setTimeout(() => {
                    this.container.style.opacity = '1';
                }, 100);
            }
            
        } catch (error) {
            console.error('❌ Error setting chart data:', error);
            console.error('❌ Stack trace:', error.stack);
            this.updateStatus('error', `Chart error: ${error.message}`);
            this.showError(`Chart error: ${error.message}`);
        }
    }
    
    updateStatus(state, message) {
        this.state = state;
        
        if (!this.statusElement) {
            this.createStatusElement();
        }
        
        const statusText = this.statusElement.querySelector('.status-text');
        const statusIndicator = this.statusElement.querySelector('.status-indicator');
        
        if (statusText) {
            statusText.textContent = message || '';
        }
        
        if (statusIndicator) {
            statusIndicator.className = `status-indicator status-${state}`;
        }
        
        // Update control states based on loading state
        this.updateControlStates(state === 'loading');
        
        // Auto-hide success messages after 3 seconds
        if (state === 'ready') {
            setTimeout(() => {
                if (this.state === 'ready' && this.statusElement) {
                    this.statusElement.style.opacity = '0.7';
                }
            }, 3000);
        } else {
            this.statusElement.style.opacity = '1';
        }
    }
    
    updateControlStates(isLoading) {
        const controls = [
            document.querySelector('#timeframeSelect'),
            document.querySelector('#daysSelect'),
            document.querySelector('#refreshDataBtn'),
            document.querySelector(`[data-target-chart="${this.containerId}"] select`),
            document.querySelector(`[data-target-chart="${this.containerId}"] button`)
        ];
        
        controls.forEach(control => {
            if (control) {
                control.disabled = isLoading;
                if (isLoading) {
                    control.style.opacity = '0.6';
                    control.style.cursor = 'wait';
                } else {
                    control.style.opacity = '1';
                    control.style.cursor = control.tagName === 'BUTTON' ? 'pointer' : 'default';
                }
            }
        });
    }
    
    createStatusElement() {
        this.statusElement = document.createElement('div');
        this.statusElement.className = 'chart-status';
        this.statusElement.innerHTML = `
            <div class="status-indicator status-loading"></div>
            <div class="status-text">Initializing chart...</div>
        `;
        
        this.statusElement.style.cssText = `
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0, 0, 0, 0.8);
            color: #fff;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace;
            font-weight: 500;
            z-index: 1000;
            display: flex;
            align-items: center;
            gap: 10px;
            backdrop-filter: blur(6px);
            transition: all 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
            min-width: 120px;
        `;
        
        // Add CSS for status indicators with enhanced animations
        const style = document.createElement('style');
        style.textContent = `
            .status-indicator {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                flex-shrink: 0;
                transition: all 0.3s ease;
            }
            .status-loading {
                background: #ffd700;
                animation: pulse-glow 1.5s infinite;
                box-shadow: 0 0 4px rgba(255, 215, 0, 0.6);
            }
            .status-ready {
                background: #4caf50;
                box-shadow: 0 0 3px rgba(76, 175, 80, 0.4);
                animation: success-ping 0.6s ease-out;
            }
            .status-error {
                background: #f44336;
                box-shadow: 0 0 3px rgba(244, 67, 54, 0.4);
                animation: error-shake 0.6s ease-out;
            }
            @keyframes pulse-glow {
                0%, 50%, 100% { 
                    opacity: 1;
                    transform: scale(1);
                    box-shadow: 0 0 4px rgba(255, 215, 0, 0.6);
                }
                25%, 75% { 
                    opacity: 0.7;
                    transform: scale(0.9);
                    box-shadow: 0 0 8px rgba(255, 215, 0, 0.8);
                }
            }
            @keyframes success-ping {
                0% { transform: scale(1); }
                50% { transform: scale(1.2); }
                100% { transform: scale(1); }
            }
            @keyframes error-shake {
                0%, 100% { transform: translateX(0); }
                25% { transform: translateX(-2px); }
                75% { transform: translateX(2px); }
            }
            .chart-status {
                transition: all 0.3s ease;
            }
            .chart-status:hover {
                background: rgba(0, 0, 0, 0.9);
            }
        `;
        document.head.appendChild(style);
        
        this.container.style.position = 'relative';
        this.container.appendChild(this.statusElement);
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
        if (this.state === 'loading') {
            console.warn('Chart is loading, ignoring timeframe change');
            return;
        }
        
        console.log(`Updating timeframe from ${this.options.timeframe} to ${timeframe}`);
        this.options.timeframe = timeframe;
        this.updateTimeframeSelect(timeframe);
        this.loadData();
    }
    
    updateDays(days) {
        if (this.state === 'loading') {
            console.warn('Chart is loading, ignoring period change');
            return;
        }
        
        console.log(`Updating period from ${this.options.days} to ${days}`);
        this.options.days = days;
        this.loadData();
    }
    
    refreshData() {
        if (this.state === 'loading') {
            console.warn('Chart is already loading, ignoring refresh request');
            return;
        }
        
        console.log('Refreshing chart data');
        this.clearErrors();
        this.loadData();
    }
    
    clearErrors() {
        // Remove any existing error messages
        const existingErrors = this.container.querySelectorAll('.chart-error');
        existingErrors.forEach(error => error.remove());
    }
    
    updateInstrument(instrument) {
        this.options.instrument = instrument;
        this.clearMarkers();
        this.loadData();
    }
    
    toggleVolume(visible) {
        this.volumeVisible = visible;
        if (this.volumeSeries) {
            this.chart.removeSeries(this.volumeSeries);
            this.volumeSeries = null;
        }
        
        if (visible) {
            // Re-create volume series
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
            
            // Re-load volume data if we have it
            if (this.cachedVolumeData) {
                this.volumeSeries.setData(this.cachedVolumeData);
            }
        }
    }
    
    updateTimeframeSelect(timeframe) {
        // Update timeframe select dropdowns that control this chart
        const selectors = [
            document.querySelector(`[data-chart-id="${this.containerId}"] .timeframe-select`),
            document.querySelector(`#timeframeSelect`),
            document.querySelector(`[data-target-chart="${this.containerId}"] select[name="timeframe"]`)
        ];
        
        selectors.forEach(select => {
            if (select && select.value !== timeframe) {
                select.value = timeframe;
                console.log(`🔄 Updated timeframe select to: ${timeframe}`);
            }
        });
    }
    
    static bindChartControls(chartInstance) {
        const containerId = chartInstance.containerId;
        
        // Find controls that should control this chart
        const timeframeSelect = document.querySelector('#timeframeSelect') || 
                              document.querySelector(`[data-target-chart="${containerId}"] select[name="timeframe"]`);
        const daysSelect = document.querySelector('#daysSelect') || 
                          document.querySelector(`[data-target-chart="${containerId}"] select[name="days"]`);
        const refreshBtn = document.querySelector('#refreshDataBtn') || 
                          document.querySelector(`[data-target-chart="${containerId}"] button[data-action="refresh"]`);
        
        // Bind timeframe control
        if (timeframeSelect && !timeframeSelect.hasChartBinding) {
            timeframeSelect.addEventListener('change', function() {
                console.log(`Timeframe changed to: ${this.value}`);
                chartInstance.updateTimeframe(this.value);
            });
            timeframeSelect.hasChartBinding = true;
            console.log('✅ Timeframe control bound to chart');
        }
        
        // Bind period control
        if (daysSelect && !daysSelect.hasChartBinding) {
            daysSelect.addEventListener('change', function() {
                console.log(`Period changed to: ${this.value} days`);
                chartInstance.updateDays(parseInt(this.value));
            });
            daysSelect.hasChartBinding = true;
            console.log('✅ Period control bound to chart');
        }
        
        // Bind refresh control
        if (refreshBtn && !refreshBtn.hasChartBinding) {
            refreshBtn.addEventListener('click', function(event) {
                event.preventDefault();
                console.log('Refresh button clicked');
                chartInstance.refreshData();
            });
            refreshBtn.hasChartBinding = true;
            console.log('✅ Refresh control bound to chart');
        }
        
        // Store reference to chart instance on container for external access
        const container = document.getElementById(containerId);
        if (container) {
            container.chartInstance = chartInstance;
        }
        
        // Set initial control states
        chartInstance.updateControlStates(false);
        
        console.log('✅ Chart controls successfully bound and initialized');
    }
    
    initOhlcDisplay() {
        // Create OHLC overlay element
        this.ohlcDisplayEl = document.createElement('div');
        this.ohlcDisplayEl.className = 'ohlc-display';
        
        // Apply styles for professional trading app appearance
        Object.assign(this.ohlcDisplayEl.style, {
            position: 'absolute',
            zIndex: '100',
            backgroundColor: 'rgba(43, 43, 43, 0.95)', // Semi-transparent
            color: '#e5e5e5',
            fontFamily: 'monospace',
            fontSize: '12px',
            padding: '12px 16px',
            borderRadius: '6px',
            pointerEvents: 'none', // Prevents blocking chart interaction
            whiteSpace: 'nowrap',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.6)',
            border: '1px solid #555',
            backdropFilter: 'blur(4px)', // Modern blur effect
            top: '15px',
            right: '15px',
            display: 'none', // Hidden by default
            minWidth: '160px',
            transition: 'opacity 0.2s ease-in-out'
        });
        
        this.container.appendChild(this.ohlcDisplayEl);
        console.log('✅ OHLC display overlay created');
    }
    
    subscribeToEvents() {
        // Subscribe to crosshair move events for OHLC display
        this.crosshairMoveHandler = param => this.handleCrosshairMove(param);
        this.chart.subscribeCrosshairMove(this.crosshairMoveHandler);
        console.log('✅ Crosshair event subscription registered');
    }
    
    setupSettingsListener() {
        // Listen for global settings updates
        this.settingsUpdateHandler = (event) => {
            const newSettings = event.detail.settings;
            console.log('⚙️ Received chart settings update:', newSettings);
            
            // Update volume visibility if it changed
            if (newSettings.volume_visibility !== undefined && newSettings.volume_visibility !== this.volumeVisible) {
                console.log(`📊 Updating volume visibility: ${this.volumeVisible} → ${newSettings.volume_visibility}`);
                this.toggleVolume(newSettings.volume_visibility);
            }
            
            // Note: timeframe and data range changes don't auto-reload existing charts
            // User can manually change these via chart controls
        };
        
        document.addEventListener('chartSettingsUpdated', this.settingsUpdateHandler);
        console.log('✅ Settings update listener registered');
    }
    
    handleCrosshairMove(param) {
        if (param.point) {
            // Check if there's data for the candlestick series at this point
            if (param.seriesData.has(this.candlestickSeries)) {
                const dataPoint = param.seriesData.get(this.candlestickSeries);
                if (dataPoint) {
                    const ohlc = {
                        time: param.time, // Include timestamp from crosshair position
                        open: dataPoint.open,
                        high: dataPoint.high,
                        low: dataPoint.low,
                        close: dataPoint.close,
                        volume: dataPoint.volume || 0
                    };
                    
                    // Add volume data if volume series is available
                    if (this.volumeSeries && param.seriesData.has(this.volumeSeries)) {
                        const volumePoint = param.seriesData.get(this.volumeSeries);
                        if (volumePoint && volumePoint.value) {
                            ohlc.volume = volumePoint.value;
                        }
                    }
                    
                    this.updateOhlcDisplay(ohlc);
                } else {
                    // No candle data at this exact time (e.g., gap)
                    this.hideOhlcDisplay();
                }
            } else {
                // Candlestick series not present in param.seriesData
                this.hideOhlcDisplay();
            }
        } else {
            // Mouse is outside the chart area
            this.hideOhlcDisplay();
        }
    }
    
    updateOhlcDisplay(ohlc) {
        // Format values with appropriate precision for futures
        const formattedO = ohlc.open.toFixed(2);
        const formattedH = ohlc.high.toFixed(2);
        const formattedL = ohlc.low.toFixed(2);
        const formattedC = ohlc.close.toFixed(2);
        
        // Calculate price change and percentage
        const priceChange = ohlc.close - ohlc.open;
        const priceChangePercent = ((priceChange / ohlc.open) * 100).toFixed(2);
        const isPositive = priceChange >= 0;
        const changeColor = isPositive ? '#4caf50' : '#f44336';
        const changeSymbol = isPositive ? '+' : '';
        
        // Format volume with thousands separators
        const formattedVolume = ohlc.volume ? ohlc.volume.toLocaleString() : 'N/A';
        
        // Format timestamp based on timeframe
        let formattedTime = '';
        if (ohlc.time) {
            const date = new Date(ohlc.time * 1000); // Convert from seconds to milliseconds
            
            // Format based on current timeframe for best readability
            if (this.options.timeframe === '1m' || this.options.timeframe === '5m' || this.options.timeframe === '15m') {
                // For intraday timeframes, show date and time
                formattedTime = date.toLocaleString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                });
            } else if (this.options.timeframe === '1h' || this.options.timeframe === '4h') {
                // For hourly timeframes, show date and hour
                formattedTime = date.toLocaleString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                });
            } else {
                // For daily timeframes, show just the date
                formattedTime = date.toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric'
                });
            }
        }

        this.ohlcDisplayEl.innerHTML = `
            <div style="margin-bottom: 6px; font-weight: bold; color: #ffd700; border-bottom: 1px solid #444; padding-bottom: 4px;">
                ${formattedTime}
            </div>
            <div style="margin-bottom: 4px;">
                <span style="margin-right: 12px; color: #b0b0b0;">O:</span><span style="color: #e5e5e5;">${formattedO}</span>
                <span style="margin-left: 12px; margin-right: 12px; color: #b0b0b0;">H:</span><span style="color: #4caf50;">${formattedH}</span>
            </div>
            <div style="margin-bottom: 4px;">
                <span style="margin-right: 12px; color: #b0b0b0;">L:</span><span style="color: #f44336;">${formattedL}</span>
                <span style="margin-left: 12px; margin-right: 12px; color: #b0b0b0;">C:</span><span style="color: #e5e5e5;">${formattedC}</span>
            </div>
            <div style="margin-bottom: 4px;">
                <span style="margin-right: 12px; color: #b0b0b0;">Vol:</span><span style="color: #9c27b0;">${formattedVolume}</span>
            </div>
            <div style="padding-top: 4px; border-top: 1px solid #444;">
                <span style="color: ${changeColor}; font-weight: bold;">
                    ${changeSymbol}${priceChange.toFixed(2)} (${changeSymbol}${priceChangePercent}%)
                </span>
            </div>
        `;
        // Show with smooth animation
        this.ohlcDisplayEl.style.display = 'block';
        this.ohlcDisplayEl.style.opacity = '1';
    }
    
    hideOhlcDisplay() {
        if (this.ohlcDisplayEl) {
            // Hide with smooth animation
            this.ohlcDisplayEl.style.opacity = '0';
            setTimeout(() => {
                if (this.ohlcDisplayEl) {
                    this.ohlcDisplayEl.style.display = 'none';
                }
            }, 200); // Match transition duration
        }
    }


    
    showError(message, availableTimeframes = null) {
        console.error('Chart error:', message);
        
        // Remove existing error elements
        const existingError = this.container.querySelector('.chart-error');
        if (existingError) {
            existingError.remove();
        }
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'chart-error';
        
        let errorContent = `
            <div class="error-icon">⚠️</div>
            <div class="error-message">${message}</div>
        `;
        
        // Add retry button and timeframe suggestions if available
        if (availableTimeframes && availableTimeframes.length > 0) {
            errorContent += `
                <div class="error-suggestions">
                    <p>Try these available timeframes:</p>
                    <div class="timeframe-buttons">
                        ${availableTimeframes.map(tf => 
                            `<button class="timeframe-btn" onclick="this.closest('.chart-error').dispatchEvent(new CustomEvent('timeframeChange', {detail: '${tf}'}))">${tf}</button>`
                        ).join('')}
                    </div>
                </div>
            `;
        }
        
        errorContent += `
            <div class="error-actions">
                <button class="retry-btn" onclick="this.closest('.chart-error').dispatchEvent(new CustomEvent('retry'))">🔄 Retry</button>
                <button class="close-btn" onclick="this.closest('.chart-error').remove()">×</button>
            </div>
        `;
        
        errorDiv.innerHTML = errorContent;
        
        errorDiv.style.cssText = `
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(248, 215, 218, 0.95);
            color: #721c24;
            border: 2px solid #f5c6cb;
            border-radius: 8px;
            z-index: 1000;
            max-width: 400px;
            min-width: 300px;
            padding: 0;
            backdrop-filter: blur(4px);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        `;
        
        // Style internal elements
        const style = document.createElement('style');
        style.textContent = `
            .chart-error .error-icon {
                font-size: 32px;
                margin-bottom: 12px;
            }
            .chart-error .error-message {
                font-size: 14px;
                margin-bottom: 16px;
                line-height: 1.4;
            }
            .chart-error .error-suggestions {
                margin-bottom: 16px;
                padding-top: 12px;
                border-top: 1px solid #f5c6cb;
            }
            .chart-error .error-suggestions p {
                margin: 0 0 8px 0;
                font-size: 13px;
                color: #856404;
            }
            .chart-error .timeframe-buttons {
                display: flex;
                gap: 6px;
                flex-wrap: wrap;
                justify-content: center;
            }
            .chart-error .timeframe-btn {
                padding: 4px 8px;
                font-size: 11px;
                background: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                transition: background 0.2s;
            }
            .chart-error .timeframe-btn:hover {
                background: #0056b3;
            }
            .chart-error .error-actions {
                display: flex;
                justify-content: center;
                gap: 10px;
                padding: 16px;
                border-top: 1px solid #f5c6cb;
                background: rgba(255, 255, 255, 0.5);
                border-radius: 0 0 6px 6px;
            }
            .chart-error .retry-btn {
                padding: 8px 16px;
                background: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                transition: all 0.2s;
                font-weight: 500;
            }
            .chart-error .retry-btn:hover {
                background: #218838;
                transform: translateY(-1px);
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            .chart-error .retry-btn:active {
                transform: translateY(0);
            }
            .chart-error .close-btn {
                padding: 8px 12px;
                background: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                transition: all 0.2s;
            }
            .chart-error .close-btn:hover {
                background: #5a6268;
                transform: translateY(-1px);
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            .chart-error .close-btn:active {
                transform: translateY(0);
            }
            .chart-error {
                animation: errorSlideIn 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
            }
            @keyframes errorSlideIn {
                0% {
                    transform: translate(-50%, -50%) scale(0.8);
                    opacity: 0;
                }
                100% {
                    transform: translate(-50%, -50%) scale(1);
                    opacity: 1;
                }
            }
        `;
        
        if (!document.querySelector('#chart-error-styles')) {
            style.id = 'chart-error-styles';
            document.head.appendChild(style);
        }
        
        // Add event handlers
        errorDiv.addEventListener('retry', () => {
            this.updateStatus('loading', 'Retrying...');
            errorDiv.remove();
            // Add small delay to show retry feedback
            setTimeout(() => {
                this.loadData();
            }, 200);
        });
        
        errorDiv.addEventListener('timeframeChange', (event) => {
            const newTimeframe = event.detail;
            errorDiv.remove();
            this.updateStatus('loading', `Switching to ${newTimeframe}...`);
            // Add small delay to show switch feedback
            setTimeout(() => {
                this.updateTimeframe(newTimeframe);
            }, 200);
        });
        
        this.container.appendChild(errorDiv);
        
        // Auto-dismiss error after 15 seconds if no user interaction
        setTimeout(() => {
            if (errorDiv.parentNode && this.state === 'error') {
                errorDiv.style.opacity = '0.8';
                errorDiv.querySelector('.error-message').innerHTML += '<br><small><em>This error will auto-dismiss in 15 seconds...</em></small>';
                
                setTimeout(() => {
                    if (errorDiv.parentNode) {
                        errorDiv.remove();
                    }
                }, 15000);
            }
        }, 15000);
    }
    
    /**
     * Add a horizontal price line at the specified price level
     * @param {number} price - Price level for the horizontal line
     * @param {Object} options - Configuration options for the price line
     * @returns {Object} The created price line object
     */
    addPriceLine(price, options = {}) {
        if (!this.candlestickSeries) {
            console.warn('Cannot add price line: candlestick series not initialized');
            return null;
        }
        
        const defaultOptions = {
            price: price,
            color: '#FFD700', // Gold color for default entry price
            lineWidth: 2,
            lineStyle: (typeof LightweightCharts !== 'undefined' && 
                       LightweightCharts.LineStyle && 
                       LightweightCharts.LineStyle.Solid) ? 
                       LightweightCharts.LineStyle.Solid : 0,
            axisLabelVisible: true,
            title: `Entry: ${price.toFixed(2)}`
        };
        
        const lineOptions = { ...defaultOptions, ...options };
        
        try {
            const priceLine = this.candlestickSeries.createPriceLine(lineOptions);
            
            const lineData = {
                line: priceLine,
                price: price,
                ...lineOptions
            };
            
            this.priceLines.push(lineData);
            console.log(`✅ Added price line at ${price} with color ${lineOptions.color}`);
            
            return lineData;
        } catch (error) {
            console.error('❌ Error adding price line:', error);
            return null;
        }
    }
    
    /**
     * Add position entry price lines based on position data
     * @param {Array} entryPrices - Array of entry price data objects
     */
    addPositionEntryLines(entryPrices) {
        if (!Array.isArray(entryPrices)) {
            console.warn('entryPrices must be an array');
            return;
        }
        
        // Clear existing position lines first
        this.clearPositionLines();
        
        entryPrices.forEach((entryData, index) => {
            if (!entryData.price || isNaN(entryData.price)) {
                console.warn(`Invalid price data at index ${index}:`, entryData);
                return;
            }
            
            // Use the color from entry data if provided, otherwise determine based on position side and type
            let color = entryData.color;
            if (!color) {
                if (entryData.type === 'average_entry') {
                    color = '#4CAF50'; // Green for average entry price
                } else if (entryData.side === 'Long' || entryData.side === 'Buy') {
                    color = '#4CAF50'; // Green for long positions
                } else if (entryData.side === 'Short' || entryData.side === 'Sell') {
                    color = '#F44336'; // Red for short positions
                } else {
                    color = '#FFD700'; // Gold for unknown/neutral
                }
            }
            
            // Use solid line for average entry, dashed for others
            let lineStyle = (typeof LightweightCharts !== 'undefined' && 
                            LightweightCharts.LineStyle && 
                            LightweightCharts.LineStyle.Solid) ? 
                            LightweightCharts.LineStyle.Solid : 0;
            
            if (entryData.type === 'individual_entry') {
                lineStyle = (typeof LightweightCharts !== 'undefined' && 
                            LightweightCharts.LineStyle && 
                            LightweightCharts.LineStyle.Dashed) ? 
                            LightweightCharts.LineStyle.Dashed : 1;
            }
            
            // Set line width - thicker for average entry
            const lineWidth = (entryData.type === 'average_entry') ? 3 : 2;
            
            this.addPriceLine(entryData.price, {
                color: color,
                title: entryData.label || `${entryData.side || 'Position'} Entry: ${entryData.price.toFixed(2)}`,
                lineStyle: lineStyle,
                lineWidth: lineWidth,
                axisLabelVisible: true
            });
            
            console.log(`📊 Added ${entryData.type || 'entry'} price line at ${entryData.price.toFixed(2)} (${color})`);
        });
        
        console.log(`✅ Added ${entryPrices.length} position entry price lines`);
    }
    
    /**
     * Clear all position-specific price lines
     */
    clearPositionLines() {
        if (!this.candlestickSeries) {
            return;
        }
        
        this.priceLines.forEach(lineData => {
            try {
                this.candlestickSeries.removePriceLine(lineData.line);
            } catch (error) {
                console.warn('Error removing price line:', error);
            }
        });
        
        this.priceLines = [];
        console.log('✅ Cleared all position price lines');
    }
    
    /**
     * Remove a specific price line
     * @param {Object} lineData - The price line data object returned by addPriceLine
     */
    removePriceLine(lineData) {
        if (!this.candlestickSeries || !lineData || !lineData.line) {
            return;
        }
        
        try {
            this.candlestickSeries.removePriceLine(lineData.line);
            
            // Remove from tracked lines
            const index = this.priceLines.indexOf(lineData);
            if (index > -1) {
                this.priceLines.splice(index, 1);
            }
            
            console.log(`✅ Removed price line at ${lineData.price}`);
        } catch (error) {
            console.error('❌ Error removing price line:', error);
        }
    }
    
    destroy() {
        // Clear position price lines before destroying chart
        this.clearPositionLines();
        
        // Clear any error messages
        this.clearErrors();
        
        // Unsubscribe from crosshair events to prevent memory leaks
        if (this.chart && this.crosshairMoveHandler) {
            this.chart.unsubscribeCrosshairMove(this.crosshairMoveHandler);
            this.crosshairMoveHandler = null;
        }
        
        // Unsubscribe from settings updates
        if (this.settingsUpdateHandler) {
            document.removeEventListener('chartSettingsUpdated', this.settingsUpdateHandler);
            this.settingsUpdateHandler = null;
        }
        
        if (this.chart) {
            this.chart.remove();
            this.chart = null;
        }
        
        // Remove OHLC display element
        if (this.ohlcDisplayEl && this.ohlcDisplayEl.parentNode) {
            this.ohlcDisplayEl.parentNode.removeChild(this.ohlcDisplayEl);
            this.ohlcDisplayEl = null;
        }
        
        // Remove status element
        if (this.statusElement && this.statusElement.parentNode) {
            this.statusElement.parentNode.removeChild(this.statusElement);
            this.statusElement = null;
        }
        
        // Remove loading overlay
        this.hideLoadingOverlay();
        
        // Restore control states
        this.updateControlStates(false);
        
        // Clear references to prevent memory leaks
        this.candlestickSeries = null;
        this.volumeSeries = null;
        this.markers = [];
        this.priceLines = [];
        this.container = null;
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
            
            // Register chart instance globally for external access
            if (!window.chartInstances) {
                window.chartInstances = [];
            }
            window.chartInstances.push(chart);
            
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