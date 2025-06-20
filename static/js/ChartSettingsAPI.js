/**
 * ChartSettingsAPI.js - Client for managing chart settings with hybrid storage
 * Uses localStorage for performance and API for persistence
 */

class ChartSettingsAPI {
    constructor() {
        this.cacheKey = 'chartSettings';
        this.apiEndpoint = '/api/v1/settings/chart';
        this.defaultSettings = {
            default_timeframe: '1h',
            default_data_range: '1week',
            volume_visibility: true
        };
    }

    /**
     * Get chart settings with fallback hierarchy
     * 1. localStorage cache (fastest)
     * 2. API request (fallback)
     * 3. System defaults (last resort)
     */
    async getSettings() {
        try {
            const startTime = performance.now();
            
            // Check localStorage first for immediate response
            const cached = localStorage.getItem(this.cacheKey);
            if (cached) {
                const loadTime = performance.now() - startTime;
                console.log(`📋 Using cached chart settings (${loadTime.toFixed(2)}ms)`);
                return JSON.parse(cached);
            }

            // Fallback to API request
            console.log('🌐 Fetching chart settings from API...');
            const response = await fetch(this.apiEndpoint);
            
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.settings) {
                    // Cache the settings for next time
                    localStorage.setItem(this.cacheKey, JSON.stringify(data.settings));
                    const loadTime = performance.now() - startTime;
                    console.log(`✅ Chart settings loaded from API and cached (${loadTime.toFixed(2)}ms)`);
                    return data.settings;
                }
            }

            // API failed, use defaults
            console.warn('⚠️ API failed, using default chart settings');
            return this.defaultSettings;

        } catch (error) {
            console.error('❌ Error getting chart settings:', error);
            return this.defaultSettings;
        }
    }

    /**
     * Update chart settings with optimistic caching
     */
    async updateSettings(newSettings) {
        try {
            console.log('💾 Updating chart settings:', newSettings);
            
            const response = await fetch(this.apiEndpoint, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(newSettings)
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    // Update cache immediately
                    localStorage.setItem(this.cacheKey, JSON.stringify(data.settings));
                    
                    // Dispatch global event for other components
                    const event = new CustomEvent('chartSettingsUpdated', {
                        detail: { settings: data.settings }
                    });
                    document.dispatchEvent(event);
                    
                    console.log('✅ Chart settings updated successfully');
                    return { success: true, settings: data.settings };
                }
            }

            const errorData = await response.json();
            console.error('❌ Failed to update chart settings:', errorData.error);
            return { success: false, error: errorData.error };

        } catch (error) {
            console.error('❌ Error updating chart settings:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Clear cached settings (forces reload from API)
     */
    clearCache() {
        localStorage.removeItem(this.cacheKey);
        console.log('🗑️ Chart settings cache cleared');
    }

    /**
     * Get specific setting with fallback to defaults
     */
    async getSetting(key) {
        const settings = await this.getSettings();
        return settings[key] !== undefined ? settings[key] : this.defaultSettings[key];
    }

    /**
     * Convert data range to days for API calls
     */
    convertDataRangeToDays(dataRange) {
        const rangeToDays = {
            '1day': 1,
            '3days': 3,
            '1week': 7,
            '2weeks': 14,
            '1month': 30,
            '3months': 90,
            '6months': 180
        };
        return rangeToDays[dataRange] || 7; // Default to 1 week
    }

    /**
     * Validate timeframe and data range combination for performance
     */
    isValidCombination(timeframe, dataRange) {
        const MAX_CANDLES = 100000; // Performance threshold
        
        const timeframeMinutes = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, 
            '1h': 60, '4h': 240, '1d': 1440
        };
        
        const rangeDays = this.convertDataRangeToDays(dataRange);
        const rangeMinutes = rangeDays * 24 * 60;
        
        const estimatedCandles = rangeMinutes / (timeframeMinutes[timeframe] || 60);
        return estimatedCandles <= MAX_CANDLES;
    }

    /**
     * Get optimal timeframe for given data range (performance optimization)
     */
    getOptimalTimeframe(dataRange) {
        const rangeDays = this.convertDataRangeToDays(dataRange);
        
        if (rangeDays <= 3) return '1m';      // ≤ 3 days: 1-minute
        if (rangeDays <= 14) return '5m';     // ≤ 2 weeks: 5-minute  
        if (rangeDays <= 30) return '15m';    // ≤ 1 month: 15-minute
        if (rangeDays <= 90) return '1h';     // ≤ 3 months: 1-hour
        return '4h';                          // > 3 months: 4-hour
    }
}

// Global instance for use across the application
window.chartSettingsAPI = new ChartSettingsAPI();

// Auto-initialize localStorage cache on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎯 ChartSettingsAPI initialized');
    
    // Pre-warm cache for faster chart loading
    window.chartSettingsAPI.getSettings().then(settings => {
        console.log('📋 Chart settings pre-warmed:', settings);
    });
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ChartSettingsAPI };
}