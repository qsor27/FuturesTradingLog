/**
 * ChartComponentManager - Modern chart component using JSON Data Bridge
 * 
 * Replaces inline JavaScript in templates with clean external module.
 * Eliminates template literal conflicts and enables modern JavaScript features.
 */
import { ComponentBase } from '../core/ComponentBase.js';
import { DataBridge } from '../core/DataBridge.js';
import { ComponentRegistry } from '../core/ComponentRegistry.js';

export class ChartComponentManager extends ComponentBase {
    constructor(element) {
        super(element);
        
        this.chart = null;
        this.chartInstance = null;
        this.timeframeSelect = null;
        this.daysSelect = null;
        this.volumeToggle = null;
        this.chartId = element.id || `chart-${Math.random().toString(36).substr(2, 9)}`;
        
        // Ensure element has an ID for chart library
        if (!element.id) {
            element.id = this.chartId;
        }
    }
    
    async setup() {
        if (!this.config) {
            throw new Error('Chart configuration is required');
        }
        
        this.log('Initializing chart with config:', this.config);
        
        // Wait for TradingView library to be available
        await this.waitForTradingViewLibrary();
        
        // Initialize chart
        await this.initializeChart();
        
        // Setup controls
        this.setupControls();
        
        // Load trade markers if specified
        if (this.config.tradeId) {
            await this.loadTradeMarkers();
        }
        
        // Store instance globally for external access
        this.storeGlobalReference();
    }
    
    async waitForTradingViewLibrary(maxWait = 10000) {
        const startTime = Date.now();
        
        while (!window.LightweightCharts && (Date.now() - startTime) < maxWait) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        if (!window.LightweightCharts) {
            throw new Error('TradingView Lightweight Charts library not available');
        }
        
        this.log(`📦 LightweightCharts available: ${typeof window.LightweightCharts}`);
    }
    
    async initializeChart() {
        try {
            // Use globally available PriceChart class (loaded via script tag)
            if (!window.PriceChart) {
                throw new Error('PriceChart class not available. Ensure PriceChart.js is loaded.');
            }
            
            // Create chart options from configuration
            const chartOptions = {
                instrument: this.config.instrument,
                timeframe: this.config.timeframe || '1h',
                days: this.config.days || 7,
                height: this.config.height || 400,
                showVolume: this.config.showVolume !== false,
                ...this.config.chartOptions
            };
            
            this.log(`🔍 Loading chart data for ${chartOptions.instrument}, timeframe: ${chartOptions.timeframe}, days: ${chartOptions.days}`);
            
            // Initialize PriceChart
            this.chartInstance = new window.PriceChart(this.element.id, chartOptions);
            
            // Store reference in element for external access
            this.element.chartInstance = this.chartInstance;
            
            this.showSuccess(`Chart loaded successfully for ${this.config.instrument}`);
            
        } catch (error) {
            this.logError('Chart initialization failed:', error);
            this.showError(`Chart initialization failed: ${error.message}`);
            throw error;
        }
    }
    
    setupControls() {
        // Find controls associated with this chart
        this.findAndSetupTimeframeControl();
        this.findAndSetupDaysControl();
        this.findAndSetupVolumeToggle();
        
        // Update timeframe availability
        this.updateTimeframeAvailability();
    }
    
    findAndSetupTimeframeControl() {
        // Look for timeframe select with data-chart-id matching our chart
        const chartIdAttr = this.config.chartId || this.chartId;
        let selector = `[data-chart-id="${chartIdAttr}"] .timeframe-select`;
        
        this.timeframeSelect = document.querySelector(selector);
        
        // Fallback: look for timeframe select near our chart element
        if (!this.timeframeSelect) {
            const container = this.element.closest('.chart-container') || this.element.parentElement;
            this.timeframeSelect = container?.querySelector('.timeframe-select');
        }
        
        if (this.timeframeSelect) {
            this.addEventListener(this.timeframeSelect, 'change', (e) => {
                this.handleTimeframeChange(e.target.value);
            });
            this.log('✅ Timeframe control connected');
        } else {
            this.log('⚠️ No timeframe control found');
        }
    }
    
    findAndSetupDaysControl() {
        const chartIdAttr = this.config.chartId || this.chartId;
        let selector = `[data-chart-id="${chartIdAttr}"] .days-select`;
        
        this.daysSelect = document.querySelector(selector);
        
        if (!this.daysSelect) {
            const container = this.element.closest('.chart-container') || this.element.parentElement;
            this.daysSelect = container?.querySelector('.days-select');
        }
        
        if (this.daysSelect) {
            this.addEventListener(this.daysSelect, 'change', (e) => {
                this.handleDaysChange(parseInt(e.target.value));
            });
            this.log('✅ Days control connected');
        }
    }
    
    findAndSetupVolumeToggle() {
        // Volume toggle is typically in the same form or container
        const container = this.element.closest('.chart-container') || 
                         this.element.closest('form') || 
                         this.element.parentElement;
        
        this.volumeToggle = container?.querySelector('input[type="checkbox"][name*="volume"], input[type="checkbox"][id*="volume"]');
        
        if (this.volumeToggle) {
            this.addEventListener(this.volumeToggle, 'change', (e) => {
                this.handleVolumeToggle(e.target.checked);
            });
            this.log('✅ Volume toggle connected');
        }
    }
    
    async handleTimeframeChange(newTimeframe) {
        this.log(`🔄 Timeframe changed to: ${newTimeframe}`);
        
        if (this.chartInstance && typeof this.chartInstance.updateTimeframe === 'function') {
            await this.safeExecute(
                () => this.chartInstance.updateTimeframe(newTimeframe),
                'Failed to update chart timeframe'
            );
        }
    }
    
    async handleDaysChange(newDays) {
        this.log(`🔄 Days changed to: ${newDays}`);
        
        if (this.chartInstance && typeof this.chartInstance.updateDays === 'function') {
            await this.safeExecute(
                () => this.chartInstance.updateDays(newDays),
                'Failed to update chart days'
            );
        }
    }
    
    handleVolumeToggle(showVolume) {
        this.log(`📊 Volume toggle changed to: ${showVolume}`);
        
        if (this.chartInstance && typeof this.chartInstance.toggleVolume === 'function') {
            this.chartInstance.toggleVolume(showVolume);
        }
    }
    
    async updateTimeframeAvailability() {
        if (!this.timeframeSelect || !this.config.instrument) {
            return;
        }
        
        try {
            const data = await DataBridge.fetchData(`/api/available-timeframes/${encodeURIComponent(this.config.instrument)}`);
            
            if (data.success && data.available_timeframes) {
                this.log('📊 Available timeframes for ' + this.config.instrument + ':', data.available_timeframes);
                
                // Update timeframe options
                Array.from(this.timeframeSelect.options).forEach(option => {
                    const tf = option.value;
                    const count = data.available_timeframes[tf];
                    
                    if (count > 0) {
                        option.disabled = false;
                        option.textContent = `${tf} (${count} records)`;
                        option.style.color = '';
                    } else {
                        option.disabled = true;
                        option.textContent = `${tf} (no data)`;
                        option.style.color = '#999';
                    }
                });
                
                // Switch to best available timeframe if current is not available
                if (data.best_timeframe && !data.available_timeframes[this.timeframeSelect.value]) {
                    this.timeframeSelect.value = data.best_timeframe;
                    this.log('🔄 Switched to best available timeframe: ' + data.best_timeframe);
                    await this.handleTimeframeChange(data.best_timeframe);
                }
            }
        } catch (error) {
            this.logError('Error updating timeframe availability:', error);
        }
    }
    
    async loadTradeMarkers() {
        if (!this.config.tradeId || !this.chartInstance) {
            return;
        }
        
        try {
            this.log(`🎯 Loading trade markers for trade ID: ${this.config.tradeId}`);
            
            if (typeof this.chartInstance.loadTradeMarkers === 'function') {
                await this.chartInstance.loadTradeMarkers(this.config.tradeId);
            }
        } catch (error) {
            this.logError('Error loading trade markers:', error);
        }
    }
    
    storeGlobalReference() {
        // Store in global chart instances array for external access
        if (!window.chartInstances) {
            window.chartInstances = [];
        }
        
        // Add to global instances
        window.chartInstances.push({
            container: this.element,
            instance: this.chartInstance,
            manager: this,
            id: this.chartId
        });
        
        this.log(`📋 Chart instance stored globally with ID: ${this.chartId}`);
    }
    
    // Public API methods for external access
    
    async updateChart(options) {
        if (this.chartInstance) {
            await this.safeExecute(
                () => {
                    if (options.timeframe) this.chartInstance.updateTimeframe(options.timeframe);
                    if (options.days) this.chartInstance.updateDays(options.days);
                    if (options.showVolume !== undefined) this.chartInstance.toggleVolume(options.showVolume);
                },
                'Failed to update chart'
            );
        }
    }
    
    async refresh() {
        if (this.chartInstance && typeof this.chartInstance.refresh === 'function') {
            await this.safeExecute(
                () => this.chartInstance.refresh(),
                'Failed to refresh chart'
            );
        }
    }
    
    getChartData() {
        if (this.chartInstance && typeof this.chartInstance.getData === 'function') {
            return this.chartInstance.getData();
        }
        return null;
    }
    
    cleanup() {
        // Remove from global instances
        if (window.chartInstances) {
            window.chartInstances = window.chartInstances.filter(
                instance => instance.container !== this.element
            );
        }
        
        // Cleanup chart instance
        if (this.chartInstance && typeof this.chartInstance.destroy === 'function') {
            this.chartInstance.destroy();
        }
        
        // Clear references
        this.chartInstance = null;
        this.timeframeSelect = null;
        this.daysSelect = null;
        this.volumeToggle = null;
    }
}

// Register the component for automatic initialization
ComponentRegistry.register('[data-component="price-chart"]', ChartComponentManager);