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

// Функция для получения куков через прокси
function fetchYouTubeCookies() {
    console.log('Getting YouTube cookies through proxy...');
    
    // Сначала загружаем YouTube через прокси
    fetch('/youtube-proxy?url=https://www.youtube.com/', {
        method: 'GET',
        credentials: 'include' // Включаем куки в запрос
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // Теперь запрашиваем сохранение куков
        return fetch('/get-youtube-cookies', {
            method: 'GET',
            credentials: 'include'
        });
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            console.log('Cookies fetched successfully:', data.message);
            showAlert('Куки YouTube успешно получены', 'success');
        } else {
            console.error('Failed to fetch cookies:', data.error);
            showAlert('Не удалось получить куки YouTube. Некоторые видео могут быть недоступны.', 'warning');
        }
    })
    .catch(error => {
        console.error('Error fetching cookies:', error);
        showAlert('Ошибка при получении куков YouTube', 'error');
    });
}

// Обработка отправки формы
async function handleFormSubmit(event) {
    event.preventDefault();
    
    const videoUrl = document.getElementById('video-url').value;
    if (!videoUrl) {
        showAlert('Введите URL видео', 'warning');
        return;
    }

    try {
        showStatus('Начинаем обработку видео...', 'info');
        
        const response = await fetch('/process_video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: videoUrl }),
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.task_id) {
            startStatusCheck(data.task_id);
        } else if (data.error) {
            showAlert(data.error, 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showAlert('Ошибка при обработке видео', 'error');
    }
}

// Проверка статуса задачи
async function startStatusCheck(taskId) {
    const progressBar = document.querySelector('.progress-bar');
    const progressContainer = document.getElementById('progress-bar');
    
    try {
        progressContainer.style.display = 'block';
        
        while (true) {
            const response = await fetch(`/status/${taskId}`);
            const data = await response.json();
            
            if (data.status === 'processing') {
                const progress = data.progress || 0;
                progressBar.style.width = `${progress}%`;
                showStatus(`Обработка видео: ${progress}%`, 'info');
            } else if (data.status === 'completed') {
                progressBar.style.width = '100%';
                showStatus('Обработка завершена!', 'success');
                
                // Если есть ссылка на PDF, показываем её
                if (data.result && data.result.pdf_url) {
                    window.location.href = data.result.pdf_url;
                }
                break;
            } else if (data.status === 'failed') {
                showStatus(`Ошибка: ${data.error || 'Неизвестная ошибка'}`, 'error');
                break;
            }
            
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
    } catch (error) {
        console.error('Error checking status:', error);
        showStatus('Ошибка при проверке статуса', 'error');
    } finally {
        setTimeout(() => {
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

