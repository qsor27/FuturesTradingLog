/**
 * ComponentRegistry - Automatic component initialization system
 * 
 * Provides automatic discovery and initialization of JavaScript components
 * based on data attributes in the DOM.
 */
export class ComponentRegistry {
    static components = new Map();
    static initialized = false;
    static instances = new Map();
    
    /**
     * Register a component class with a CSS selector
     * @param {string} selector - CSS selector to find component elements
     * @param {class} componentClass - Component class constructor
     */
    static register(selector, componentClass) {
        this.components.set(selector, componentClass);
        
        // If already initialized, immediately initialize new components
        if (this.initialized) {
            this.initializeComponents(selector, componentClass);
        }
    }
    
    /**
     * Initialize all registered components
     * Called automatically on DOM ready
     */
    static async initializeAll() {
        if (this.initialized) {
            console.warn('ComponentRegistry: Already initialized');
            return;
        }
        
        console.log('🚀 ComponentRegistry: Initializing all components...');
        
        for (const [selector, componentClass] of this.components) {
            await this.initializeComponents(selector, componentClass);
        }
        
        this.initialized = true;
        console.log(`✅ ComponentRegistry: Initialized ${this.instances.size} component instances`);
    }
    
    /**
     * Initialize components matching a specific selector
     * @param {string} selector - CSS selector
     * @param {class} componentClass - Component class
     */
    static async initializeComponents(selector, componentClass) {
        const elements = document.querySelectorAll(selector);
        
        if (elements.length === 0) {
            console.log(`ComponentRegistry: No elements found for selector: ${selector}`);
            return;
        }
        
        console.log(`🔍 ComponentRegistry: Found ${elements.length} elements for ${componentClass.name}`);
        
        for (const element of elements) {
            await this.initializeComponent(element, componentClass);
        }
    }
    
    /**
     * Initialize a single component instance
     * @param {Element} element - DOM element
     * @param {class} componentClass - Component class
     */
    static async initializeComponent(element, componentClass) {
        // Skip if already initialized
        if (element.dataset.componentInitialized) {
            return;
        }
        
        try {
            console.log(`⚡ ComponentRegistry: Initializing ${componentClass.name}`, element);
            
            const instance = new componentClass(element);
            
            // Store instance reference
            const instanceId = this.generateInstanceId(element, componentClass);
            this.instances.set(instanceId, instance);
            
            // Mark as initialized
            element.dataset.componentInitialized = 'true';
            element.dataset.componentInstanceId = instanceId;
            
            // Call async initialize if it exists
            if (typeof instance.initialize === 'function') {
                await instance.initialize();
            }
            
            console.log(`✅ ComponentRegistry: ${componentClass.name} initialized successfully`);
            
        } catch (error) {
            console.error(`❌ ComponentRegistry: Error initializing ${componentClass.name}:`, error);
            element.dataset.componentError = error.message;
        }
    }
    
    /**
     * Generate unique instance ID for a component
     * @param {Element} element - DOM element
     * @param {class} componentClass - Component class
     * @returns {string} Unique instance ID
     */
    static generateInstanceId(element, componentClass) {
        const elementId = element.id || `element-${Math.random().toString(36).substr(2, 9)}`;
        return `${componentClass.name}-${elementId}`;
    }
    
    /**
     * Get component instance by element or instance ID
     * @param {Element|string} elementOrId - DOM element or instance ID
     * @returns {Object|null} Component instance
     */
    static getInstance(elementOrId) {
        if (typeof elementOrId === 'string') {
            return this.instances.get(elementOrId);
        } else if (elementOrId.dataset?.componentInstanceId) {
            return this.instances.get(elementOrId.dataset.componentInstanceId);
        }
        return null;
    }
    
    /**
     * Destroy a component instance
     * @param {Element|string} elementOrId - DOM element or instance ID
     */
    static destroyInstance(elementOrId) {
        const instance = this.getInstance(elementOrId);
        if (instance) {
            // Call cleanup method if it exists
            if (typeof instance.destroy === 'function') {
                instance.destroy();
            }
            
            // Remove from registry
            const instanceId = typeof elementOrId === 'string' 
                ? elementOrId 
                : elementOrId.dataset.componentInstanceId;
            
            this.instances.delete(instanceId);
            
            // Clean up element data
            if (typeof elementOrId !== 'string') {
                delete elementOrId.dataset.componentInitialized;
                delete elementOrId.dataset.componentInstanceId;
            }
        }
    }
    
    /**
     * Reinitialize components (useful for dynamic content)
     */
    static async reinitialize() {
        console.log('🔄 ComponentRegistry: Reinitializing components...');
        
        for (const [selector, componentClass] of this.components) {
            // Find new elements that haven't been initialized
            const newElements = document.querySelectorAll(
                `${selector}:not([data-component-initialized="true"])`
            );
            
            for (const element of newElements) {
                await this.initializeComponent(element, componentClass);
            }
        }
    }
    
    /**
     * Get debug information about registered components
     * @returns {Object} Debug information
     */
    static getDebugInfo() {
        return {
            totalComponents: this.components.size,
            totalInstances: this.instances.size,
            initialized: this.initialized,
            components: Array.from(this.components.keys()),
            instances: Array.from(this.instances.keys())
        };
    }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        ComponentRegistry.initializeAll();
    });
} else {
    // DOM is already ready
    ComponentRegistry.initializeAll();
}

// Make available globally for debugging
window.ComponentRegistry = ComponentRegistry;