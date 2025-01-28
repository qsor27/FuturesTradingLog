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
    const currentSort = new URLSearchParams(window.location.search).get('sort_by') || 'entry_time';
    const currentOrder = new URLSearchParams(window.location.search).get('sort_order') || 'DESC';
    
    let newOrder = 'DESC';
    if (column === currentSort && currentOrder === 'DESC') {
        newOrder = 'ASC';
    }
    
    window.location.href = `/?sort_by=${column}&sort_order=${newOrder}`;
}

function toggleRow(checkbox) {
    const row = checkbox.closest('tr');
    row.classList.toggle('selected', checkbox.checked);
    updateDeleteButton();
}

function toggleSelectAll(checkbox) {
    const rows = document.querySelectorAll('tbody input[type="checkbox"]');
    rows.forEach(row => {
        row.checked = checkbox.checked;
        toggleRow(row);
    });
}

function updateDeleteButton() {
    const selectedCount = document.querySelectorAll('tbody input[type="checkbox"]:checked').length;
    const deleteBtn = document.getElementById('deleteBtn');
    const selectedCountSpan = document.getElementById('selectedCount');
    
    deleteBtn.style.display = selectedCount > 0 ? 'inline-block' : 'none';
    selectedCountSpan.textContent = selectedCount;
}

function deleteSelected() {
    if (!confirm('Are you sure you want to delete the selected trades?')) {
        return;
    }
    
    const selectedRows = document.querySelectorAll('tbody input[type="checkbox"]:checked');
    const tradeIds = Array.from(selectedRows).map(checkbox => checkbox.value);
    
    fetch('/delete-trades', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({trade_ids: tradeIds}),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            selectedRows.forEach(checkbox => checkbox.closest('tr').remove());
            updateDeleteButton();
            alert('Trades deleted successfully');
        } else {
            alert('Error deleting trades');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error deleting trades');
    });
}