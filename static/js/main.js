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

function submitFilterForm() {
    const form = document.getElementById('filterForm');
    if (form) {
        const selectedAccounts = Array.from(document.querySelectorAll('#accountSelect option:checked'))
            .map(option => option.value);
        
        // Create URLSearchParams object
        const params = new URLSearchParams(window.location.search);
        
        // Clear existing accounts parameters
        params.delete('accounts');
        
        // Add selected accounts
        selectedAccounts.forEach(account => {
            params.append('accounts', account);
        });
        
        // Add other form parameters
        const formData = new FormData(form);
        for (let [key, value] of formData.entries()) {
            if (key !== 'accounts' && value) {
                params.set(key, value);
            }
        }
        
        // Reset to page 1 when applying new filters
        params.set('page', '1');
        
        // Update URL
        window.location.search = params.toString();
    }
}

// Create debounced version of submitFilterForm
const debouncedSubmitFilterForm = debounce(submitFilterForm, 300);

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
}

function updateActionButtons() {
    const selectedCount = document.querySelectorAll('tbody input[type="checkbox"]:checked').length;
    const deleteBtn = document.getElementById('deleteBtn');
    const linkBtn = document.getElementById('linkSelectedBtn');
    const selectedCountSpans = document.querySelectorAll('.selectedCount');
    
    if (selectedCount > 0) {
        deleteBtn.style.display = 'inline-block';
    } else {
        deleteBtn.style.display = 'none';
    }
}
