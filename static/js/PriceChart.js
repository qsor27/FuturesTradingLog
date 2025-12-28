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
        this.executionArrows = []; // Store execution arrow markers
        this.arrowTooltip = null; // Tooltip element for execution arrows
        this.currentTimeframe = options.timeframe || '1h'; // Track current timeframe for arrow positioning
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
            start_date: null, // Auto-centered start date from backend
            end_date: null, // Auto-centered end date from backend
            width: this.container.clientWidth || this.container.parentElement?.clientWidth || 800,
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
                rightBarStaysOnScroll: true,
                minBarSpacing: 0.5, // Allow very narrow bars to fit all data in view
            },
            ...this.userOptions
        };

        // Read date range attributes from container for auto-centering
        // These take precedence over days parameter when both are present
        if (this.container.dataset.startDate) {
            this.options.start_date = this.container.dataset.startDate;
            console.log(`📅 Read start_date from container: ${this.options.start_date}`);
        }

        if (this.container.dataset.endDate) {
            this.options.end_date = this.container.dataset.endDate;
            console.log(`📅 Read end_date from container: ${this.options.end_date}`);
        }
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

        // Debug container dimensions before chart creation
        console.log(`📐 Container dimensions before chart creation:`);
        console.log(`   clientWidth: ${this.container.clientWidth}`);
        console.log(`   clientHeight: ${this.container.clientHeight}`);
        console.log(`   offsetWidth: ${this.container.offsetWidth}`);
        console.log(`   offsetHeight: ${this.container.offsetHeight}`);
        const rect = this.container.getBoundingClientRect();
        console.log(`   boundingRect: ${rect.width}x${rect.height}`);
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

            // Build API URL with date parameters if available
            let url = `/api/chart-data/${this.options.instrument}?timeframe=${this.options.timeframe}`;

            // Check if start_date and end_date are set for auto-centering
            if (this.options.start_date && this.options.end_date) {
                // Use date range parameters for auto-centered view
                url += `&start_date=${encodeURIComponent(this.options.start_date)}`;
                url += `&end_date=${encodeURIComponent(this.options.end_date)}`;
                console.log(`🔍 AUTO-CENTER: Using date range - Start: ${this.options.start_date}, End: ${this.options.end_date}`);
            }

            // Always include days parameter for backward compatibility and fallback
            url += `&days=${this.options.days}`;

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
                    // Check if there are available timeframes to fallback to
                    if (data.available_timeframes && Object.keys(data.available_timeframes).length > 0) {
                        const availableTimeframes = Object.keys(data.available_timeframes);
                        const bestTimeframe = data.best_timeframe || availableTimeframes[0];

                        // Only auto-fallback if we haven't already tried this timeframe
                        if (bestTimeframe && bestTimeframe !== this.options.timeframe) {
                            console.log(`⚠️ No data for ${this.options.timeframe}, auto-switching to available timeframe: ${bestTimeframe}`);
                            this.updateStatus('loading', `No ${this.options.timeframe} data, trying ${bestTimeframe}...`);

                            // Update timeframe directly (bypass updateTimeframe() which blocks during loading)
                            this.options.timeframe = bestTimeframe;
                            this.currentTimeframe = bestTimeframe;
                            this.updateTimeframeSelect(bestTimeframe);

                            // Recursively call loadData with new timeframe
                            // Use a flag to prevent infinite loops
                            if (!this._fallbackAttempted) {
                                this._fallbackAttempted = true;
                                this.loadData();
                                return;
                            }
                        }
                    }

                    // No available timeframes or already tried - show error
                    this._fallbackAttempted = false; // Reset flag
                    const noDataMessage = this.getNoDataMessage(data);
                    this.showError(noDataMessage, data.available_timeframes);
                    return;
                }

                // Reset fallback flag on successful load
                this._fallbackAttempted = false;

                console.log(`✅ Received ${data.data.length} data points`);
                this.setData(data.data);
                this.updateStatus('ready', `Loaded ${data.count.toLocaleString()} candles`);
                this.hideLoadingOverlay();

                // Check for contract fallback and show warning if applicable
                if (data.metadata && data.metadata.is_fallback) {
                    this.showContractWarning(
                        data.metadata.requested_instrument,
                        data.metadata.actual_instrument,
                        data.metadata.is_continuous_fallback
                    );
                } else {
                    this.hideContractWarning();
                }

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

            // Cache the chart data for centering calculations
            this.chartData = candlestickData;

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

            console.log(`🎉 Successfully loaded ${candlestickData.length} candles for ${this.options.instrument}`);

            // Fit all data initially - if this chart has execution arrows, they will
            // be loaded later and will center the view on the position's execution times
            const timeScale = this.chart.timeScale();
            const dataLength = candlestickData.length;

            // Log data range for debugging
            const firstCandle = candlestickData[0];
            const lastCandle = candlestickData[dataLength - 1];
            console.log(`📊 Data range: first=${firstCandle.time} (${new Date(firstCandle.time * 1000).toISOString()})`);
            console.log(`📊 Data range: last=${lastCandle.time} (${new Date(lastCandle.time * 1000).toISOString()})`);
            console.log(`📊 Total candles: ${dataLength}`);

            // If execution arrows have been loaded, center on them
            // Otherwise, call fitContent to show all data
            if (this.pendingExecutionCenter) {
                console.log(`📌 Execution center pending, centering now after data load (skipping fitContent)`);
                // Don't call fitContent - let centerOnExecutions handle the view
                this.centerOnExecutions();
            } else {
                // No execution data - show all data
                timeScale.fitContent();
                console.log(`✅ Called fitContent() for ${dataLength} candles (no execution data pending)`);
            }

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

    showContractWarning(requestedInstrument, actualInstrument, isContinuous) {
        // Remove any existing warning
        this.hideContractWarning();

        const warningDiv = document.createElement('div');
        warningDiv.className = 'chart-contract-warning';
        warningDiv.id = `contract-warning-${this.containerId}`;

        const warningIcon = isContinuous ? '⚠️' : 'ℹ️';
        const warningText = isContinuous
            ? `Showing continuous contract (${actualInstrument}) - specific data for ${requestedInstrument} not available`
            : `Showing data from ${actualInstrument} - specific data for ${requestedInstrument} not available`;

        warningDiv.innerHTML = `
            <span class="warning-icon">${warningIcon}</span>
            <span class="warning-text">${warningText}</span>
            <button class="warning-dismiss" onclick="this.parentElement.remove()" title="Dismiss">&times;</button>
        `;

        // Insert at top of chart container
        if (this.container) {
            this.container.style.position = 'relative';
            this.container.insertBefore(warningDiv, this.container.firstChild);
        }
    }

    hideContractWarning() {
        const existingWarning = document.getElementById(`contract-warning-${this.containerId}`);
        if (existingWarning) {
            existingWarning.remove();
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

    /**
     * Add execution arrow markers to the chart
     * @param {Array} executions - Array of execution objects with timestamp, price, quantity, side, type
     */
    addExecutionArrows(executions) {
        if (!Array.isArray(executions) || executions.length === 0) {
            console.warn('No executions provided for arrow rendering');
            return;
        }

        console.log(`🏹 Adding ${executions.length} execution arrows to chart`);

        // Clear existing execution arrows
        this.clearExecutionArrows();

        // Process executions into arrow markers
        const arrowMarkers = executions
            .filter(execution => this.isValidExecution(execution))
            .map(execution => this.createExecutionArrowMarker(execution))
            .filter(marker => marker !== null);

        console.log(`✅ Created ${arrowMarkers.length} valid arrow markers`);

        // Store arrow markers
        this.executionArrows = arrowMarkers;

        // Combine with existing markers and update chart
        this.updateChartMarkers();

        // Setup interactive features
        this.setupArrowInteractions();

        console.log(`🎯 Execution arrows successfully added to chart`);
    }

    /**
     * Create an arrow marker from execution data
     * @param {Object} execution - Execution object
     * @returns {Object} Arrow marker object for TradingView
     */
    createExecutionArrowMarker(execution) {
        try {
            // Convert timestamp to Unix timestamp for TradingView
            const timestamp = this.alignExecutionTimestamp(execution.timestamp, this.currentTimeframe);

            // Determine arrow properties based on execution type and side
            const arrowProps = this.getArrowProperties(execution);

            // Create marker object
            const marker = {
                time: timestamp,
                position: arrowProps.position,
                color: arrowProps.color,
                shape: arrowProps.shape,
                text: this.formatArrowText(execution),
                id: `execution_${execution.execution_id}`,
                size: this.calculateArrowSize(),
                execution: execution // Store execution data for interactions
            };

            console.log(`📍 Created arrow marker:`, marker);
            return marker;

        } catch (error) {
            console.error('❌ Error creating execution arrow marker:', error, execution);
            return null;
        }
    }

    /**
     * Validate execution data for arrow rendering
     * @param {Object} execution - Execution object to validate
     * @returns {boolean} True if execution is valid
     */
    isValidExecution(execution) {
        if (!execution) return false;

        const required = ['execution_id', 'timestamp', 'price', 'quantity', 'side', 'type'];
        const missing = required.filter(field => !execution.hasOwnProperty(field) || execution[field] === null);

        if (missing.length > 0) {
            console.warn(`Invalid execution - missing fields: ${missing.join(', ')}`, execution);
            return false;
        }

        if (typeof execution.price !== 'number' || isNaN(execution.price)) {
            console.warn('Invalid execution - price must be a number', execution);
            return false;
        }

        if (!['Buy', 'Sell'].includes(execution.side)) {
            console.warn('Invalid execution - side must be Buy or Sell', execution);
            return false;
        }

        if (!['entry', 'exit'].includes(execution.type)) {
            console.warn('Invalid execution - type must be entry or exit', execution);
            return false;
        }

        return true;
    }

    /**
     * Align execution timestamp to chart timeframe boundaries
     * @param {string} timestamp - ISO timestamp string
     * @param {string} timeframe - Chart timeframe (1m, 5m, 1h, etc.)
     * @returns {number} Aligned Unix timestamp
     */
    alignExecutionTimestamp(timestamp, timeframe) {
        const date = new Date(timestamp);
        let alignedDate = new Date(date);

        // Align to timeframe boundaries for better arrow positioning
        switch (timeframe) {
            case '1m':
                alignedDate.setSeconds(0, 0);
                break;
            case '5m':
                const minutes5 = Math.floor(date.getMinutes() / 5) * 5;
                alignedDate.setMinutes(minutes5, 0, 0);
                break;
            case '15m':
                const minutes15 = Math.floor(date.getMinutes() / 15) * 15;
                alignedDate.setMinutes(minutes15, 0, 0);
                break;
            case '1h':
                alignedDate.setMinutes(0, 0, 0);
                break;
            case '4h':
                const hours4 = Math.floor(date.getHours() / 4) * 4;
                alignedDate.setHours(hours4, 0, 0, 0);
                break;
            case '1d':
                alignedDate.setHours(0, 0, 0, 0);
                break;
            default:
                // Default to exact timestamp for unknown timeframes
                break;
        }

        return Math.floor(alignedDate.getTime() / 1000); // Convert to Unix timestamp
    }

    /**
     * Determine arrow visual properties based on execution
     * @param {Object} execution - Execution object
     * @returns {Object} Arrow properties (position, color, shape)
     */
    getArrowProperties(execution) {
        const isBuy = execution.side === 'Buy';
        const isEntry = execution.type === 'entry';

        let position, color, shape;

        // Determine position and shape based on side and type
        if (isBuy) {
            position = 'belowBar';
            shape = 'arrowUp';
            color = '#4CAF50'; // Green for buy
        } else {
            position = 'aboveBar';
            shape = 'arrowDown';
            color = '#F44336'; // Red for sell
        }

        return { position, color, shape };
    }

    /**
     * Format arrow text display
     * @param {Object} execution - Execution object
     * @returns {string} Formatted text for arrow
     */
    formatArrowText(execution) {
        const type = execution.type.toUpperCase();
        const quantity = Math.abs(execution.quantity);
        const price = execution.price.toFixed(2);

        return `${type}: ${quantity}@${price}`;
    }

    /**
     * Calculate responsive arrow size based on chart dimensions
     * @returns {number} Arrow size multiplier
     */
    calculateArrowSize() {
        if (!this.container) return 1;

        const width = this.container.clientWidth;

        // Responsive sizing
        if (width < 600) {
            return 0.8; // Smaller arrows for small screens
        } else if (width < 1000) {
            return 1.0; // Default size for medium screens
        } else {
            return 1.2; // Larger arrows for large screens
        }
    }

    /**
     * Clear all execution arrow markers
     */
    clearExecutionArrows() {
        this.executionArrows = [];
        this.updateChartMarkers();
        this.clearArrowTooltip();
        console.log('🧹 Cleared all execution arrows');
    }

    /**
     * Update chart with all markers (existing + execution arrows)
     */
    updateChartMarkers() {
        if (!this.candlestickSeries) return;

        const allMarkers = [...this.markers, ...this.executionArrows];
        this.candlestickSeries.setMarkers(allMarkers);
        console.log(`📊 Updated chart with ${allMarkers.length} total markers`);
    }

    /**
     * Refresh execution arrows for timeframe changes
     */
    refreshExecutionArrows() {
        if (this.executionArrows.length === 0) return;

        console.log('🔄 Refreshing execution arrows for timeframe change');

        // Extract original execution data and re-process
        const executions = this.executionArrows.map(arrow => arrow.execution);
        this.addExecutionArrows(executions);
    }

    /**
     * Setup interactive features for execution arrows
     */
    setupArrowInteractions() {
        if (!this.chart) return;

        // Setup click handler for arrow-to-table linking
        this.chart.subscribeClick((param) => {
            this.handleArrowClick(param);
        });

        // Setup crosshair move handler for arrow tooltips
        this.chart.subscribeCrosshairMove((param) => {
            this.handleArrowHover(param);
        });

        console.log('🎮 Arrow interactions setup complete');
    }

    /**
     * Handle arrow click events for table row linking
     * @param {Object} param - TradingView click parameter
     */
    handleArrowClick(param) {
        if (!param.point || !param.time) return;

        // Find clicked arrow marker within tolerance
        const tolerance = 60; // 1 minute tolerance
        const clickedArrow = this.executionArrows.find(arrow =>
            Math.abs(arrow.time - param.time) < tolerance
        );

        if (clickedArrow) {
            console.log('🎯 Arrow clicked:', clickedArrow);
            this.highlightTableRow(clickedArrow.execution);
            this.highlightArrowTemporarily(clickedArrow);
        }
    }

    /**
     * Handle arrow hover events for tooltip display
     * @param {Object} param - TradingView crosshair parameter
     */
    handleArrowHover(param) {
        if (!param.point || !param.time) {
            this.hideArrowTooltip();
            return;
        }

        // Find arrow marker near crosshair
        const tolerance = 60; // 1 minute tolerance
        const hoveredArrow = this.executionArrows.find(arrow =>
            Math.abs(arrow.time - param.time) < tolerance
        );

        if (hoveredArrow) {
            this.showArrowTooltip(hoveredArrow, param.point);
        } else {
            this.hideArrowTooltip();
        }
    }

    /**
     * Show tooltip for execution arrow
     * @param {Object} arrow - Arrow marker object
     * @param {Object} point - Mouse point coordinates
     */
    showArrowTooltip(arrow, point) {
        if (!arrow.execution) return;

        // Create tooltip if it doesn't exist
        if (!this.arrowTooltip) {
            this.createArrowTooltip();
        }

        const execution = arrow.execution;
        const tooltipContent = this.formatTooltipContent(execution);

        // Update tooltip content
        this.arrowTooltip.innerHTML = tooltipContent;

        // Position tooltip to avoid chart obstruction
        const tooltipPos = this.calculateTooltipPosition(point);
        this.arrowTooltip.style.left = `${tooltipPos.x}px`;
        this.arrowTooltip.style.top = `${tooltipPos.y}px`;

        // Show tooltip with animation
        this.arrowTooltip.style.display = 'block';
        this.arrowTooltip.style.opacity = '1';

        console.log('💬 Showing arrow tooltip for execution:', execution.execution_id);
    }

    /**
     * Hide arrow tooltip
     */
    hideArrowTooltip() {
        if (this.arrowTooltip) {
            this.arrowTooltip.style.opacity = '0';
            setTimeout(() => {
                if (this.arrowTooltip) {
                    this.arrowTooltip.style.display = 'none';
                }
            }, 200);
        }
    }

    /**
     * Create tooltip element for execution arrows
     */
    createArrowTooltip() {
        this.arrowTooltip = document.createElement('div');
        this.arrowTooltip.className = 'execution-arrow-tooltip';

        // Apply mobile-responsive styles
        const isMobile = window.innerWidth < 768;
        const maxWidth = isMobile ? Math.min(300, window.innerWidth * 0.8) : 320;

        this.arrowTooltip.style.cssText = `
            position: absolute;
            z-index: 2000;
            background: rgba(43, 43, 43, 0.95);
            color: #e5e5e5;
            border: 1px solid #555;
            border-radius: 6px;
            padding: 12px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace;
            font-size: 12px;
            line-height: 1.4;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(4px);
            pointer-events: none;
            transition: opacity 0.2s ease;
            display: none;
            opacity: 0;
            max-width: ${maxWidth}px;
            word-wrap: break-word;
        `;

        this.container.appendChild(this.arrowTooltip);
        console.log('💬 Arrow tooltip element created');
    }

    /**
     * Format tooltip content for execution
     * @param {Object} execution - Execution object
     * @returns {string} HTML content for tooltip
     */
    formatTooltipContent(execution) {
        const time = new Date(execution.timestamp).toLocaleString();
        const price = `$${execution.price.toFixed(2)}`;
        const quantity = `${Math.abs(execution.quantity)} contracts`;
        const commission = execution.commission ? `$${execution.commission.toFixed(2)}` : 'N/A';
        const pnl = execution.pnl ? `$${execution.pnl.toFixed(2)}` : '$0.00';
        const pnlColor = execution.pnl >= 0 ? '#4CAF50' : '#F44336';

        return `
            <div style="margin-bottom: 8px; font-weight: bold; color: #ffd700; border-bottom: 1px solid #555; padding-bottom: 4px;">
                ${execution.type.toUpperCase()} EXECUTION
            </div>
            <div style="margin-bottom: 4px;">
                <span style="color: #b0b0b0;">Time:</span> <span style="color: #e5e5e5;">${time}</span>
            </div>
            <div style="margin-bottom: 4px;">
                <span style="color: #b0b0b0;">Price:</span> <span style="color: #e5e5e5;">${price}</span>
            </div>
            <div style="margin-bottom: 4px;">
                <span style="color: #b0b0b0;">Quantity:</span> <span style="color: #e5e5e5;">${quantity}</span>
            </div>
            <div style="margin-bottom: 4px;">
                <span style="color: #b0b0b0;">Side:</span> <span style="color: ${execution.side === 'Buy' ? '#4CAF50' : '#F44336'};">${execution.side}</span>
            </div>
            <div style="margin-bottom: 4px;">
                <span style="color: #b0b0b0;">Commission:</span> <span style="color: #e5e5e5;">${commission}</span>
            </div>
            <div>
                <span style="color: #b0b0b0;">P&L:</span> <span style="color: ${pnlColor};">${pnl}</span>
            </div>
        `;
    }

    /**
     * Calculate tooltip position to avoid chart obstruction
     * @param {Object} point - Mouse point coordinates
     * @returns {Object} Calculated position {x, y}
     */
    calculateTooltipPosition(point) {
        if (!this.arrowTooltip || !this.container) {
            return { x: point.x, y: point.y };
        }

        const containerRect = this.container.getBoundingClientRect();
        const tooltipWidth = 320; // Estimated tooltip width
        const tooltipHeight = 160; // Estimated tooltip height
        const margin = 10;

        let x = point.x + margin;
        let y = point.y - tooltipHeight - margin;

        // Adjust X position if tooltip would go off right edge
        if (x + tooltipWidth > containerRect.width) {
            x = point.x - tooltipWidth - margin;
        }

        // Adjust Y position if tooltip would go off top edge
        if (y < 0) {
            y = point.y + margin;
        }

        // Ensure tooltip stays within chart bounds
        x = Math.max(margin, Math.min(x, containerRect.width - tooltipWidth - margin));
        y = Math.max(margin, Math.min(y, containerRect.height - tooltipHeight - margin));

        return { x, y };
    }

    /**
     * Clear arrow tooltip element
     */
    clearArrowTooltip() {
        if (this.arrowTooltip && this.arrowTooltip.parentNode) {
            this.arrowTooltip.parentNode.removeChild(this.arrowTooltip);
            this.arrowTooltip = null;
        }
    }

    /**
     * Highlight table row corresponding to execution
     * @param {Object} execution - Execution object
     */
    highlightTableRow(execution) {
        // Dispatch custom event for table synchronization
        const event = new CustomEvent('executionArrowClick', {
            detail: {
                execution: execution,
                action: 'highlight_table_row',
                scroll_to_row: true,
                highlight_duration: 2000
            }
        });
        document.dispatchEvent(event);

        console.log('📋 Dispatched table row highlight event for execution:', execution.execution_id);
    }

    /**
     * Temporarily highlight an arrow marker
     * @param {Object} arrow - Arrow marker object
     */
    highlightArrowTemporarily(arrow) {
        if (!arrow) return;

        // Create temporary highlight marker
        const highlightMarker = {
            ...arrow,
            color: '#FFD700', // Gold highlight
            size: arrow.size * 1.5 // Larger size for highlight
        };

        // Replace arrow temporarily
        const arrowIndex = this.executionArrows.findIndex(a => a.id === arrow.id);
        if (arrowIndex !== -1) {
            const originalArrow = { ...this.executionArrows[arrowIndex] };
            this.executionArrows[arrowIndex] = highlightMarker;
            this.updateChartMarkers();

            // Reset after 2 seconds
            setTimeout(() => {
                if (arrowIndex < this.executionArrows.length) {
                    this.executionArrows[arrowIndex] = originalArrow;
                    this.updateChartMarkers();
                }
            }, 2000);
        }

        console.log('✨ Temporarily highlighted arrow:', arrow.id);
    }

    /**
     * Handle external table row interactions (bi-directional)
     * @param {Object} execution - Execution object to highlight
     */
    highlightArrowFromTable(execution) {
        const arrow = this.executionArrows.find(a =>
            a.execution && a.execution.execution_id === execution.execution_id
        );

        if (arrow) {
            this.highlightArrowTemporarily(arrow);

            // Scroll chart to show the arrow if it's outside visible range
            if (this.chart && this.chart.timeScale) {
                const visibleRange = this.chart.timeScale().getVisibleRange();
                if (visibleRange && (arrow.time < visibleRange.from || arrow.time > visibleRange.to)) {
                    // Center the arrow in the visible range
                    const rangeSize = visibleRange.to - visibleRange.from;
                    const newFrom = arrow.time - rangeSize / 2;
                    const newTo = arrow.time + rangeSize / 2;

                    this.chart.timeScale().setVisibleRange({ from: newFrom, to: newTo });
                    console.log('📍 Scrolled chart to show highlighted arrow');
                }
            }
        }
    }

    updateTimeframe(timeframe) {
        if (this.state === 'loading') {
            console.warn('Chart is loading, ignoring timeframe change');
            return;
        }

        console.log(`Updating timeframe from ${this.options.timeframe} to ${timeframe}`);
        this.options.timeframe = timeframe;
        this.currentTimeframe = timeframe;

        // Keep auto-centered dates when changing timeframe
        // This maintains the position-focused date range across timeframe changes
        if (this.options.start_date && this.options.end_date) {
            console.log('📅 Preserving auto-centered date range across timeframe change');
        }

        this.updateTimeframeSelect(timeframe);
        this.loadData();

        // Refresh execution arrows for new timeframe if they exist
        if (this.executionArrows.length > 0) {
            this.refreshExecutionArrows();
        }
    }

    updateDays(days) {
        if (this.state === 'loading') {
            console.warn('Chart is loading, ignoring period change');
            return;
        }

        console.log(`Updating period from ${this.options.days} to ${days}`);
        this.options.days = days;

        // Keep auto-centered dates when changing days
        // This maintains the position-focused date range across period changes
        if (this.options.start_date && this.options.end_date) {
            console.log('📅 Preserving auto-centered date range across period change');
        }

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

        // Clear execution arrows and tooltips
        this.clearExecutionArrows();

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
        this.executionArrows = [];
        this.priceLines = [];
        this.container = null;
    }

    /**
     * Load execution arrows from API data
     * Public method to be called from external scripts
     * @param {Array} executions - Array of execution data from API
     */
    loadExecutionArrows(executions) {
        try {
            if (!executions || !Array.isArray(executions)) {
                console.warn('loadExecutionArrows: Invalid executions data provided');
                return;
            }

            console.log(`🎯 Loading ${executions.length} execution arrows into chart`);

            // Use the existing addExecutionArrows method
            this.addExecutionArrows(executions);

            // Store execution times for centering - will be used after chart data loads
            // Parse and store the execution timestamps for later use
            if (executions.length > 0) {
                const executionTimes = executions.map(e => {
                    // Handle different timestamp formats
                    let ts = null;

                    // Try numeric timestamp first
                    if (typeof e.timestamp === 'number' && e.timestamp > 0) {
                        ts = e.timestamp;
                    }
                    // Try parsing string timestamp (format: "2025-12-11 10:25:54")
                    else if (typeof e.timestamp === 'string' && e.timestamp) {
                        // Parse the date string - add 'T' for ISO format if space-separated
                        const dateStr = e.timestamp.includes('T') ? e.timestamp : e.timestamp.replace(' ', 'T');
                        const date = new Date(dateStr);
                        if (!isNaN(date.getTime())) {
                            ts = Math.floor(date.getTime() / 1000);
                        }
                    }
                    // Try execution_time field as fallback
                    else if (e.execution_time) {
                        const date = new Date(e.execution_time);
                        if (!isNaN(date.getTime())) {
                            ts = Math.floor(date.getTime() / 1000);
                        }
                    }

                    console.log(`📍 Execution timestamp: ${ts} (from ${e.timestamp || e.execution_time})`);
                    return ts;
                }).filter(t => t !== null && t > 0);

                console.log(`🎯 Valid execution times found: ${executionTimes.length}`);

                if (executionTimes.length > 0) {
                    // Store for use in centerOnExecutions method
                    this.pendingExecutionCenter = {
                        minTime: Math.min(...executionTimes),
                        maxTime: Math.max(...executionTimes)
                    };
                    console.log(`📌 Stored execution times for centering after data loads`);

                    // Try to center now if chart already has data
                    this.centerOnExecutions();
                }
            }

        } catch (error) {
            console.error('❌ Error loading execution arrows:', error);
        }
    }

    /**
     * Center the chart view on execution times if pending and chart has data
     * Called from both loadExecutionArrows and setData to handle async loading
     *
     * TradingView Lightweight Charts setVisibleRange/setVisibleLogicalRange are ASYNCHRONOUS
     * They use requestAnimationFrame internally and don't apply changes immediately.
     * See: https://github.com/tradingview/lightweight-charts/issues/650
     */
    centerOnExecutions() {
        if (!this.pendingExecutionCenter) {
            return; // No pending center request
        }

        if (!this.chart || !this.chart.timeScale) {
            console.log(`⏳ Chart not ready for centering yet`);
            return;
        }

        if (!this.candlestickSeries) {
            console.log(`⏳ Candlestick series not ready yet`);
            return;
        }

        const timeScale = this.chart.timeScale();

        // Check if chart has data
        const chartData = this.chartData;
        if (!chartData || chartData.length === 0) {
            console.log(`⏳ Chart has no data yet, will center later`);
            return;
        }

        const { minTime, maxTime } = this.pendingExecutionCenter;

        // Validate timestamps
        const minDate = new Date(minTime * 1000);
        const maxDate = new Date(maxTime * 1000);

        if (isNaN(minDate.getTime()) || isNaN(maxDate.getTime())) {
            console.error(`❌ Invalid execution times for centering: ${minTime}, ${maxTime}`);
            this.pendingExecutionCenter = null;
            return;
        }

        console.log(`🎯 Centering on executions: ${minDate.toISOString()} to ${maxDate.toISOString()}`);

        // Calculate the time range we want to show
        // Add padding of ~10 minutes before first execution and after last execution
        const paddingSeconds = 10 * 60; // 10 minutes in seconds
        const viewStartTime = minTime - paddingSeconds;
        const viewEndTime = maxTime + paddingSeconds;

        console.log(`📐 Target time range: ${new Date(viewStartTime * 1000).toISOString()} to ${new Date(viewEndTime * 1000).toISOString()}`);

        // Store execution center info for potential re-centering
        // Don't clear it yet - we'll clear it only after successful centering
        const executionCenterInfo = { minTime, maxTime, viewStartTime, viewEndTime };

        // Store reference for use in callbacks
        const self = this;

        // Use setTimeout to ensure all async operations complete before setting range
        // TradingView Lightweight Charts uses requestAnimationFrame internally,
        // so we need to wait for that plus a little extra time
        // Use a longer delay (500ms) to ensure the chart is fully rendered
        setTimeout(() => {
            try {
                // Calculate bar indices from the data
                const chartData = self.chartData;
                let startBarIndex = -1;
                let endBarIndex = -1;
                let executionCenterIndex = -1;

                for (let i = 0; i < chartData.length; i++) {
                    const barTime = chartData[i].time;
                    if (startBarIndex === -1 && barTime >= viewStartTime) {
                        startBarIndex = Math.max(0, i - 5); // Add some padding
                    }
                    if (barTime <= viewEndTime) {
                        endBarIndex = Math.min(chartData.length - 1, i + 5);
                    }
                    // Find the bar closest to execution center
                    if (executionCenterIndex === -1 && barTime >= minTime) {
                        executionCenterIndex = i;
                    }
                }

                console.log(`🔧 Centering on bars ${startBarIndex} to ${endBarIndex} (execution center at bar ${executionCenterIndex})`);

                // Calculate target barSpacing to fit the desired range
                const chartWidth = self.container.clientWidth - 60; // Account for price scale
                const barsToShow = endBarIndex - startBarIndex + 1;
                const targetBarSpacing = Math.max(8, Math.floor(chartWidth / barsToShow));

                console.log(`📐 Chart width: ${chartWidth}px, bars to show: ${barsToShow}, target barSpacing: ${targetBarSpacing}px`);

                // NEW APPROACH: Use barSpacing + scrollToPosition
                // Step 1: Set the barSpacing to zoom to desired level
                console.log(`🔍 Step 1: Setting barSpacing to ${targetBarSpacing}px`);
                timeScale.applyOptions({
                    barSpacing: targetBarSpacing,
                    rightOffset: 5
                });

                // Step 2: After barSpacing is applied, scroll to center on executions
                // scrollToPosition uses position from the RIGHT edge
                // We want the execution center to be in the middle of the view
                requestAnimationFrame(() => {
                    // Get how many bars are visible at this barSpacing
                    const visibleBars = Math.floor(chartWidth / targetBarSpacing);
                    const halfVisibleBars = Math.floor(visibleBars / 2);

                    // scrollToPosition: negative = scroll left (back in time), position is from right
                    // We want executionCenterIndex to be centered
                    // Total bars = chartData.length, execution is at index executionCenterIndex
                    // Bars from right = total - executionCenterIndex - 1
                    const barsFromRight = chartData.length - executionCenterIndex - 1;
                    // To center, scroll so that execution is halfVisibleBars from center
                    const scrollPosition = barsFromRight - halfVisibleBars;

                    console.log(`🎯 Step 2: Scrolling to position ${scrollPosition} (visibleBars: ${visibleBars}, execution at bar ${executionCenterIndex}, barsFromRight: ${barsFromRight})`);

                    timeScale.scrollToPosition(scrollPosition, false);

                    // Verify after another frame
                    setTimeout(() => {
                        const logicalRange = timeScale.getVisibleLogicalRange();
                        const actualBarSpacing = timeScale.options().barSpacing;

                        if (logicalRange) {
                            const visibleFrom = Math.round(logicalRange.from);
                            const visibleTo = Math.round(logicalRange.to);
                            console.log(`📊 Final view: bars ${visibleFrom} to ${visibleTo}, barSpacing: ${actualBarSpacing}px`);

                            // Check if execution is visible
                            if (visibleFrom <= executionCenterIndex && visibleTo >= executionCenterIndex) {
                                console.log(`✅ Success! Execution (bar ${executionCenterIndex}) is visible in range ${visibleFrom}-${visibleTo}`);
                            } else {
                                console.log(`⚠️ Execution (bar ${executionCenterIndex}) NOT in visible range ${visibleFrom}-${visibleTo}`);

                                // Last resort: try setVisibleLogicalRange
                                console.log(`🔄 Fallback: trying setVisibleLogicalRange`);
                                timeScale.setVisibleLogicalRange({
                                    from: startBarIndex,
                                    to: endBarIndex
                                });
                            }
                        }

                        // Clear after verification
                        self.pendingExecutionCenter = null;
                    }, 300);
                });

            } catch (error) {
                console.error(`❌ Error centering on executions:`, error);
                self.pendingExecutionCenter = null;
            }
        }, 500);
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
