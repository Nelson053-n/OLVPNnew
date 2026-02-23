"""
Хендлер для управления тестовыми данными.
Создание, удаление и просмотр тестовых данных.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from core.settings import admin_tlg
from core.sql.function_db_user_vpn.users_vpn import get_all_user_keys

router = Router()

# Проверяем наличие администратора
ADMIN_ID = int(admin_tlg) if admin_tlg else None


def create_test_data_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру для управления тестовыми данными"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="🧪 Создать тестовые данные",
                callback_data="test_data_create"
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑️ Удалить тестовые данные",
                callback_data="test_data_delete"
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Список тестовых данных",
                callback_data="test_data_list"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="test_data_back"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Command("testdata"))
async def cmd_testdata(message: Message):
    """
    Команда /testdata - меню управления тестовыми данными.
    Доступно только администратору.
    """
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к этой команде")
        return

    text = (
        "🧪 <b>Управление тестовыми данными</b>\n\n"
        "Выберите действие:\n\n"
        "<i>Тестовые данные используются для проверки функционала бота</i>"
    )

    keyboard = create_test_data_keyboard()

    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


@router.callback_query(F.data == "test_data_create")
async def callback_test_data_create(callback: CallbackQuery):
    """Создание тестовых данных"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer("⏳ Создание тестовых данных...")

    try:
        from core.handlers.seed_test_data import command_seed
        await command_seed(callback.message)
        await callback.answer("✅ Тестовые данные созданы")
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "test_data_delete")
async def callback_test_data_delete(callback: CallbackQuery):
    """Удаление тестовых данных"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer("⏳ Удаление тестовых данных...")

    try:
        from core.handlers.unseed_test_data import command_unseed
        await command_unseed(callback.message)
        await callback.answer("✅ Тестовые данные удалены")
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "test_data_list")
async def callback_test_data_list(callback: CallbackQuery):
    """Список тестовых данных"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()

    try:
        keys = await get_all_user_keys()
        test_keys = [k for k in keys if 'test' in str(k.account).lower() or k.promo]

        if not test_keys:
            await callback.message.answer("📊 Тестовые данные не найдены")
            return

        text = f"📊 <b>Тестовые данные</b>\n\nНайдено записей: {len(test_keys)}\n\n"
        for key in test_keys[:20]:  # Показываем первые 20
            text += f"• User: {key.account}, Server: {key.region_server}, Promo: {key.promo}\n"

        if len(test_keys) > 20:
            text += f"\n<i>... и ещё {len(test_keys) - 20}</i>"

        await callback.message.answer(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "test_data_back")
async def callback_test_data_back(callback: CallbackQuery):
    """Возврат назад"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer("🔙 Возврат в главное меню...")
