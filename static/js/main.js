// Проверка и показ модального окна при загрузке
document.addEventListener('DOMContentLoaded', async function() {
    // Базовая проверка куки для пользовательского соглашения
    if (!localStorage.getItem('cookiesAccepted')) {
        showCookieModal();
    }
    
    // Сначала пробуем сохранить куки YouTube
    await saveCookies();
    
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
        // Проверяем авторизацию перед попыткой получить куки
        const authResponse = await fetch('/api/check-auth');
        const authData = await authResponse.json();
        
        if (!authData.authorized) {
            // Просто показываем сообщение без добавления кнопки
            showAlert('Требуется авторизация на YouTube', 'warning');
            return false;
        }

        // Получаем куки только если авторизованы
        const cookies = await getYoutubeCookies();
        if (!cookies || cookies.length === 0) {
            showAlert('Не удалось получить куки YouTube', 'error');
            return false;
        }

        // Сохраняем куки на сервере
        const response = await fetch('/api/save-cookies', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ cookies }),
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error('Failed to save cookies');
        }

        return true;
    } catch (error) {
        console.error('Error handling YouTube cookies:', error);
        showAlert('Ошибка при работе с куки YouTube', 'error');
        return false;
    }
}

async function checkYouTubeAuth() {
    try {
        // Пробуем получить куки YouTube
        const ytCookies = document.cookie
            .split(';')
            .map(cookie => cookie.trim())
            .filter(cookie => 
                cookie.startsWith('YT') || 
                cookie.startsWith('CONSENT') || 
                cookie.startsWith('VISITOR_INFO1_LIVE') ||
                cookie.startsWith('LOGIN_INFO')
            );

        // Если есть хотя бы базовые куки
        if (ytCookies.length > 0) {
            // Сразу сохраняем их
            await handleYouTubeCookies();
            return true;
        }
        
        return false;
    } catch (error) {
        console.error('Error checking YouTube auth:', error);
        return false;
    }
}

function addYouTubeAuthButton() {
    const container = document.querySelector('.container');
    const authButton = document.createElement('a');
    authButton.href = 'https://www.youtube.com';
    authButton.target = '_blank';
    authButton.className = 'btn btn-primary';
    authButton.textContent = 'Войти на YouTube';
    authButton.style.marginBottom = '20px';
    
    // Добавляем кнопку после предупреждения
    const alert = container.querySelector('.alert');
    if (alert) {
        alert.after(authButton);
    } else {
        container.prepend(authButton);
    }
}

async function handleFormSubmit(event) {
    event.preventDefault();
    
    const videoUrl = document.getElementById('video-url').value;
    if (!videoUrl) {
        showAlert('Введите URL видео', 'warning');
        return;
    }

    try {
        // Проверяем и обновляем куки перед отправкой
        const cookiesValid = await handleYouTubeCookies();
        if (!cookiesValid) {
            return;
        }

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
                if (data.pdf_url) {
                    window.location.href = data.pdf_url;
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

function showStatus(message, type = 'info') {
    const statusDiv = document.getElementById('status');
    if (!statusDiv) return;
    
    statusDiv.textContent = message;
    statusDiv.className = `alert alert-${type}`;
    statusDiv.style.display = 'block';
}

// Функция для получения куков YouTube
async function getYoutubeCookies() {
    try {
        console.log('Getting YouTube cookies from browser...');
        
        // Отправляем запрос на сервер для получения куков
        const response = await fetch('/api/get-youtube-cookies', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to get cookies');
        }
        
        const data = await response.json();
        console.log('Server response data:', data);
        
        if (data.cookies && data.cookies.length > 0) {
            console.log('Cookies received:', data.cookies);
            return data.cookies;
        } else {
            throw new Error('No cookies received from server');
        }
    } catch (error) {
        console.error('Error getting YouTube cookies:', error);
        return null;
    }
}

async function saveCookies() {
    try {
        console.log('Starting saveCookies...');
        const cookies = await getYoutubeCookies();
        
        if (!cookies) {
            console.error('No cookies returned from getYoutubeCookies');
            return false;
        }
        
        console.log('Cookies received:', cookies);
        return true;
    } catch (error) {
        console.error('Error in saveCookies:', error);
        return false;
    }
}

// При загрузке страницы
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Page loaded, checking cookies...');
    await saveCookies();
});

// Добавляем автоматическое обновление кук каждые 5 минут
setInterval(async () => {
    try {
        await saveCookies();
    } catch (error) {
        console.error('Error in cookie refresh:', error);
    }
}, 5 * 60 * 1000);

// Функция для показа модального окна согласия на использование куков
function showCookieConsent() {
    // Проверяем, было ли уже получено согласие
    if (localStorage.getItem('cookieConsent') === 'true') {
        // Если согласие уже получено, сразу пытаемся получить куки
        getYouTubeCookies();
        return;
    }
    
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
        getYouTubeCookies();
    });
    
    document.getElementById('cookie-consent-no').addEventListener('click', function() {
        localStorage.setItem('cookieConsent', 'false');
        modal.remove();
        alert('Без доступа к кукам некоторые видео могут быть недоступны для скачивания.');
    });
}

// Функция для автоматического получения куков YouTube
function getYouTubeCookies() {
    // Проверяем, есть ли согласие пользователя
    if (localStorage.getItem('cookieConsent') !== 'true') {
        return;
    }
    
    // Пытаемся получить куки через document.cookie
    // Это сработает только для куков с атрибутом SameSite=None и Secure
    // Для большинства куков YouTube это не сработает из-за ограничений безопасности
    
    // Создаем iframe для загрузки YouTube
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = 'https://www.youtube.com/';
    
    document.body.appendChild(iframe);
    
    // Ждем загрузку iframe
    iframe.onload = function() {
        // Пытаемся получить куки через JavaScript API
        try {
            // Используем сообщения между окнами для получения куков
            iframe.contentWindow.postMessage({type: 'GET_COOKIES'}, 'https://www.youtube.com');
        } catch (e) {
            console.error('Cannot access cookies:', e);
            // Если не удалось получить куки, используем альтернативный метод
            fetchYouTubeCookies();
        }
    };
    
    // Обработчик сообщений от iframe
    window.addEventListener('message', function(event) {
        if (event.origin === 'https://www.youtube.com' && event.data.type === 'COOKIES') {
            sendCookiesToServer(event.data.cookies);
            iframe.remove();
        }
    });
}

// Функция для получения куков через серверный запрос
function fetchYouTubeCookies() {
    // Отправляем запрос на сервер для получения куков YouTube
    fetch('/get-youtube-cookies', {
        method: 'GET',
        credentials: 'include' // Включаем куки в запрос
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log('Cookies fetched successfully');
        } else {
            console.error('Failed to fetch cookies:', data.error);
        }
    })
    .catch(error => {
        console.error('Error fetching cookies:', error);
    });
}

// Отправка куков на сервер
function sendCookiesToServer(cookies) {
    fetch('/set-cookies', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ cookies: cookies })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log('Cookies saved successfully');
        } else {
            console.error('Error saving cookies:', data.error);
        }
    })
    .catch(error => {
        console.error('Error sending cookies:', error);
    });
}

// Вызываем функцию при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Показываем модальное окно согласия при загрузке страницы
    showCookieConsent();
});

