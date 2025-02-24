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

    console.log('Form submitted with URL:', url);

    try {
        const response = await fetch('/process_video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url })
        });

        console.log('Server response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Server error:', errorText);
            throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        console.log('Server response data:', data);
        
        if (data.task_id) {
            await checkConversionStatus(data.task_id);
        } else {
            throw new Error('No task ID received');
        }
    } catch (error) {
        console.error('Error:', error);
        showAlert('Error: ' + error.message);
    }
}

async function checkConversionStatus(taskId) {
    try {
        // Показываем индикатор прогресса при начале проверки
        document.getElementById('conversion-progress').style.display = 'block';
        let retryCount = 0;
        const maxRetries = 3;
        
        while (true) {
            try {
                console.log('Checking status for task:', taskId);
                
                const response = await fetch('/status/' + taskId, {
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`Server returned ${response.status}: ${errorText}`);
                }

                const data = await response.json();
                console.log('Status response:', data);
                
                // Обновляем прогресс-бар
                const progressBar = document.getElementById('progress-bar-fill');
                if (progressBar) {
                    progressBar.style.width = `${data.progress || 0}%`;
                }
                
                if (data.status === 'completed') {
                    showStatus('Conversion completed!', 'success');
                    document.getElementById('conversion-progress').style.display = 'none';
                    
                    if (data.result && data.result.download_url) {
                        window.location.href = data.result.download_url;
                    }
                    break;
                    
                } else if (data.status === 'failed') {
                    const errorMessage = data.error || 'Conversion failed';
                    console.error('Task failed:', errorMessage);
                    throw new Error(errorMessage);
                } else if (data.status === 'error') {
                    // Добавляем обработку статуса error
                    const errorMessage = data.message || 'An error occurred during conversion';
                    console.error('Task error:', errorMessage);
                    throw new Error(errorMessage);
                } else {
                    showStatus(`Converting... ${data.progress || 0}%`, 'info');
                }
                
                // Сбрасываем счетчик повторов при успешном запросе
                retryCount = 0;
                
            } catch (error) {
                console.error('Error in status check iteration:', error);
                retryCount++;
                
                if (retryCount >= maxRetries) {
                    throw new Error(`Failed after ${maxRetries} retries: ${error.message}`);
                }
                
                // Ждем перед повторной попыткой
                await new Promise(resolve => setTimeout(resolve, 5000));
                continue;
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

