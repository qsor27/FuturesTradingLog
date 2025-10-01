/**
 * DataBridge - Core system for safe data transfer between Flask/Jinja2 and JavaScript
 * 
 * Eliminates template literal conflicts by providing clean JSON data injection
 * and modern API communication patterns.
 */
export class DataBridge {
    /**
     * Safely extract JSON data from script tags injected by templates
     * @param {string} elementId - ID of the script tag containing JSON data
     * @returns {Object|null} Parsed JSON data or null if not found/invalid
     */
    static getJsonData(elementId) {
        const element = document.getElementById(elementId);
        if (!element) {
            console.warn(`DataBridge: No element found with ID: ${elementId}`);
            return null;
        }
        
        try {
            const jsonText = element.textContent.trim();
            if (!jsonText) {
                console.warn(`DataBridge: Empty JSON data in element: ${elementId}`);
                return null;
            }
            
            return JSON.parse(jsonText);
        } catch (error) {
            console.error(`DataBridge: Error parsing JSON data from ${elementId}:`, error);
            console.error('Raw content:', element.textContent);
            return null;
        }
    }
    
    /**
     * Modern fetch wrapper with error handling and automatic JSON parsing
     * @param {string} endpoint - API endpoint URL
     * @param {Object} options - Fetch options (method, body, etc.)
     * @returns {Promise<Object>} Response data
     */
    static async fetchData(endpoint, options = {}) {
        const url = new URL(endpoint, window.location.origin);
        
        // Add query parameters if provided
        if (options.params) {
            Object.entries(options.params).forEach(([key, value]) => {
                if (value !== null && value !== undefined) {
                    url.searchParams.append(key, value);
                }
            });
        }
        
        const fetchOptions = {
            method: options.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };
        
        // Remove params from fetchOptions to avoid conflicts
        delete fetchOptions.params;
        
        try {
            const response = await fetch(url, fetchOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Check if response is JSON
            const contentType = response.headers.get('Content-Type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            } else {
                return await response.text();
            }
            
        } catch (error) {
            console.error(`DataBridge: Error fetching data from ${endpoint}:`, error);
            throw error;
        }
    }
    
    /**
     * Global data storage for cross-component communication
     * @param {string} key - Data key
     * @param {*} data - Data to store
     */
    static setGlobalData(key, data) {
        if (!window.appData) {
            window.appData = {};
        }
        window.appData[key] = data;
    }
    
    /**
     * Retrieve global data
     * @param {string} key - Data key
     * @returns {*} Stored data or undefined
     */
    static getGlobalData(key) {
        return window.appData?.[key];
    }
    
    /**
     * Safely inject template data into DOM elements
     * Useful for dynamically updating element attributes with server data
     * @param {string} sourceElementId - ID of JSON script tag
     * @param {string} targetElementId - ID of target element
     */
    static injectTemplateData(sourceElementId, targetElementId) {
        const data = this.getJsonData(sourceElementId);
        const target = document.getElementById(targetElementId);
        
        if (data && target) {
            Object.entries(data).forEach(([key, value]) => {
                target.dataset[key] = value;
            });
        }
    }
    
    /**
     * Format data for safe template injection
     * Handles dates, numbers, and complex objects
     * @param {*} data - Data to format
     * @returns {string} JSON string safe for template injection
     */
    static formatForTemplate(data) {
        return JSON.stringify(data, (key, value) => {
            // Handle Date objects
            if (value instanceof Date) {
                return value.toISOString();
            }
            // Handle undefined values
            if (value === undefined) {
                return null;
            }
            return value;
        });
    }
    
    /**
     * Debounce function for performance optimization
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Make available globally for debugging
window.DataBridge = DataBridge;