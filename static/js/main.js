async function exportYouTubeCookies() {
    try {
        // Получаем куки через document.cookie
        const cookies = document.cookie
            .split(';')
            .map(cookie => cookie.trim())
            .filter(cookie => cookie.startsWith('YT'));
        
        // Отправляем на сервер
        const response = await fetch('/save_cookies', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(cookies)
        });

        if (!response.ok) {
            throw new Error('Failed to save cookies');
        }

        showAlert('Cookies successfully exported', 'success');
    } catch (error) {
        showAlert('Failed to export cookies: ' + error.message, 'error');
    }
}

async function startConversion() {
    const urlInput = document.getElementById('url');
    const statusDiv = document.getElementById('status');
    const url = urlInput.value.trim();

    if (!url) {
        showStatus('Please enter a YouTube URL', 'error');
        return;
    }

    try {
        // Начинаем конвертацию
        const response = await fetch('/api/convert', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });

        const data = await response.json();

        if (data.error) {
            showStatus(data.error, 'error');
            return;
        }

        // Начинаем проверять статус
        checkStatus(data.task_id);

    } catch (error) {
        showStatus('Error starting conversion: ' + error, 'error');
    }
}

async function checkStatus(taskId) {
    try {
        const response = await fetch(`/api/status/${taskId}`);
        const data = await response.json();

        if (data.status === 'completed') {
            showStatus('Conversion completed! Downloading...', 'success');
            window.location.href = data.download_url;
        } else if (data.status === 'failed') {
            showStatus('Conversion failed: ' + data.error, 'error');
        } else {
            showStatus(`Converting... ${data.progress}%`, 'info');
            setTimeout(() => checkStatus(taskId), 2000);
        }
    } catch (error) {
        showStatus('Error checking status: ' + error, 'error');
    }
}

function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

function showStatus(message, type) {
    const statusDiv = document.getElementById('status');
    statusDiv.textContent = message;
    statusDiv.className = type;
}
