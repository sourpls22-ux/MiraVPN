import aiosqlite
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

DB_PATH = "vpn_bot.db"

async def init_db():
    """Инициализация базы данных и создание таблиц"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                tariff_type TEXT DEFAULT 'base',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_check TIMESTAMP,
                free_mode_enabled BOOLEAN DEFAULT 0,
                free_mode_until TIMESTAMP
            )
        """)
        
        # Таблица транзакций
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            )
        """)
        
        await db.commit()
        logger.info("База данных инициализирована")

async def create_user(telegram_id: int, username: str, tariff_type: str = "base") -> bool:
    """Создание нового пользователя в базе данных"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO users (telegram_id, username, tariff_type, created_at)
                VALUES (?, ?, ?, ?)
            """, (telegram_id, username, tariff_type, datetime.now()))
            await db.commit()
            logger.info(f"Пользователь создан: {telegram_id} -> {username}")
            return True
    except aiosqlite.IntegrityError:
        logger.warning(f"Пользователь уже существует: {telegram_id}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при создании пользователя: {e}")
        return False

async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict]:
    """Получить пользователя по Telegram ID"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM users WHERE telegram_id = ?
            """, (telegram_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None
    except Exception as e:
        logger.error(f"Ошибка при получении пользователя: {e}")
        return None

async def get_user_by_username(username: str) -> Optional[Dict]:
    """Получить пользователя по username"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM users WHERE username = ?
            """, (username,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None
    except Exception as e:
        logger.error(f"Ошибка при получении пользователя: {e}")
        return None

async def update_user_tariff(telegram_id: int, tariff_type: str) -> bool:
    """Обновить тип тарифа пользователя"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE users SET tariff_type = ? WHERE telegram_id = ?
            """, (tariff_type, telegram_id))
            await db.commit()
            logger.info(f"Тариф обновлен для {telegram_id}: {tariff_type}")
            return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении тарифа: {e}")
        return False

async def update_last_check(telegram_id: int) -> bool:
    """Обновить время последней проверки"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE users SET last_check = ? WHERE telegram_id = ?
            """, (datetime.now(), telegram_id))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении last_check: {e}")
        return False

async def enable_free_mode(telegram_id: int, until_timestamp: datetime) -> bool:
    """Включить бесплатный режим для пользователя"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE users 
                SET free_mode_enabled = 1, free_mode_until = ?
                WHERE telegram_id = ?
            """, (until_timestamp, telegram_id))
            await db.commit()
            logger.info(f"Бесплатный режим включен для {telegram_id} до {until_timestamp}")
            return True
    except Exception as e:
        logger.error(f"Ошибка при включении бесплатного режима: {e}")
        return False

async def disable_free_mode(telegram_id: int) -> bool:
    """Отключить бесплатный режим для пользователя"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE users 
                SET free_mode_enabled = 0, free_mode_until = NULL
                WHERE telegram_id = ?
            """, (telegram_id,))
            await db.commit()
            logger.info(f"Бесплатный режим отключен для {telegram_id}")
            return True
    except Exception as e:
        logger.error(f"Ошибка при отключении бесплатного режима: {e}")
        return False

async def get_all_users() -> List[Dict]:
    """Получить всех пользователей для проверки лимитов"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Ошибка при получении всех пользователей: {e}")
        return []

async def add_transaction(telegram_id: int, amount: float, transaction_type: str) -> bool:
    """Добавить транзакцию"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO transactions (telegram_id, amount, type, timestamp)
                VALUES (?, ?, ?, ?)
            """, (telegram_id, amount, transaction_type, datetime.now()))
            await db.commit()
            logger.info(f"Транзакция добавлена: {telegram_id} - {amount}₽ ({transaction_type})")
            return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении транзакции: {e}")
        return False

async def get_user_transactions(telegram_id: int, limit: int = 10) -> List[Dict]:
    """Получить транзакции пользователя"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM transactions 
                WHERE telegram_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (telegram_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Ошибка при получении транзакций: {e}")
        return []

