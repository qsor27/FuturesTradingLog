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