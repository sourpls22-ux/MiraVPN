import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
from config import (
    TELEGRAM_BOT_TOKEN, SERVER_IP,
    BASE_TARIFF_GB, BASE_TARIFF_DAYS, BASE_TARIFF_PRICE,
    EXTRA_GB_AMOUNT, EXTRA_GB_PRICE, FREE_MODE_SPEED_MBPS
)
from marzban_api import MarzbanAPI
from database import (
    init_db, get_user_by_telegram_id, create_user as db_create_user,
    update_user_tariff, enable_free_mode, add_transaction
)
from scheduler import start_scheduler, set_bot_and_marzban
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
marzban = MarzbanAPI()

async def create_vpn_key(message: types.Message, telegram_id: int):
    """Создание VPN ключа с автоматической генерацией username"""
    username = f"user_{telegram_id}"
    
    await message.answer("⏳ Создаю ваш VPN ключ...")
    
    # Создаем пользователя в Marzban
    user_data = await marzban.create_user(
        username=username,
        data_limit_gb=BASE_TARIFF_GB,
        expire_days=BASE_TARIFF_DAYS
    )
    
    if user_data:
        # Сохраняем в БД
        await db_create_user(telegram_id, username, "base")
        
        # Получаем конфигурацию
        config = await marzban.get_user_config(username)
        
        if config:
            await message.answer(
                f"✅ *VPN ключ создан успешно!*\n\n"
                f"👤 Пользователь: `{username}`\n"
                f"📦 Лимит: {BASE_TARIFF_GB} GB\n"
                f"⏰ Срок действия: {BASE_TARIFF_DAYS} дней\n\n"
                f"📥 *Ваша конфигурация:*\n"
                f"```\n{config}\n```\n\n"
                f"💡 *Как использовать:*\n"
                f"1. Скопируйте конфигурацию выше\n"
                f"2. Вставьте в ваш VPN клиент (v2rayNG, Nekoray и т.д.)",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"✅ Пользователь создан: `{username}`\n"
                f"Но не удалось получить конфигурацию. Попробуйте /start",
                parse_mode="Markdown"
            )
    else:
        await message.answer(
            "❌ Ошибка при создании ключа. Возможно, пользователь уже существует.\n"
            "Попробуйте /start для проверки статуса."
        )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    telegram_id = message.from_user.id
    user = await get_user_by_telegram_id(telegram_id)
    
    if user:
        # Пользователь уже существует - показываем статус
        username = user["username"]
        marzban_user = await marzban.get_user(username)
        
        if marzban_user:
            used_gb = marzban_user.get("used_traffic", 0) / (1024**3)
            limit_gb = marzban_user.get("data_limit", 0) / (1024**3) if marzban_user.get("data_limit") else "∞"
            status = marzban_user.get("status", "unknown")
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🌐 Открыть Web App",
                    web_app=WebAppInfo(url="https://app.miravpn.com")
                )],
                [InlineKeyboardButton(text="📊 Мой статус", callback_data="my_status")],
                [InlineKeyboardButton(text="📥 Получить конфигурацию", callback_data="get_my_config")],
                [InlineKeyboardButton(text="💰 Продлить (+100 ГБ)", callback_data="buy_extra")],
                [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
            ])
            
            status_emoji = {
                "active": "✅",
                "expired": "⏰",
                "limited": "📊",
                "disabled": "❌"
            }.get(status, "❓")
            
            await message.answer(
                f"🔐 *VPN Bot*\n\n"
                f"{status_emoji} Статус: {status}\n"
                f"📊 Использовано: {used_gb:.2f} GB / {limit_gb} GB\n\n"
                f"Выберите действие:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            # Пользователь в БД, но не в Marzban - создаем заново
            await create_vpn_key(message, telegram_id)
    else:
        # Новый пользователь - предлагаем купить VPN
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🌐 Открыть Web App",
                web_app=WebAppInfo(url="https://app.miravpn.com")
            )],
            [InlineKeyboardButton(
                text=f"💰 Купить VPN ({BASE_TARIFF_PRICE}₽)",
                callback_data="buy_vpn"
            )],
            [InlineKeyboardButton(text="ℹ️ О тарифах", callback_data="tariffs_info")]
        ])
        
        await message.answer(
            f"🔐 *Добро пожаловать в VPN Bot!*\n\n"
            f"*Базовый тариф:*\n"
            f"📦 {BASE_TARIFF_GB} ГБ трафика\n"
            f"⏰ Срок действия: {BASE_TARIFF_DAYS} дней\n"
            f"💰 Цена: {BASE_TARIFF_PRICE}₽\n\n"
            f"Протокол: *VLESS + Reality* для обхода блокировок в России.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

@dp.callback_query(F.data == "my_status")
async def my_status_callback(callback: types.CallbackQuery):
    """Показать статус пользователя"""
    telegram_id = callback.from_user.id
    user = await get_user_by_telegram_id(telegram_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    username = user["username"]
    marzban_user = await marzban.get_user(username)
    
    if marzban_user:
        used_gb = marzban_user.get("used_traffic", 0) / (1024**3)
        limit_gb = marzban_user.get("data_limit", 0) / (1024**3) if marzban_user.get("data_limit") else "∞"
        status = marzban_user.get("status", "unknown")
        expire = marzban_user.get("expire", 0)
        
        status_emoji = {
            "active": "✅",
            "expired": "⏰",
            "limited": "📊",
            "disabled": "❌"
        }.get(status, "❓")
        
        if expire:
            expire_date = datetime.fromtimestamp(expire)
            expire_text = expire_date.strftime("%d.%m.%Y %H:%M")
        else:
            expire_text = "Бессрочно"
        
        free_mode = user.get("free_mode_enabled", 0)
        mode_text = "🐌 Бесплатный режим (2 Мбит/с)" if free_mode else "🚀 Быстрый режим"
        
        await callback.message.edit_text(
            f"📊 *Ваш статус*\n\n"
            f"{status_emoji} Статус: {status}\n"
            f"{mode_text}\n"
            f"📦 Использовано: {used_gb:.2f} GB / {limit_gb} GB\n"
            f"⏰ Срок действия: {expire_text}\n\n"
            f"👤 Пользователь: `{username}`",
            parse_mode="Markdown"
        )
    else:
        await callback.answer("❌ Не удалось получить данные", show_alert=True)

@dp.callback_query(F.data == "get_my_config")
async def get_my_config_callback(callback: types.CallbackQuery):
    """Получить конфигурацию пользователя"""
    telegram_id = callback.from_user.id
    user = await get_user_by_telegram_id(telegram_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    username = user["username"]
    config = await marzban.get_user_config(username)
    
    if config:
        await callback.message.answer(
            f"📥 *Ваша конфигурация:*\n\n"
            f"```\n{config}\n```\n\n"
            f"💡 Скопируйте и вставьте в ваш VPN клиент.",
            parse_mode="Markdown"
        )
        await callback.answer("✅ Конфигурация отправлена")
    else:
        await callback.answer("❌ Не удалось получить конфигурацию", show_alert=True)

@dp.callback_query(F.data == "tariffs_info")
async def tariffs_info_callback(callback: types.CallbackQuery):
    """Информация о тарифах"""
    await callback.message.edit_text(
        f"💰 *Тарифы VPN*\n\n"
        f"*Базовый тариф:*\n"
        f"📦 {BASE_TARIFF_GB} ГБ трафика\n"
        f"⏰ Срок: {BASE_TARIFF_DAYS} дней\n"
        f"💰 Цена: {BASE_TARIFF_PRICE}₽\n"
        f"🚀 Скорость: без ограничений\n\n"
        f"*Дополнительный пакет:*\n"
        f"📦 +{EXTRA_GB_AMOUNT} ГБ\n"
        f"💰 Цена: {EXTRA_GB_PRICE}₽\n\n"
        f"*Бесплатный режим:*\n"
        f"🐌 Скорость: {FREE_MODE_SPEED_MBPS} Мбит/с\n"
        f"⏰ До конца месяца\n"
        f"💰 Бесплатно\n\n"
        f"Протокол: *VLESS + Reality*",
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "help")
async def help_callback(callback: types.CallbackQuery):
    help_text = (
        "ℹ️ *Помощь*\n\n"
        "*Команды:*\n"
        "`/start` - Главное меню\n\n"
        "*Возможности:*\n"
        "• Покупка VPN ключа с автоматической генерацией\n"
        "• Просмотр статуса и использования трафика\n"
        "• Покупка дополнительных 100 ГБ\n"
        "• Бесплатный режим при превышении лимита\n\n"
        "Все ключи создаются с протоколом *VLESS + Reality*\n"
        "для обхода блокировок в России."
    )
    await callback.message.edit_text(help_text, parse_mode="Markdown")

@dp.callback_query(F.data == "buy_vpn")
async def buy_vpn_callback(callback: types.CallbackQuery):
    """Обработчик покупки базового тарифа"""
    telegram_id = callback.from_user.id
    
    # Проверяем, не существует ли уже пользователь
    user = await get_user_by_telegram_id(telegram_id)
    if user:
        await callback.answer("✅ У вас уже есть VPN ключ! Используйте /start", show_alert=True)
        return
    
    await callback.answer("⏳ Создаю ваш VPN ключ...")
    
    # TODO: Здесь будет интеграция с платежной системой
    # Пока создаем ключ сразу (для тестирования)
    await create_vpn_key(callback.message, telegram_id)
    
    # Сохраняем транзакцию
    await add_transaction(telegram_id, BASE_TARIFF_PRICE, "base_tariff")

@dp.callback_query(F.data == "buy_extra")
async def buy_extra_callback(callback: types.CallbackQuery):
    """Обработчик покупки дополнительных 100 ГБ"""
    telegram_id = callback.from_user.id
    
    await callback.answer("⏳ Обрабатываю запрос...")
    
    # Получаем пользователя из БД
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден. Используйте /start для создания ключа.")
        return
    
    username = user["username"]
    
    # TODO: Здесь будет интеграция с платежной системой
    # Пока добавляем трафик сразу (для тестирования)
    result = await marzban.add_traffic(username, EXTRA_GB_AMOUNT)
    
    if result:
        # Сохраняем транзакцию
        await add_transaction(telegram_id, EXTRA_GB_PRICE, "extra_gb")
        
        # Получаем обновленную информацию
        updated_user = await marzban.get_user(username)
        if updated_user:
            limit_gb = updated_user.get("data_limit", 0) / (1024**3)
            
            await callback.message.edit_text(
                f"✅ *Дополнительные {EXTRA_GB_AMOUNT} ГБ добавлены!*\n\n"
                f"💰 Стоимость: {EXTRA_GB_PRICE}₽\n"
                f"📦 Новый лимит: {limit_gb:.0f} GB\n\n"
                f"⚠️ *Внимание:* Интеграция с платежной системой в разработке.\n"
                f"Для реальной оплаты обратитесь к администратору.",
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text("✅ Трафик добавлен!")
    else:
        await callback.message.edit_text("❌ Ошибка при добавлении трафика.")

@dp.callback_query(F.data.startswith("buy_extra_"))
async def buy_extra_from_notification_callback(callback: types.CallbackQuery):
    """Обработчик покупки дополнительных 100 ГБ из уведомления о превышении лимита"""
    telegram_id = int(callback.data.replace("buy_extra_", ""))
    
    # Проверяем, что это тот же пользователь
    if callback.from_user.id != telegram_id:
        await callback.answer("❌ Это не ваш запрос", show_alert=True)
        return
    
    # Перенаправляем на основной обработчик
    callback.data = "buy_extra"
    await buy_extra_callback(callback)

@dp.callback_query(F.data.startswith("enable_free_"))
async def enable_free_mode_callback(callback: types.CallbackQuery):
    """Обработчик включения бесплатного режима"""
    telegram_id = int(callback.data.replace("enable_free_", ""))
    
    # Проверяем, что это тот же пользователь
    if callback.from_user.id != telegram_id:
        await callback.answer("❌ Это не ваш запрос", show_alert=True)
        return
    
    await callback.answer("⏳ Включаю бесплатный режим...")
    
    # Получаем пользователя из БД
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден в базе данных.")
        return
    
    username = user["username"]
    
    # Переключаем на бесплатный режим (медленный inbound + сброс лимита)
    result = await marzban.switch_to_free_mode(username)
    
    if result:
        # Вычисляем дату до конца месяца
        now = datetime.now()
        if now.month == 12:
            end_of_month = datetime(now.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_of_month = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
        
        # Сохраняем в БД
        await enable_free_mode(telegram_id, end_of_month)
        await update_user_tariff(telegram_id, "free")
        
        # Получаем новую конфигурацию
        config = await marzban.get_user_config(username)
        
        await callback.message.edit_text(
            f"✅ *Бесплатный режим включен!*\n\n"
            f"🐌 Скорость: {FREE_MODE_SPEED_MBPS} Мбит/с\n"
            f"⏰ Действует до: {end_of_month.strftime('%d.%m.%Y')}\n\n"
            f"📥 *Новая конфигурация (медленный режим):*\n"
            f"```\n{config}\n```\n\n"
            f"💡 *Важно:* Обновите конфигурацию в вашем VPN клиенте!",
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при переключении на бесплатный режим.\n"
            "Обратитесь к администратору."
        )

async def main():
    logging.info("Инициализация базы данных...")
    await init_db()  # Создаем таблицы users и transactions
    
    # Инициализируем scheduler с ботом и Marzban API
    set_bot_and_marzban(bot, marzban)
    scheduler = start_scheduler()
    
    logging.info("Бот запущен...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())

