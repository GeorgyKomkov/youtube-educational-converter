async function exportYouTubeCookies() {
    try {
        // Проверяем поддержку API chrome.cookies
        if (typeof chrome === 'undefined' || !chrome.cookies) {
            throw new Error('Chrome cookies API is not available');
        }

        // Получаем cookies для youtube.com
        const cookies = await chrome.cookies.getAll({domain: ".youtube.com"});
        
        // Проверяем наличие cookies
        if (!cookies || cookies.length === 0) {
            throw new Error('No YouTube cookies found');
        }

        // Отправляем на сервер
        const response = await fetch('/api/set-cookies', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ cookies }),
            credentials: 'include' // Важно для работы с сессией
        });
        
        if (!response.ok) {
            throw new Error('Failed to set cookies');
        }
        
        showAlert('YouTube cookies successfully exported!', 'success');
    } catch (error) {
        console.error('Error exporting cookies:', error);
        showAlert('Failed to export cookies: ' + error.message, 'error');
    }
}

async function convertVideo() {
    const videoUrl = document.getElementById('video-url').value;
    if (!videoUrl) {
        showAlert('Please enter YouTube URL', 'error');
        return;
    }

    // Показываем индикатор загрузки
    const statusElement = document.getElementById('status');
    statusElement.innerHTML = '<div class="loading"></div> Starting conversion...';
    statusElement.style.display = 'block';

    try {
        const response = await fetch('/api/convert', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: videoUrl }),
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error('Conversion request failed');
        }

        const result = await response.json();
        if (result.task_id) {
            checkStatus(result.task_id);
        } else {
            throw new Error('No task ID received');
        }

    } catch (error) {
        console.error('Error:', error);
        showAlert('Failed to start conversion: ' + error.message, 'error');
        statusElement.style.display = 'none';
    }
}

function checkStatus(taskId) {
    const statusElement = document.getElementById('status');
    let retryCount = 0;
    const maxRetries = 60; // 2 минуты при интервале в 2 секунды

    const checkProgress = async () => {
        try {
            const response = await fetch(`/api/status/${taskId}`);
            if (!response.ok) {
                throw new Error('Failed to get status');
            }

            const data = await response.json();
            
            switch(data.status) {
                case 'completed':
                    showAlert('Conversion completed successfully!', 'success');
                    window.location.href = data.pdf_url;
                    statusElement.style.display = 'none';
                    break;
                    
                case 'failed':
                    throw new Error(data.error || 'Conversion failed');
                    
                case 'processing':
                    statusElement.innerHTML = `
                        <div class="loading"></div>
                        Converting video... ${data.progress || ''}
                    `;
                    if (retryCount++ < maxRetries) {
                        setTimeout(checkProgress, 2000);
                    } else {
                        throw new Error('Conversion timeout');
                    }
                    break;
                    
                default:
                    throw new Error('Unknown status');
            }
        } catch (error) {
            console.error('Error checking status:', error);
            showAlert('Error: ' + error.message, 'error');
            statusElement.style.display = 'none';
        }
    };

    checkProgress();
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
