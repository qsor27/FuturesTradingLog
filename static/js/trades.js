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
    const linkBtn = document.getElementById('linkBtn');
    const selectedCountSpans = document.querySelectorAll('.selectedCount');
    
    deleteBtn.style.display = selectedCount > 0 ? 'inline-block' : 'none';
    linkBtn.style.display = selectedCount >= 2 ? 'inline-block' : 'none';
    selectedCountSpans.forEach(span => span.textContent = selectedCount);
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
            updateActionButtons();
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

function linkSelectedTrades() {
    const selectedRows = document.querySelectorAll('tbody input[type="checkbox"]:checked');
    const tradeIds = Array.from(selectedRows).map(checkbox => checkbox.value);
    
    if (tradeIds.length < 2) {
        alert('Please select at least two trades to link');
        return;
    }

    const notes = prompt('Enter any notes for this trade group (optional):');
    const chartUrl = prompt('Enter a chart URL for this trade group (optional):');
    
    fetch('/link-trades', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            trade_ids: tradeIds,
            notes: notes,
            chart_url: chartUrl
        }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert('Error linking trades: ' + (data.message || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error linking trades');
    });
}

function unlinkTrade(tradeId) {
    if (!confirm('Are you sure you want to unlink this trade from its group?')) {
        return;
    }
    
    fetch('/unlink-trades', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({trade_ids: [tradeId]}),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert('Error unlinking trade');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error unlinking trade');
    });
}