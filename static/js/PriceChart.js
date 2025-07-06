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
            this.showLoading(true);
            console.log(`🔍 Loading chart data for ${this.options.instrument}, timeframe: ${this.options.timeframe}, days: ${this.options.days}`);
            
            // Use adaptive endpoint for automatic resolution optimization
            let url = `/api/chart-data-adaptive/${this.options.instrument}?timeframe=${this.options.timeframe}&days=${this.options.days}`;
            console.log(`📡 Fetching from adaptive endpoint: ${url}`);
            
            let response = await fetch(url);
            console.log(`📊 Response status: ${response.status} ${response.statusText}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            let data = await response.json();
            console.log(`📈 Adaptive API Response:`, {
                success: data.success,
                count: data.count,
                hasData: !!(data.data && data.data.length > 0),
                instrument: data.instrument,
                requestedTimeframe: data.requested_timeframe,
                actualTimeframe: data.actual_timeframe,
                resolutionAdapted: data.resolution_adapted,
                estimatedCandles: data.estimated_candles,
                performanceWarning: data.performance_warning
            });
            
            // Show resolution adaptation info to user
            if (data.resolution_adapted) {
                console.log(`🔄 Resolution adapted: ${data.requested_timeframe} → ${data.actual_timeframe} for ${data.days} days (${data.estimated_candles:,} candles)`);
                this.showResolutionAdaptationNotice(data.requested_timeframe, data.actual_timeframe, data.days);
            }
            
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
                        
                        if (timeframesData.has_data && timeframesData.best_timeframe) {
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
                        } else if (timeframesData.fetch_attempted && timeframesData.fetch_error) {
                            console.error(`❌ Data fetch failed for ${this.options.instrument}: ${timeframesData.fetch_error}`);
                            this.showError(`Unable to load market data for ${this.options.instrument}. ${timeframesData.fetch_error}`);
                            return;
                        } else if (!timeframesData.has_data) {
                            console.warn(`⚠️ No data available for ${this.options.instrument} in any timeframe`);
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
            // Set data to candlestick series
            this.candlestickSeries.setData(candlestickData);
            
            // Cache volume data for toggle functionality
            this.cachedVolumeData = volumeData;
            
            // Set volume data only if volume is visible
            if (this.volumeVisible && this.volumeSeries) {
                this.volumeSeries.setData(volumeData);
            }
            
            // Fit content to show all data with auto-scaling
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
        // Update the timeframe select dropdown to reflect the current timeframe
        const timeframeSelect = document.querySelector(`[data-chart-id="${this.containerId}"].timeframe-select`);
        if (timeframeSelect) {
            timeframeSelect.value = timeframe;
            console.log(`🔄 Updated timeframe select to: ${timeframe}`);
        }
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

    showLoading(show) {
        const loadingEl = this.container.querySelector('.chart-loading');
        if (loadingEl) {
            loadingEl.style.display = show ? 'block' : 'none';
        }
    }

    showResolutionAdaptationNotice(requestedTimeframe, actualTimeframe, days) {
        // Show a subtle notification that resolution was adapted for performance
        const notice = document.createElement('div');
        notice.className = 'resolution-adaptation-notice';
        notice.innerHTML = `
            <span class="notice-icon">🔄</span>
            <span class="notice-text">
                Resolution adapted to ${actualTimeframe} for ${days}-day range (was ${requestedTimeframe})
            </span>
            <button class="notice-close" onclick="this.parentElement.remove()">×</button>
        `;
        notice.style.cssText = `
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0, 123, 255, 0.9);
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            z-index: 1000;
            display: flex;
            align-items: center;
            gap: 8px;
            max-width: 300px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        `;
        
        this.container.style.position = 'relative';
        this.container.appendChild(notice);
        
        // Auto-hide after 8 seconds
        setTimeout(() => {
            if (notice.parentElement) {
                notice.remove();
            }
        }, 8000);
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