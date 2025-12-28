/**
 * Enhanced Statistics JavaScript
 * Handles chart toggle functionality and Chart.js integration for stat cards
 */

// Store chart instances to allow destruction before recreation
const statCharts = {};

/**
 * Toggle chart visibility for a stat card
 * @param {string} cardId - Unique card identifier
 * @param {string} chartType - Type of chart (pie, bar, line)
 * @param {string} endpoint - API endpoint for chart data
 * @param {string} params - Query parameters for the API
 */
function toggleStatChart(cardId, chartType, endpoint, params) {
    const container = document.getElementById(`${cardId}-chart-container`);
    const button = container.parentElement.querySelector('.chart-toggle-btn');

    if (container.style.display === 'none' || container.style.display === '') {
        // Show chart
        container.style.display = 'block';
        button.classList.add('active');

        // Load chart data if not already loaded
        if (!statCharts[cardId]) {
            loadStatChart(cardId, chartType, endpoint, params);
        }
    } else {
        // Hide chart
        container.style.display = 'none';
        button.classList.remove('active');
    }
}

/**
 * Load chart data from API and render
 * @param {string} cardId - Unique card identifier
 * @param {string} chartType - Type of chart (pie, bar, line)
 * @param {string} endpoint - API endpoint for chart data
 * @param {string} params - Query parameters for the API
 */
async function loadStatChart(cardId, chartType, endpoint, params) {
    const loadingEl = document.getElementById(`${cardId}-loading`);
    const canvasEl = document.getElementById(`${cardId}-chart`);

    try {
        loadingEl.style.display = 'block';

        // Build full URL
        let url = endpoint;
        if (params) {
            url += (endpoint.includes('?') ? '&' : '?') + params;
        }

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const chartData = await response.json();

        // Destroy existing chart if any
        if (statCharts[cardId]) {
            statCharts[cardId].destroy();
        }

        // Create new chart
        const ctx = canvasEl.getContext('2d');
        statCharts[cardId] = createChart(ctx, chartType, chartData);

        loadingEl.style.display = 'none';

    } catch (error) {
        console.error(`Error loading chart for ${cardId}:`, error);
        loadingEl.textContent = 'Error loading chart';
        loadingEl.classList.add('error');
    }
}

/**
 * Create a Chart.js chart with the given configuration
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {string} chartType - Type of chart (pie, bar, line)
 * @param {Object} chartData - Chart.js compatible data object
 * @returns {Chart} Chart.js instance
 */
function createChart(ctx, chartType, chartData) {
    const config = {
        type: chartType,
        data: chartData,
        options: getChartOptions(chartType, chartData)
    };

    return new Chart(ctx, config);
}

/**
 * Get chart options based on chart type
 * @param {string} chartType - Type of chart
 * @param {Object} chartData - Chart data (to determine if dual axes needed)
 * @returns {Object} Chart.js options object
 */
function getChartOptions(chartType, chartData) {
    const baseOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true,
                position: 'bottom',
                labels: {
                    color: '#e5e5e5',
                    font: {
                        size: 11
                    },
                    padding: 8
                }
            },
            tooltip: {
                backgroundColor: 'rgba(42, 42, 42, 0.95)',
                titleColor: '#e5e5e5',
                bodyColor: '#e5e5e5',
                borderColor: '#404040',
                borderWidth: 1,
                cornerRadius: 4,
                padding: 8
            }
        }
    };

    if (chartType === 'pie' || chartType === 'doughnut') {
        return {
            ...baseOptions,
            cutout: chartType === 'doughnut' ? '50%' : 0
        };
    }

    if (chartType === 'bar' || chartType === 'line') {
        // Check if we have dual Y axes
        const hasDualAxes = chartData.datasets?.some(ds => ds.yAxisID === 'y1');

        const options = {
            ...baseOptions,
            scales: {
                x: {
                    grid: {
                        color: 'rgba(64, 64, 64, 0.5)'
                    },
                    ticks: {
                        color: '#e5e5e5'
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(64, 64, 64, 0.5)'
                    },
                    ticks: {
                        color: '#e5e5e5'
                    },
                    title: {
                        display: true,
                        text: 'P&L ($)',
                        color: '#e5e5e5'
                    }
                }
            }
        };

        if (hasDualAxes) {
            options.scales.y1 = {
                type: 'linear',
                display: true,
                position: 'right',
                grid: {
                    drawOnChartArea: false
                },
                ticks: {
                    color: '#e5e5e5'
                },
                title: {
                    display: true,
                    text: 'Win Rate (%)',
                    color: '#e5e5e5'
                }
            };
        }

        return options;
    }

    return baseOptions;
}

/**
 * Refresh all visible charts (useful after data updates)
 */
function refreshVisibleCharts() {
    Object.keys(statCharts).forEach(cardId => {
        const container = document.getElementById(`${cardId}-chart-container`);
        if (container && container.style.display !== 'none') {
            const button = container.parentElement.querySelector('.chart-toggle-btn');
            const chartType = button?.dataset?.chartType || 'bar';
            const endpoint = button?.dataset?.endpoint || '';
            const params = button?.dataset?.params || '';

            loadStatChart(cardId, chartType, endpoint, params);
        }
    });
}

/**
 * Format currency value
 * @param {number} value - Value to format
 * @returns {string} Formatted currency string
 */
function formatCurrency(value) {
    const formatter = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
    return formatter.format(value);
}

/**
 * Format percentage value
 * @param {number} value - Value to format
 * @returns {string} Formatted percentage string
 */
function formatPercent(value) {
    return `${value.toFixed(1)}%`;
}

/**
 * Get trend class based on value
 * @param {number} value - Value to check
 * @returns {string} CSS class name
 */
function getTrendClass(value) {
    if (value > 0) return 'positive';
    if (value < 0) return 'negative';
    return 'neutral';
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        toggleStatChart,
        loadStatChart,
        refreshVisibleCharts,
        formatCurrency,
        formatPercent,
        getTrendClass
    };
}
