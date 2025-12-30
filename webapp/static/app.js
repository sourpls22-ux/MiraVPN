const API_URL = 'https://app.miravpn.com/api';

// Инициализация Telegram Web App
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// Получаем данные пользователя из Telegram
const initData = tg.initDataUnsafe;
const telegramId = initData?.user?.id;

if (!telegramId) {
    showError('Не удалось получить данные пользователя');
}

// Загрузка тарифов
async function loadTariffs() {
    try {
        const response = await fetch(`${API_URL}/tariffs`);
        const data = await response.json();
        
        document.getElementById('base-gb').textContent = data.base.gb;
        document.getElementById('base-days').textContent = data.base.days;
        document.getElementById('base-price').textContent = data.base.price;
        document.getElementById('extra-gb').textContent = data.extra.gb;
        document.getElementById('extra-price').textContent = data.extra.price;
    } catch (error) {
        console.error('Error loading tariffs:', error);
    }
}

// Проверка статуса пользователя
async function checkUserStatus() {
    try {
        const response = await fetch(`${API_URL}/user/status?telegram_id=${telegramId}`);
        
        if (response.status === 404) {
            // Пользователь не найден - показываем экран покупки
            showWelcomeScreen();
            return;
        }
        
        if (!response.ok) {
            throw new Error('Ошибка при получении статуса');
        }
        
        const data = await response.json();
        showUserScreen(data);
    } catch (error) {
        console.error('Error checking user status:', error);
        showError('Ошибка при загрузке данных');
    }
}

// Показать экран покупки
function showWelcomeScreen() {
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('welcome-screen').classList.remove('hidden');
    document.getElementById('user-screen').classList.add('hidden');
}

// Показать экран пользователя
function showUserScreen(data) {
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('welcome-screen').classList.add('hidden');
    document.getElementById('user-screen').classList.remove('hidden');
    
    // Заполняем данные
    document.getElementById('username-display').textContent = data.username;
    
    // Статус
    const statusEmoji = {
        'active': '✅',
        'expired': '⏰',
        'limited': '📊',
        'disabled': '❌'
    }[data.status] || '❓';
    
    document.getElementById('status-icon').textContent = statusEmoji;
    document.getElementById('status-text').textContent = data.status;
    
    // Режим
    const modeBadge = document.getElementById('mode-badge');
    if (data.free_mode) {
        modeBadge.textContent = '🐌 Бесплатный режим (2 Мбит/с)';
    } else {
        modeBadge.textContent = '🚀 Быстрый режим';
    }
    
    // Использование трафика
    const usedGb = data.used_gb;
    const limitGb = data.limit_gb || 0;
    const percentage = limitGb > 0 ? (usedGb / limitGb) * 100 : 0;
    
    document.getElementById('used-gb').textContent = usedGb.toFixed(2);
    document.getElementById('limit-gb').textContent = limitGb.toFixed(0);
    document.getElementById('progress-fill').style.width = `${Math.min(percentage, 100)}%`;
    
    // Дата истечения
    if (data.expire_date) {
        const date = new Date(data.expire_date);
        document.getElementById('expire-date').textContent = date.toLocaleDateString('ru-RU');
    } else {
        document.getElementById('expire-date').textContent = 'Бессрочно';
    }
}

// Создание VPN ключа
async function createVPN() {
    try {
        tg.showAlert('⏳ Создаю ваш VPN ключ...');
        
        const response = await fetch(`${API_URL}/user/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ telegram_id: telegramId })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Ошибка при создании ключа');
        }
        
        const data = await response.json();
        
        // Показываем конфигурацию
        showConfigModal(data.config);
        
        // Обновляем экран
        await checkUserStatus();
        
        showNotification('✅ VPN ключ создан успешно!');
    } catch (error) {
        console.error('Error creating VPN:', error);
        tg.showAlert(`❌ ${error.message}`);
    }
}

// Получение конфигурации
async function getConfig() {
    try {
        tg.showAlert('⏳ Загружаю конфигурацию...');
        
        const response = await fetch(`${API_URL}/user/config?telegram_id=${telegramId}`);
        
        if (!response.ok) {
            throw new Error('Ошибка при получении конфигурации');
        }
        
        const data = await response.json();
        showConfigModal(data.config);
    } catch (error) {
        console.error('Error getting config:', error);
        tg.showAlert(`❌ ${error.message}`);
    }
}

// Покупка дополнительных 100 ГБ
async function buyExtra() {
    try {
        if (!confirm('Купить дополнительные 100 ГБ за 99₽?')) {
            return;
        }
        
        tg.showAlert('⏳ Обрабатываю запрос...');
        
        const response = await fetch(`${API_URL}/user/buy-extra`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ telegram_id: telegramId })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Ошибка при покупке');
        }
        
        const data = await response.json();
        
        showNotification('✅ Дополнительные 100 ГБ добавлены!');
        
        // Обновляем экран
        await checkUserStatus();
    } catch (error) {
        console.error('Error buying extra:', error);
        tg.showAlert(`❌ ${error.message}`);
    }
}

// Включение бесплатного режима
async function enableFreeMode() {
    try {
        if (!confirm('Включить бесплатный режим (2 Мбит/с) до конца месяца?')) {
            return;
        }
        
        tg.showAlert('⏳ Включаю бесплатный режим...');
        
        const response = await fetch(`${API_URL}/user/free-mode`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ telegram_id: telegramId })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Ошибка при переключении');
        }
        
        const data = await response.json();
        
        // Показываем новую конфигурацию
        showConfigModal(data.config);
        
        showNotification('✅ Бесплатный режим включен!');
        
        // Обновляем экран
        await checkUserStatus();
    } catch (error) {
        console.error('Error enabling free mode:', error);
        tg.showAlert(`❌ ${error.message}`);
    }
}

// Показать модальное окно с конфигурацией
function showConfigModal(config) {
    document.getElementById('config-text').value = config;
    document.getElementById('config-modal').classList.remove('hidden');
}

// Закрыть модальное окно
function closeConfigModal() {
    document.getElementById('config-modal').classList.add('hidden');
}

// Копировать конфигурацию
function copyConfig() {
    const configText = document.getElementById('config-text');
    configText.select();
    document.execCommand('copy');
    showNotification('📋 Конфигурация скопирована!');
}

// Показать уведомление
function showNotification(message) {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.classList.remove('hidden');
    
    setTimeout(() => {
        notification.classList.add('hidden');
    }, 3000);
}

// Показать ошибку
function showError(message) {
    tg.showAlert(`❌ ${message}`);
}

// Обработчики событий
document.addEventListener('DOMContentLoaded', async () => {
    await loadTariffs();
    await checkUserStatus();
    
    // Кнопки
    document.getElementById('buy-vpn-btn').addEventListener('click', createVPN);
    document.getElementById('get-config-btn').addEventListener('click', getConfig);
    document.getElementById('buy-extra-btn').addEventListener('click', buyExtra);
    document.getElementById('free-mode-btn').addEventListener('click', enableFreeMode);
    document.getElementById('close-config').addEventListener('click', closeConfigModal);
    document.getElementById('copy-config-btn').addEventListener('click', copyConfig);
    
    // Закрытие модального окна по клику вне его
    document.getElementById('config-modal').addEventListener('click', (e) => {
        if (e.target.id === 'config-modal') {
            closeConfigModal();
        }
    });
});

