function updatePageSize(select) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page_size', select.value);
    urlParams.set('page', '1');
    window.location.search = urlParams.toString();
}

function goToPage(page) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    window.location.search = urlParams.toString();
}

function updateSort(column) {
    const urlParams = new URLSearchParams(window.location.search);
    const currentSort = urlParams.get('sort_by') || 'entry_time';
    const currentOrder = urlParams.get('sort_order') || 'DESC';
    
    let newOrder = 'DESC';
    if (column === currentSort && currentOrder === 'DESC') {
        newOrder = 'ASC';
    }
    
    urlParams.set('sort_by', column);
    urlParams.set('sort_order', newOrder);
    
    window.location.search = urlParams.toString();
}

function submitFilterForm() {
    console.log('🔍 Submitting filter form...');
    const form = document.getElementById('filterForm');
    if (form) {
        const selectedAccounts = Array.from(document.querySelectorAll('#accountSelect option:checked'))
            .map(option => option.value);
        
        console.log('📋 Selected accounts:', selectedAccounts);
        
        // Create URLSearchParams object
        const params = new URLSearchParams();
        
        // Add selected accounts
        if (selectedAccounts.length > 0) {
            selectedAccounts.forEach(account => {
                params.append('accounts', account);
            });
        }
        
        // Add other form parameters, excluding empty values
        const formData = new FormData(form);
        for (let [key, value] of formData.entries()) {
            if (key !== 'accounts' && value.trim() !== '') {
                params.set(key, value);
            }
        }
        
        // Preserve sorting parameters
        const currentParams = new URLSearchParams(window.location.search);
        ['sort_by', 'sort_order', 'page_size'].forEach(param => {
            if (currentParams.has(param)) {
                params.set(param, currentParams.get(param));
            }
        });
        
        // Reset to page 1 when applying filters
        params.set('page', '1');
        
        // Update URL
        console.log('🔄 Applying filters with parameters:', params.toString());
        window.location.search = params.toString();
    } else {
        console.warn('⚠️ Filter form not found');
    }
}

// Create debounced version of submitFilterForm
const debouncedSubmitFilterForm = debounce(submitFilterForm, 300);

// Debounce function to prevent too many rapid filter submissions
function debounce(func, wait) {
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

// Add event listener when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const filterForm = document.getElementById('filterForm');
    if (filterForm) {
        filterForm.addEventListener('submit', function(e) {
            e.preventDefault();
        });
    }
});

function toggleRow(checkbox) {
    const row = checkbox.closest('tr');
    row.classList.toggle('selected', checkbox.checked);
    updateActionButtons();
}

function toggleSelectAll(checkbox) {
    const rows = document.querySelectorAll('tbody input[type="checkbox"]');
    rows.forEach(row => {
        row.checked = checkbox.checked;
        toggleRow(row);
    });
    updateActionButtons();
}

function updateActionButtons() {
    const selectedCount = document.querySelectorAll('tbody input[type="checkbox"]:checked').length;
    const actionButtons = document.getElementById('actionButtons');
    if (actionButtons) {
        actionButtons.style.display = selectedCount > 0 ? 'block' : 'none';
    }
}

function deleteTrades() {
    const selectedRows = document.querySelectorAll('tbody input[type="checkbox"]:checked');
    const tradeIds = Array.from(selectedRows).map(checkbox => checkbox.value);
    
    console.log(`🗑️ Attempting to delete ${tradeIds.length} trades:`, tradeIds);
    
    if (confirm(`Are you sure you want to delete ${tradeIds.length} trade(s)?`)) {
        console.log('✅ User confirmed deletion, sending request...');
        fetch('/delete-trades', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ trade_ids: tradeIds }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`✅ Successfully deleted ${tradeIds.length} trades`);
                window.location.reload();
            } else {
                console.error('❌ Failed to delete trades:', data);
                alert('Failed to delete trades: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('❌ Error deleting trades:', error);
            alert('Failed to delete trades: ' + error);
        });
    }
}