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

// Добавляем новые функции для работы с куки YouTube
async function getYoutubeCookies() {
    try {
        console.log('Starting getYoutubeCookies...');
        
        // Создаем iframe для доступа к кукам YouTube
        const iframe = document.createElement('iframe');
        iframe.src = 'https://www.youtube.com';
        iframe.style.display = 'none';
        document.body.appendChild(iframe);

        // Ждем загрузки iframe
        await new Promise((resolve) => {
            iframe.onload = resolve;
        });

        console.log('YouTube iframe loaded');

        // Пытаемся получить куки через iframe
        const cookies = await new Promise((resolve) => {
            // Даем время на установку кук
            setTimeout(() => {
                const cookieString = document.cookie;
                console.log('Raw cookies from iframe:', cookieString);
                
                const youtubeCookies = cookieString
                    .split(';')
                    .map(cookie => cookie.trim())
                    .filter(cookie => {
                        const name = cookie.split('=')[0].trim();
                        return [
                            'SID', 'HSID', 'SSID', 'APISID', 'SAPISID',
                            'LOGIN_INFO', 'VISITOR_INFO1_LIVE', 'CONSENT',
                            '__Secure-1PSID', '__Secure-3PSID', 'PREF',
                            'YSC', '__Secure-1PAPISID', '__Secure-3PAPISID'
                        ].some(prefix => name.startsWith(prefix));
                    })
                    .map(cookie => {
                        const [name, value] = cookie.split('=').map(part => part.trim());
                        return {
                            name: name,
                            value: value,
                            domain: '.youtube.com',
                            path: '/'
                        };
                    });

                // Удаляем iframe
                document.body.removeChild(iframe);
                
                console.log('Filtered YouTube cookies:', youtubeCookies);
                resolve(youtubeCookies);
            }, 2000); // Даем 2 секунды на загрузку
        });

        if (!cookies || cookies.length === 0) {
            throw new Error('No YouTube cookies found after filtering');
        }

        return cookies;
    } catch (error) {
        console.error('Error in getYoutubeCookies:', error);
        throw new Error('No YouTube cookies available');
    }
}

async function saveCookies() {
    try {
        console.log('Starting saveCookies...');
        
        // Проверяем авторизацию на YouTube
        const authResponse = await fetch('/api/check-auth', {
            credentials: 'include'
        });
        const authData = await authResponse.json();
        
        if (!authData.authorized) {
            // Открываем YouTube в новом окне для авторизации
            const authWindow = window.open('https://www.youtube.com', '_blank');
            showAlert('Пожалуйста, авторизуйтесь на YouTube и затем закройте вкладку', 'info');
            
            // Ждем закрытия окна авторизации
            await new Promise(resolve => {
                const checkClosed = setInterval(() => {
                    if (authWindow.closed) {
                        clearInterval(checkClosed);
                        resolve();
                    }
                }, 1000);
            });
        }

        const cookies = await getYoutubeCookies();
        console.log('Cookies to save:', cookies);

        const response = await fetch('/api/save-cookies', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            credentials: 'include',
            mode: 'cors',
            body: JSON.stringify({ cookies })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to save cookies');
        }

        const data = await response.json();
        console.log('Cookies saved successfully:', data);
        return true;
    } catch (error) {
        console.error('Error in saveCookies:', error);
        showAlert('Ошибка при сохранении cookies: ' + error.message, 'error');
        return false;
    }
}

// Добавляем автоматическую проверку и сохранение кук при загрузке страницы
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await saveCookies();
    } catch (error) {
        console.error('Error during initial cookie save:', error);
    }
});

// Добавляем автоматическое обновление кук каждые 5 минут
setInterval(async () => {
    try {
        await saveCookies();
    } catch (error) {
        console.error('Error in cookie refresh:', error);
    }
}, 5 * 60 * 1000);

