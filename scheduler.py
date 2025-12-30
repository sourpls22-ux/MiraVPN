import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import get_all_users, update_last_check
from marzban_api import MarzbanAPI
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

# Глобальные переменные для бота и Marzban API
bot_instance = None
marzban_instance = None

def set_bot_and_marzban(bot: Bot, marzban: MarzbanAPI):
    """Установить экземпляры бота и Marzban API"""
    global bot_instance, marzban_instance
    bot_instance = bot
    marzban_instance = marzban

async def check_limits_task():
    """Проверка лимитов всех пользователей"""
    if not bot_instance or not marzban_instance:
        logger.error("Бот или Marzban API не инициализированы")
        return
    
    logger.info("Начинаю проверку лимитов пользователей...")
    
    # Получаем всех пользователей из БД
    db_users = await get_all_users()
    
    if not db_users:
        logger.info("Нет пользователей для проверки")
        return
    
    # Получаем всех пользователей из Marzban
    marzban_users_data = await marzban_instance.get_users()
    
    if not marzban_users_data or not marzban_users_data.get("users"):
        logger.warning("Не удалось получить пользователей из Marzban")
        return
    
    # Создаем словарь для быстрого поиска по username
    marzban_users = {user.get("username"): user for user in marzban_users_data["users"]}
    
    limited_count = 0
    
    # Проверяем каждого пользователя из БД
    for db_user in db_users:
        telegram_id = db_user["telegram_id"]
        username = db_user["username"]
        
        # Получаем данные пользователя из Marzban
        marzban_user = marzban_users.get(username)
        
        if not marzban_user:
            logger.warning(f"Пользователь {username} не найден в Marzban")
            continue
        
        status = marzban_user.get("status", "unknown")
        
        # Проверяем, если статус limited и пользователь еще не был уведомлен
        if status == "limited":
            limited_count += 1
            logger.info(f"Пользователь {username} (ID: {telegram_id}) превысил лимит")
            
            # Отправляем уведомление с выбором
            try:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💰 Купить +100 ГБ за 99₽",
                            callback_data=f"buy_extra_{telegram_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🐌 Включить бесплатный режим (2 Мбит/с)",
                            callback_data=f"enable_free_{telegram_id}"
                        )
                    ]
                ])
                
                used_gb = marzban_user.get("used_traffic", 0) / (1024**3)
                limit_gb = marzban_user.get("data_limit", 0) / (1024**3) if marzban_user.get("data_limit") else "∞"
                
                message_text = (
                    "⚠️ *Трафик закончился!*\n\n"
                    f"Использовано: {used_gb:.2f} GB / {limit_gb} GB\n\n"
                    "У тебя есть два пути:\n\n"
                    "💰 *Купить еще 100 ГБ за 99₽* (скорость 1 Гбит/с)\n\n"
                    "🐌 *Включить 'Бесплатный режим'* до конца месяца (скорость будет 2 Мбит/с)"
                )
                
                await bot_instance.send_message(
                    chat_id=telegram_id,
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                
                logger.info(f"Уведомление отправлено пользователю {telegram_id}")
                
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {telegram_id}: {e}")
        
        # Обновляем время последней проверки
        await update_last_check(telegram_id)
    
    logger.info(f"Проверка завершена. Найдено пользователей с превышением лимита: {limited_count}")

def start_scheduler():
    """Запуск планировщика для проверки лимитов каждые 5 минут"""
    scheduler = AsyncIOScheduler()
    
    # Запускаем проверку каждые 5 минут
    scheduler.add_job(
        check_limits_task,
        trigger="interval",
        minutes=5,
        id="check_limits",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Планировщик запущен. Проверка лимитов каждые 5 минут")
    
    return scheduler

