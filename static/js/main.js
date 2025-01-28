function updatePageSize(select) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page_size', select.value);
    urlParams.set('page', '1');
    window.location.search = urlParams.toString();
}

function goToPage(page) {
    const urlParams = new URLSearchParams(window.location.search);
    
    // Get all selected accounts
    const selectedAccounts = Array.from(document.querySelectorAll('.account-select select option:checked'))
        .map(option => option.value);
    
    // Remove existing account parameter and add all selected accounts
    urlParams.delete('accounts');
    selectedAccounts.forEach(account => {
        urlParams.append('accounts', account);
    });
    
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