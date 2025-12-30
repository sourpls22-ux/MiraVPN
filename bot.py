import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID, SERVER_IP
from marzban_api import MarzbanAPI

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
marzban = MarzbanAPI()

class CreateKeyStates(StatesGroup):
    waiting_username = State()
    waiting_limit = State()
    waiting_expire = State()

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id == TELEGRAM_ADMIN_ID

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этому боту.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать ключ", callback_data="create_key")],
        [InlineKeyboardButton(text="📋 Мои ключи", callback_data="list_keys")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])
    
    await message.answer(
        "🔐 *VPN Bot - Управление ключами*\n\n"
        "Выберите действие:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "create_key")
async def create_key_callback(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📝 *Создание нового ключа*\n\n"
        "Отправьте имя пользователя для нового ключа.\n"
        "Или отправьте /cancel для отмены.",
        parse_mode="Markdown"
    )
    
    await state.set_state(CreateKeyStates.waiting_username)

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.")

@dp.message(CreateKeyStates.waiting_username)
async def process_username(message: types.Message, state: FSMContext):
    username = message.text.strip()
    
    # Проверяем, что имя не пустое
    if not username:
        await message.answer("❌ Имя пользователя не может быть пустым. Попробуйте еще раз.")
        return
    
    await state.update_data(username=username)
    await message.answer(
        f"✅ Имя пользователя: `{username}`\n\n"
        "Отправьте лимит трафика в GB (или 0 для безлимита):\n"
        "Или отправьте /skip для значения по умолчанию (100 GB)",
        parse_mode="Markdown"
    )
    await state.set_state(CreateKeyStates.waiting_limit)

@dp.message(Command("skip"))
async def cmd_skip(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == CreateKeyStates.waiting_limit:
        await state.update_data(data_limit=100)
        await message.answer(
            "✅ Лимит: 100 GB (по умолчанию)\n\n"
            "Отправьте срок действия в днях (или 0 для бессрочного):\n"
            "Или отправьте /skip для значения по умолчанию (30 дней)"
        )
        await state.set_state(CreateKeyStates.waiting_expire)
    elif current_state == CreateKeyStates.waiting_expire:
        await state.update_data(expire_days=30)
        data = await state.get_data()
        await create_user_final(message, data)
        await state.clear()

@dp.message(CreateKeyStates.waiting_limit)
async def process_limit(message: types.Message, state: FSMContext):
    try:
        limit = float(message.text.strip())
        if limit < 0:
            raise ValueError
        await state.update_data(data_limit=limit)
        await message.answer(
            f"✅ Лимит: {limit} GB\n\n"
            "Отправьте срок действия в днях (или 0 для бессрочного):\n"
            "Или отправьте /skip для значения по умолчанию (30 дней)"
        )
        await state.set_state(CreateKeyStates.waiting_expire)
    except ValueError:
        await message.answer("❌ Неверный формат. Отправьте число (например: 100 или 0)")

@dp.message(CreateKeyStates.waiting_expire)
async def process_expire(message: types.Message, state: FSMContext):
    try:
        expire = int(message.text.strip())
        if expire < 0:
            raise ValueError
        await state.update_data(expire_days=expire)
        data = await state.get_data()
        await create_user_final(message, data)
        await state.clear()
    except ValueError:
        await message.answer("❌ Неверный формат. Отправьте число дней (например: 30 или 0)")

async def create_user_final(message: types.Message, data: dict):
    username = data.get("username")
    data_limit = data.get("data_limit", 100)
    expire_days = data.get("expire_days", 30)
    
    await message.answer("⏳ Создаю ключ...")
    
    user_data = await marzban.create_user(
        username=username,
        data_limit_gb=data_limit if data_limit > 0 else None,
        expire_days=expire_days if expire_days > 0 else None
    )
    
    if user_data:
        # Получаем конфигурацию
        config = await marzban.get_user_config(username)
        
        if config:
            limit_text = f"{data_limit} GB" if data_limit > 0 else "Безлимит"
            expire_text = f"{expire_days} дней" if expire_days > 0 else "Бессрочно"
            
            await message.answer(
                f"✅ *Ключ создан успешно!*\n\n"
                f"👤 Пользователь: `{username}`\n"
                f"📊 Лимит: {limit_text}\n"
                f"⏰ Срок действия: {expire_text}\n\n"
                f"📥 *Конфигурация:*\n"
                f"```\n{config}\n```",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"✅ Пользователь создан: `{username}`\n"
                f"Но не удалось получить конфигурацию. Попробуйте /config {username}",
                parse_mode="Markdown"
            )
    else:
        await message.answer("❌ Ошибка при создании ключа. Возможно, пользователь уже существует.")

@dp.callback_query(F.data == "list_keys")
async def list_keys_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.answer("Загрузка...")
    
    users = await marzban.get_users()
    
    if users and users.get("users"):
        text = "📋 *Список ключей:*\n\n"
        keyboard_buttons = []
        
        for user in users["users"][:15]:  # Показываем первые 15
            username = user.get("username", "N/A")
            status = user.get("status", "unknown")
            used = user.get("used_traffic", 0) / (1024**3)  # GB
            limit = user.get("data_limit", 0) / (1024**3) if user.get("data_limit") else "∞"
            
            status_emoji = {
                "active": "✅",
                "expired": "⏰",
                "limited": "📊",
                "disabled": "❌"
            }.get(status, "❓")
            
            text += f"{status_emoji} `{username}`\n"
            text += f"   Статус: {status}\n"
            text += f"   Использовано: {used:.2f} GB / {limit} GB\n\n"
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"📥 {username}",
                    callback_data=f"get_config_{username}"
                ),
                InlineKeyboardButton(
                    text=f"🗑️",
                    callback_data=f"delete_user_{username}"
                )
            ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await callback.message.edit_text("📭 Ключей пока нет.")

@dp.callback_query(F.data.startswith("get_config_"))
async def get_config_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    username = callback.data.replace("get_config_", "")
    config = await marzban.get_user_config(username)
    
    if config:
        await callback.message.answer(
            f"📥 *Конфигурация для {username}:*\n\n"
            f"```\n{config}\n```",
            parse_mode="Markdown"
        )
        await callback.answer("✅ Конфигурация отправлена")
    else:
        await callback.answer("❌ Не удалось получить конфигурацию", show_alert=True)

@dp.callback_query(F.data.startswith("delete_user_"))
async def delete_user_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    username = callback.data.replace("delete_user_", "")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{username}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="list_keys")
        ]
    ])
    
    await callback.message.edit_text(
        f"⚠️ *Подтверждение удаления*\n\n"
        f"Вы уверены, что хотите удалить ключ `{username}`?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    username = callback.data.replace("confirm_delete_", "")
    result = await marzban.delete_user(username)
    
    if result:
        await callback.message.edit_text(f"✅ Ключ `{username}` успешно удален.", parse_mode="Markdown")
        await callback.answer("✅ Удалено")
    else:
        await callback.answer("❌ Ошибка при удалении", show_alert=True)

@dp.callback_query(F.data == "help")
async def help_callback(callback: types.CallbackQuery):
    help_text = (
        "ℹ️ *Помощь*\n\n"
        "*Команды:*\n"
        "`/start` - Главное меню\n"
        "`/create <username>` - Быстрое создание ключа\n"
        "`/list` - Список всех ключей\n"
        "`/config <username>` - Получить конфигурацию\n"
        "`/delete <username>` - Удалить ключ\n"
        "`/stats <username>` - Статистика пользователя\n"
        "`/cancel` - Отменить текущую операцию\n\n"
        "Все ключи создаются с протоколом *VLESS + Reality*\n"
        "для обхода блокировок в России."
    )
    await callback.message.edit_text(help_text, parse_mode="Markdown")

@dp.message(Command("create"))
async def cmd_create(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: /create <username>")
        return
    
    username = args[0]
    await message.answer("⏳ Создаю ключ с настройками по умолчанию...")
    
    user_data = await marzban.create_user(username, data_limit_gb=100, expire_days=30)
    
    if user_data:
        config = await marzban.get_user_config(username)
        if config:
            await message.answer(
                f"✅ *Ключ создан!*\n\n"
                f"👤 Пользователь: `{username}`\n"
                f"📊 Лимит: 100 GB\n"
                f"⏰ Срок: 30 дней\n\n"
                f"📥 *Конфигурация:*\n"
                f"```\n{config}\n```",
                parse_mode="Markdown"
            )
        else:
            await message.answer(f"✅ Пользователь создан: `{username}`", parse_mode="Markdown")
    else:
        await message.answer("❌ Ошибка при создании ключа. Возможно, пользователь уже существует.")

@dp.message(Command("list"))
async def cmd_list(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    users = await marzban.get_users()
    if users and users.get("users"):
        text = "📋 *Список ключей:*\n\n"
        for user in users["users"]:
            username = user.get("username", "N/A")
            status = user.get("status", "unknown")
            text += f"👤 `{username}` - {status}\n"
        await message.answer(text, parse_mode="Markdown")
    else:
        await message.answer("📭 Ключей нет.")

@dp.message(Command("delete"))
async def cmd_delete(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: /delete <username>")
        return
    
    username = args[0]
    result = await marzban.delete_user(username)
    
    if result:
        await message.answer(f"✅ Ключ `{username}` удален.", parse_mode="Markdown")
    else:
        await message.answer("❌ Ошибка при удалении.")

@dp.message(Command("config"))
async def cmd_config(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: /config <username>")
        return
    
    username = args[0]
    config = await marzban.get_user_config(username)
    
    if config:
        await message.answer(
            f"📥 *Конфигурация для {username}:*\n\n"
            f"```\n{config}\n```",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Не удалось получить конфигурацию.")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: /stats <username>")
        return
    
    username = args[0]
    user = await marzban.get_user(username)
    
    if user:
        used = user.get("used_traffic", 0) / (1024**3)  # GB
        limit = user.get("data_limit", 0) / (1024**3) if user.get("data_limit") else "∞"
        status = user.get("status", "unknown")
        expire = user.get("expire", 0)
        
        expire_text = "Бессрочно" if expire == 0 else f"до {expire}"
        
        await message.answer(
            f"📊 *Статистика пользователя {username}:*\n\n"
            f"Статус: {status}\n"
            f"Использовано: {used:.2f} GB / {limit} GB\n"
            f"Срок действия: {expire_text}",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Пользователь не найден.")

async def main():
    logging.info("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

