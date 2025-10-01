/**
 * ComponentBase - Base class for all JavaScript components
 * 
 * Provides common functionality like error handling, event management,
 * and lifecycle methods for consistent component development.
 */
import { DataBridge } from './DataBridge.js';

export class ComponentBase {
    constructor(element) {
        this.element = element;
        this.config = null;
        this.eventListeners = [];
        this.isInitialized = false;
        this.isDestroyed = false;
        
        // Load configuration if specified
        this.loadConfiguration();
    }
    
    /**
     * Load component configuration from JSON data
     */
    loadConfiguration() {
        const configId = this.element.dataset.configId;
        if (configId) {
            this.config = DataBridge.getJsonData(configId);
            if (!this.config) {
                this.logError(`No configuration found for configId: ${configId}`);
            }
        }
    }
    
    /**
     * Initialize the component - override in subclasses
     * @returns {Promise<void>}
     */
    async initialize() {
        if (this.isInitialized) {
            this.logWarn('Component already initialized');
            return;
        }
        
        try {
            await this.setup();
            this.isInitialized = true;
            this.log('Component initialized successfully');
        } catch (error) {
            this.logError('Component initialization failed:', error);
            throw error;
        }
    }
    
    /**
     * Setup method - override in subclasses for initialization logic
     * @returns {Promise<void>}
     */
    async setup() {
        // Override in subclasses
    }
    
    /**
     * Safe execution wrapper with error handling
     * @param {Function} operation - Operation to execute
     * @param {string} errorMessage - Error message prefix
     * @returns {Promise<*>} Operation result or null on error
     */
    async safeExecute(operation, errorMessage) {
        try {
            return await operation();
        } catch (error) {
            this.logError(errorMessage, error);
            this.showError(`${errorMessage}: ${error.message}`);
            return null;
        }
    }
    
    /**
     * Add event listener with automatic cleanup tracking
     * @param {Element} target - Target element
     * @param {string} event - Event name
     * @param {Function} handler - Event handler
     * @param {Object} options - Event listener options
     */
    addEventListener(target, event, handler, options = {}) {
        target.addEventListener(event, handler, options);
        
        // Track for automatic cleanup
        this.eventListeners.push({
            target,
            event,
            handler,
            options
        });
    }
    
    /**
     * Remove all tracked event listeners
     */
    removeAllEventListeners() {
        this.eventListeners.forEach(({ target, event, handler, options }) => {
            target.removeEventListener(event, handler, options);
        });
        this.eventListeners = [];
    }
    
    /**
     * Show error message to user
     * @param {string} message - Error message
     */
    showError(message) {
        this.showNotification(message, 'error');
    }
    
    /**
     * Show success message to user
     * @param {string} message - Success message
     */
    showSuccess(message) {
        this.showNotification(message, 'success');
    }
    
    /**
     * Show notification to user
     * @param {string} message - Message text
     * @param {string} type - Notification type (error, success, warning, info)
     */
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-message">${message}</span>
                <button class="notification-close" aria-label="Close notification">×</button>
            </div>
        `;
        
        // Add styles if not already present
        this.ensureNotificationStyles();
        
        // Add to DOM
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        const autoRemove = setTimeout(() => {
            this.removeNotification(notification);
        }, 5000);
        
        // Manual close handler
        notification.querySelector('.notification-close').addEventListener('click', () => {
            clearTimeout(autoRemove);
            this.removeNotification(notification);
        });
    }
    
    /**
     * Remove notification from DOM
     * @param {Element} notification - Notification element
     */
    removeNotification(notification) {
        if (notification.parentNode) {
            notification.style.opacity = '0';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    }
    
    /**
     * Ensure notification styles are loaded
     */
    ensureNotificationStyles() {
        if (document.getElementById('component-notification-styles')) {
            return;
        }
        
        const styles = document.createElement('style');
        styles.id = 'component-notification-styles';
        styles.textContent = `
            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                max-width: 400px;
                padding: 16px;
                border-radius: 6px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                z-index: 10000;
                opacity: 1;
                transition: opacity 0.3s ease;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            
            .notification-error {
                background: #fee;
                border-left: 4px solid #f87171;
                color: #7f1d1d;
            }
            
            .notification-success {
                background: #f0fdf4;
                border-left: 4px solid #4ade80;
                color: #14532d;
            }
            
            .notification-warning {
                background: #fffbeb;
                border-left: 4px solid #fbbf24;
                color: #92400e;
            }
            
            .notification-info {
                background: #eff6ff;
                border-left: 4px solid #3b82f6;
                color: #1e40af;
            }
            
            .notification-content {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
            }
            
            .notification-message {
                flex: 1;
                margin-right: 12px;
            }
            
            .notification-close {
                background: none;
                border: none;
                font-size: 18px;
                cursor: pointer;
                padding: 0;
                line-height: 1;
                opacity: 0.7;
            }
            
            .notification-close:hover {
                opacity: 1;
            }
        `;
        
        document.head.appendChild(styles);
    }
    
    /**
     * Logging methods with component context
     */
    log(...args) {
        console.log(`[${this.constructor.name}]`, ...args);
    }
    
    logWarn(...args) {
        console.warn(`[${this.constructor.name}]`, ...args);
    }
    
    logError(...args) {
        console.error(`[${this.constructor.name}]`, ...args);
    }
    
    /**
     * Destroy the component and clean up resources
     */
    destroy() {
        if (this.isDestroyed) {
            return;
        }
        
        this.removeAllEventListeners();
        this.cleanup();
        this.isDestroyed = true;
        this.log('Component destroyed');
    }
    
    /**
     * Cleanup method - override in subclasses for custom cleanup
     */
    cleanup() {
        // Override in subclasses
    }
    
    /**
     * Check if component is ready for use
     * @returns {boolean}
     */
    isReady() {
        return this.isInitialized && !this.isDestroyed;
    }
    
    /**
     * Get component configuration value
     * @param {string} key - Configuration key
     * @param {*} defaultValue - Default value if key not found
     * @returns {*} Configuration value
     */
    getConfig(key, defaultValue = null) {
        return this.config?.[key] ?? defaultValue;
    }
    
    /**
     * Update component configuration
     * @param {Object} newConfig - New configuration values
     */
    updateConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
    }
}