from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import logging
from datetime import datetime, timedelta
from config import (
    TELEGRAM_BOT_TOKEN, BASE_TARIFF_GB, BASE_TARIFF_DAYS, BASE_TARIFF_PRICE,
    EXTRA_GB_AMOUNT, EXTRA_GB_PRICE, FREE_MODE_SPEED_MBPS
)
from marzban_api import MarzbanAPI
from database import (
    get_user_by_telegram_id, create_user as db_create_user,
    update_user_tariff, enable_free_mode, add_transaction
)

app = Flask(__name__)
CORS(app)  # Разрешаем CORS для Telegram Web App

marzban = MarzbanAPI()

def run_async(coro):
    """Запуск async функции в синхронном контексте"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

@app.route('/api/user/status', methods=['GET'])
def get_user_status():
    """Получить статус пользователя"""
    try:
        telegram_id = int(request.args.get('telegram_id'))
        
        # Получаем пользователя из БД
        user = run_async(get_user_by_telegram_id(telegram_id))
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404
        
        username = user["username"]
        
        # Получаем данные из Marzban
        marzban_user = run_async(marzban.get_user(username))
        if not marzban_user:
            return jsonify({"error": "Пользователь не найден в Marzban"}), 404
        
        used_gb = marzban_user.get("used_traffic", 0) / (1024**3)
        limit_gb = marzban_user.get("data_limit", 0) / (1024**3) if marzban_user.get("data_limit") else None
        status = marzban_user.get("status", "unknown")
        expire = marzban_user.get("expire", 0)
        
        expire_date = None
        if expire:
            expire_date = datetime.fromtimestamp(expire).isoformat()
        
        free_mode = user.get("free_mode_enabled", 0)
        
        return jsonify({
            "username": username,
            "status": status,
            "used_gb": round(used_gb, 2),
            "limit_gb": round(limit_gb, 2) if limit_gb else None,
            "expire_date": expire_date,
            "free_mode": bool(free_mode),
            "tariff_type": user.get("tariff_type", "base")
        })
    except Exception as e:
        logging.error(f"Error in get_user_status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/user/config', methods=['GET'])
def get_user_config():
    """Получить конфигурацию пользователя"""
    try:
        telegram_id = int(request.args.get('telegram_id'))
        
        user = run_async(get_user_by_telegram_id(telegram_id))
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404
        
        username = user["username"]
        config = run_async(marzban.get_user_config(username))
        
        if not config:
            return jsonify({"error": "Не удалось получить конфигурацию"}), 404
        
        return jsonify({"config": config})
    except Exception as e:
        logging.error(f"Error in get_user_config: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/user/create', methods=['POST'])
def create_user():
    """Создать VPN ключ для пользователя"""
    try:
        data = request.json
        telegram_id = int(data.get('telegram_id'))
        
        # Проверяем, не существует ли уже пользователь
        user = run_async(get_user_by_telegram_id(telegram_id))
        if user:
            return jsonify({"error": "У вас уже есть VPN ключ"}), 400
        
        username = f"user_{telegram_id}"
        
        # Создаем пользователя в Marzban
        user_data = run_async(marzban.create_user(
            username=username,
            data_limit_gb=BASE_TARIFF_GB,
            expire_days=BASE_TARIFF_DAYS
        ))
        
        if not user_data:
            return jsonify({"error": "Ошибка при создании ключа"}), 500
        
        # Сохраняем в БД
        run_async(db_create_user(telegram_id, username, "base"))
        run_async(add_transaction(telegram_id, BASE_TARIFF_PRICE, "base_tariff"))
        
        # Получаем конфигурацию
        config = run_async(marzban.get_user_config(username))
        
        return jsonify({
            "success": True,
            "username": username,
            "config": config,
            "limit_gb": BASE_TARIFF_GB,
            "expire_days": BASE_TARIFF_DAYS
        })
    except Exception as e:
        logging.error(f"Error in create_user: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/user/buy-extra', methods=['POST'])
def buy_extra():
    """Купить дополнительные 100 ГБ"""
    try:
        data = request.json
        telegram_id = int(data.get('telegram_id'))
        
        user = run_async(get_user_by_telegram_id(telegram_id))
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404
        
        username = user["username"]
        
        # Добавляем трафик
        result = run_async(marzban.add_traffic(username, EXTRA_GB_AMOUNT))
        if not result:
            return jsonify({"error": "Ошибка при добавлении трафика"}), 500
        
        # Сохраняем транзакцию
        run_async(add_transaction(telegram_id, EXTRA_GB_PRICE, "extra_gb"))
        
        # Получаем обновленную информацию
        updated_user = run_async(marzban.get_user(username))
        limit_gb = updated_user.get("data_limit", 0) / (1024**3) if updated_user else None
        
        return jsonify({
            "success": True,
            "new_limit_gb": round(limit_gb, 2) if limit_gb else None
        })
    except Exception as e:
        logging.error(f"Error in buy_extra: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/user/free-mode', methods=['POST'])
def enable_free():
    """Включить бесплатный режим"""
    try:
        data = request.json
        telegram_id = int(data.get('telegram_id'))
        
        user = run_async(get_user_by_telegram_id(telegram_id))
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404
        
        username = user["username"]
        
        # Переключаем на бесплатный режим
        result = run_async(marzban.switch_to_free_mode(username))
        if not result:
            return jsonify({"error": "Ошибка при переключении на бесплатный режим"}), 500
        
        # Вычисляем дату до конца месяца
        now = datetime.now()
        if now.month == 12:
            end_of_month = datetime(now.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_of_month = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
        
        # Сохраняем в БД
        run_async(enable_free_mode(telegram_id, end_of_month))
        run_async(update_user_tariff(telegram_id, "free"))
        
        # Получаем новую конфигурацию
        config = run_async(marzban.get_user_config(username))
        
        return jsonify({
            "success": True,
            "config": config,
            "expire_date": end_of_month.isoformat()
        })
    except Exception as e:
        logging.error(f"Error in enable_free: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/tariffs', methods=['GET'])
def get_tariffs():
    """Получить информацию о тарифах"""
    return jsonify({
        "base": {
            "gb": BASE_TARIFF_GB,
            "days": BASE_TARIFF_DAYS,
            "price": BASE_TARIFF_PRICE
        },
        "extra": {
            "gb": EXTRA_GB_AMOUNT,
            "price": EXTRA_GB_PRICE
        },
        "free_mode": {
            "speed_mbps": FREE_MODE_SPEED_MBPS
        }
    })

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host='127.0.0.1', port=5000, debug=False)

