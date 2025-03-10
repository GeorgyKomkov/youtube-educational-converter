// Единая функция для инициализации при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, было ли уже получено согласие
    if (localStorage.getItem('cookieConsent') === 'true') {
        // Если согласие уже получено, сразу пытаемся получить куки
        fetchYouTubeCookies();
    } else {
        // Показываем модальное окно согласия
        showCookieConsent();
    }
    
    // Инициализация формы
    const form = document.getElementById('video-form');
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    } else {
        console.error('Form with id "video-form" not found');
    }
});

// Функция для показа модального окна согласия на использование куков
function showCookieConsent() {
    // Создаем модальное окно
    const modal = document.createElement('div');
    modal.className = 'cookie-modal';
    modal.innerHTML = `
        <div class="cookie-modal-content">
            <h3>Использование куков YouTube</h3>
            <p>Для скачивания и обработки видео с YouTube нам необходимо использовать куки вашего браузера.</p>
            <p>Это позволит нам скачивать видео, которые требуют авторизации или имеют ограничения.</p>
            <p>Мы используем куки только для скачивания видео и не храним их для других целей.</p>
            <div class="cookie-modal-buttons">
                <button id="cookie-consent-yes">Согласен</button>
                <button id="cookie-consent-no">Не согласен</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Обработчики для кнопок
    document.getElementById('cookie-consent-yes').addEventListener('click', function() {
        localStorage.setItem('cookieConsent', 'true');
        modal.remove();
        fetchYouTubeCookies();
    });
    
    document.getElementById('cookie-consent-no').addEventListener('click', function() {
        localStorage.setItem('cookieConsent', 'false');
        modal.remove();
        showAlert('Без доступа к кукам некоторые видео могут быть недоступны для скачивания.', 'warning');
    });
}

// Функция для получения куков YouTube
async function fetchYouTubeCookies() {
    try {
        console.log('Fetching YouTube cookies...');
        const response = await fetch('/get-youtube-cookies');
        console.log('YouTube cookies response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Error fetching YouTube cookies:', errorText);
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('YouTube cookies response:', data);
        
        if (data.status === 'success') {
            console.log('YouTube cookies fetched successfully');
            showAlert('Куки YouTube успешно получены', 'success');
        } else {
            console.error('Failed to fetch YouTube cookies:', data.error);
            showAlert('Не удалось получить куки YouTube', 'error');
        }
    } catch (error) {
        console.error('Error fetching YouTube cookies:', error);
        showAlert('Ошибка при получении куков YouTube', 'error');
    }
}

// Обработка отправки формы
async function handleFormSubmit(event) {
    event.preventDefault();
    console.log('Form submitted');
    
    const form = event.target;
    const urlInput = form.querySelector('input[name="url"]');
    const url = urlInput.value.trim();
    
    if (!url) {
        showAlert('Пожалуйста, введите URL видео', 'warning');
        return;
    }
    
    // Проверяем, что URL является действительным URL YouTube
    if (!isValidYouTubeUrl(url)) {
        showAlert('Пожалуйста, введите корректный URL YouTube', 'warning');
        return;
    }
    
    console.log('Video URL:', url);
    
    try {
        // Отправляем запрос на обработку видео
        console.log('Sending request to process video:', url);
        const response = await fetch('/process_video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });
        
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Error response:', errorText);
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Response data:', data);
        
        if (data.task_id) {
            console.log('Starting status check for task:', data.task_id);
            showStatus('Видео обрабатывается...', 'info');
            startStatusCheck(data.task_id);
        } else {
            console.error('No task_id in response');
            showAlert('Ошибка при обработке видео', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showAlert('Ошибка при обработке видео: ' + error.message, 'error');
    }
}

// Проверка статуса задачи
async function startStatusCheck(taskId) {
    console.log('Starting status check for task:', taskId);
    
    const progressBar = document.querySelector('.progress-bar');
    const progressContainer = document.getElementById('progress-bar');
    
    try {
        console.log('Showing progress bar');
        progressContainer.style.display = 'block';
        
        while (true) {
            console.log('Checking status for task:', taskId);
            const response = await fetch(`/status/${taskId}`);
            console.log('Status response:', response.status);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('Error checking status:', errorText);
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Status data:', data);
            
            if (data.status === 'processing') {
                const progress = data.progress || 0;
                console.log('Task is processing, progress:', progress);
                progressBar.style.width = `${progress}%`;
                showStatus(`Обработка видео: ${progress}%`, 'info');
            } else if (data.status === 'completed') {
                console.log('Task completed successfully');
                progressBar.style.width = '100%';
                showStatus('Обработка завершена!', 'success');
                
                // Если есть ссылка на PDF, показываем её
                if (data.result && data.result.pdf_url) {
                    console.log('Opening PDF:', data.result.pdf_url);
                    window.location.href = data.result.pdf_url;
                } else if (data.result && data.result.video_path) {
                    console.log('Video path:', data.result.video_path);
                    // Извлекаем имя файла из пути
                    const fileName = data.result.video_path.split('/').pop();
                    // Создаем ссылку для скачивания
                    const downloadLink = document.createElement('a');
                    downloadLink.href = `/download/${fileName}`;
                    downloadLink.className = 'btn btn-success mt-3';
                    downloadLink.textContent = 'Скачать видео';
                    downloadLink.download = fileName;
                    
                    // Добавляем ссылку на страницу
                    const container = document.querySelector('.container');
                    container.appendChild(downloadLink);
                    
                    showAlert('Видео успешно обработано! Вы можете скачать его.', 'success');
                } else {
                    console.log('No result data:', data.result);
                    showAlert('Видео обработано, но результат недоступен', 'warning');
                }
                break;
            } else if (data.status === 'failed') {
                console.error('Task failed:', data.error);
                showStatus(`Ошибка: ${data.error || 'Неизвестная ошибка'}`, 'error');
                break;
            } else {
                console.log('Unknown task status:', data.status);
            }
            
            console.log('Waiting 2 seconds before next check');
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
    } catch (error) {
        console.error('Error checking status:', error);
        showStatus('Ошибка при проверке статуса: ' + error.message, 'error');
    } finally {
        setTimeout(() => {
            console.log('Hiding progress bar');
            progressContainer.style.display = 'none';
        }, 3000);
    }
}

// Показ уведомлений
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

// Показ статуса
function showStatus(message, type = 'info') {
    const statusDiv = document.getElementById('status');
    if (!statusDiv) return;
    
    statusDiv.textContent = message;
    statusDiv.className = `alert alert-${type}`;
    statusDiv.style.display = 'block';
}

// Добавляем автоматическое обновление кук каждые 30 минут
setInterval(() => {
    if (localStorage.getItem('cookieConsent') === 'true') {
        fetchYouTubeCookies();
    }
}, 30 * 60 * 1000);

