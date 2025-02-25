// NinjaTrader API Integration

class NinjaTraderAPI {
    constructor() {
        this.statusElement = document.getElementById('nt-status');
        // Wrap initialization in try-catch to handle any initialization errors
        try {
            this.initialize();
        } catch (error) {
            console.warn('Error initializing NinjaTrader API:', error);
            this.updateStatus('Error initializing NinjaTrader connection', 'error');
        }
    }

    initialize() {
        this.checkStatus();
        // Check status every 30 seconds
        setInterval(() => {
            try {
                this.checkStatus();
            } catch (error) {
                console.warn('Error checking NinjaTrader status:', error);
            }
        }, 30000);
    }

    async checkStatus() {
        if (!this.statusElement) {
            console.warn('Status element not found');
            return false;
        }

        try {
            const response = await fetch('/api/ninja-trader/status');
            const data = await response.json();
            
            this.updateStatus(
                data.available ? data.message : 'NinjaTrader integration unavailable',
                this.getStatusClass(data)
            );
            
            if (data.error) {
                this.statusElement.title = data.error;
            }
            
            return data.connected;
        } catch (error) {
            console.warn('Error checking NinjaTrader status:', error);
            this.updateStatus('Error connecting to NinjaTrader', 'error');
            return false;
        }
    }

    updateStatus(message, statusClass) {
        if (this.statusElement) {
            this.statusElement.textContent = message;
            this.statusElement.className = `nt-status status-${statusClass}`;
        }
    }

    getStatusClass(data) {
        if (!data.available) return 'unavailable';
        if (data.connected) return 'connected';
        return 'disconnected';
    }

    async getRecentTrades(days = 7, account = null) {
        try {
            const params = new URLSearchParams({
                days: days.toString()
            });
            if (account) {
                params.append('account', account);
            }

            const response = await fetch(`/api/ninja-trader/trades?${params}`);
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Unknown error fetching trades');
            }
            
            return data.trades;
        } catch (error) {
            console.warn('Error getting recent trades:', error);
            throw error;
        }
    }

    async getMarketData(instrument, timeframe = '1 Day', days = 30) {
        try {
            const params = new URLSearchParams({
                instrument,
                timeframe,
                days: days.toString()
            });

            const response = await fetch(`/api/ninja-trader/market-data?${params}`);
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Unknown error fetching market data');
            }
            
            return data.data;
        } catch (error) {
            console.warn('Error getting market data:', error);
            throw error;
        }
    }
}

// Initialize NinjaTrader API integration when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    try {
        window.ntAPI = new NinjaTraderAPI();
    } catch (error) {
        console.warn('Error creating NinjaTrader API instance:', error);
    }
});