// Проверка и показ модального окна при загрузке
document.addEventListener('DOMContentLoaded', function() {
    if (!localStorage.getItem('cookiesAccepted')) {
        showCookieModal();
    } else {
        // Если куки приняты, запускаем фоновый процесс
        handleYouTubeCookies();
    }

    // Ищем форму по id
    const form = document.getElementById('video-form');
    
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    } else {
        console.error('Form with id "video-form" not found');
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

async function handleFormSubmit(event) {
    event.preventDefault();
    
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
        
        // Показываем индикатор прогресса
        document.getElementById('conversion-progress').style.display = 'block';
        showStatus('Starting conversion...', 'info');
        
        // Отправляем запрос
        const response = await fetch('/process_video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ url })
        });

        console.log('Got response:', response); // Отладочный лог

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const data = await response.json();
        console.log('Response data:', data); // Отладочный лог

        if (data.error) {
            throw new Error(data.error);
        }

        // Начинаем проверять статус
        await checkConversionStatus(data.task_id);

    } catch (error) {
        console.error('Error:', error);
        showAlert('Error starting conversion: ' + error.message, 'error');
        document.getElementById('conversion-progress').style.display = 'none';
    }
}

async function checkConversionStatus(taskId) {
    try {
        while (true) {
            const response = await fetch(`/status/${taskId}`);
            const data = await response.json();
            
            // Обновляем прогресс-бар
            const progressBar = document.getElementById('progress-bar-fill');
            progressBar.style.width = `${data.progress}%`;
            
            if (data.status === 'completed') {
                // Скрываем индикатор прогресса
                document.getElementById('conversion-progress').style.display = 'none';
                showStatus('Conversion completed!', 'success');
                
                // Скачиваем PDF
                window.location.href = `/download/${taskId}`;
                break;
                
            } else if (data.status === 'failed') {
                throw new Error(data.error || 'Conversion failed');
            } else {
                showStatus(`Converting... ${data.progress || 0}%`, 'info');
            }
            
            // Ждем перед следующей проверкой
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
    } catch (error) {
        console.error('Error checking status:', error);
        showAlert('Error checking conversion status: ' + error.message, 'error');
        document.getElementById('conversion-progress').style.display = 'none';
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

