"""
Система поддержки - создание и управление тикетами
"""
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import traceback
from datetime import datetime

from core.sql.function_db_user_vpn.support_tickets import (
    create_ticket,
    get_ticket,
    get_open_tickets,
    update_ticket_status,
    add_admin_response,
    get_ticket_stats,
    get_user_tickets,
)
from core.sql.function_db_user_vpn.users_vpn import get_user_data_from_table_users
from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


class SupportStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_category = State()
    waiting_for_description = State()
    waiting_for_admin_response = State()


def fmt(dt: datetime) -> str:
    if not dt:
        return "Unknown"
    return dt.strftime('%d.%m.%Y - %H:%M')


async def command_support(message: Message, state: FSMContext) -> None:
    """
    Команда /support - создание тикета поддержки
    """
    try:
        account = message.from_user.id

        if admin_tlg and account == int(admin_tlg):
            from core.handlers.admin_keys import create_admin_support_keyboard
            await message.answer(
                text="<b>🆘 Раздел: Поддержка</b>\n\nВыберите действие:",
                parse_mode='HTML',
                reply_markup=create_admin_support_keyboard(),
            )
            return
        
        # Проверяем что пользователь есть в БД
        user = await get_user_data_from_table_users(account=account)
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы в системе\n"
                "Используйте /start для начала работы",
                parse_mode=None
            )
            return
        
        text = (
            "✉️ <b>Служба поддержки</b>\n\n"
            "Опишите вашу проблему и мы вам поможем.\n\n"
            "Сначала укажите <b>название проблемы</b> (одна строка):"
        )
        
        await message.answer(text)
        await state.set_state(SupportStates.waiting_for_title)
        
    except Exception as e:
        logger.log('error', f'command_support error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при создании тикета", parse_mode=None)


async def support_title_handler(message: Message, state: FSMContext) -> None:
    """Получаем название проблемы"""
    try:
        title = message.text.strip()
        
        if len(title) < 5 or len(title) > 200:
            await message.answer(
                "⚠️ Название должно быть от 5 до 200 символов\n"
                "Попробуйте ещё раз:",
                parse_mode=None
            )
            return
        
        await state.update_data(title=title)
        
        # Выбор категории
        builder = InlineKeyboardBuilder()
        categories = [
            ("🔧 Техническая проблема", "cat_technical"),
            ("💰 Вопрос по платежу", "cat_payment"),
            ("🗝️ Проблема с ключом", "cat_key"),
            ("📊 Требование данных", "cat_data"),
            ("❓ Другое", "cat_other"),
        ]
        
        for label, callback in categories:
            builder.button(text=label, callback_data=callback)
        
        builder.adjust(1)
        
        await message.answer(
            "Выберите <b>категорию проблемы</b>:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(SupportStates.waiting_for_category)
        
    except Exception as e:
        logger.log('error', f'support_title_handler error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при обработке названия", parse_mode=None)


async def support_category_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Получаем категорию проблемы"""
    try:
        category_map = {
            'cat_technical': 'Техническая проблема',
            'cat_payment': 'Проблема с платежом',
            'cat_key': 'Проблема с ключом',
            'cat_data': 'Требование данных',
            'cat_other': 'Другое',
        }
        
        category = category_map.get(callback.data, 'Другое')
        await state.update_data(category=category)
        
        # Редактируем сообщение
        await callback.message.edit_text(
            "📝 Теперь опишите <b>подробно вашу проблему</b>:\n\n"
            "(Приложите как можно больше информации для быстрого решения)"
        )
        await callback.answer()
        await state.set_state(SupportStates.waiting_for_description)
        
    except Exception as e:
        logger.log('error', f'support_category_handler error: {e}\n{traceback.format_exc()}')
        await callback.message.answer("❌ Ошибка при выборе категории", parse_mode=None)
        await callback.answer()


async def support_description_handler(message: Message, state: FSMContext) -> None:
    """Получаем описание и создаём тикет"""
    try:
        description = message.text.strip()
        
        if len(description) < 10 or len(description) > 2000:
            await message.answer(
                "⚠️ Описание должно быть от 10 до 2000 символов\n"
                "Попробуйте ещё раз:",
                parse_mode=None
            )
            return
        
        # Получаем данные из state
        data = await state.get_data()
        title = data.get('title', 'Без названия')
        category = data.get('category', 'Другое')
        account = message.from_user.id
        
        # Создаём тикет
        ticket_id = await create_ticket(
            account=account,
            title=title,
            category=category,
            description=description,
            priority='normal'
        )
        
        if not ticket_id:
            await message.answer("❌ Ошибка при создании тикета", parse_mode=None)
            await state.clear()
            return
        
        # Отправляем ответ пользователю
        text = (
            f"✅ <b>Тикет создан</b>\n\n"
            f"🎫 Номер тикета: <code>#{ticket_id}</code>\n"
            f"<b>Название:</b> {title}\n"
            f"<b>Категория:</b> {category}\n"
            f"<b>Статус:</b> 🔵 Новый\n\n"
            f"Администратор рассмотрит вашу проблему в ближайшее время.\n"
            f"Вы сможете получать обновления по статусу тикета."
        )
        
        await message.answer(text)
        
        # Уведомляем администратора
        if admin_tlg:
            try:
                admin_text = (
                    f"🆕 <b>Новый тикет поддержки</b>\n\n"
                    f"🎫 ID: #{ticket_id}\n"
                    f"👤 От пользователя: {message.from_user.first_name or 'User'} (ID: {account})\n"
                    f"<b>Название:</b> {title}\n"
                    f"<b>Категория:</b> {category}\n\n"
                    f"<b>Описание:</b>\n{description}"
                )
                from core.bot import bot
                await bot.send_message(chat_id=int(admin_tlg), text=admin_text)
            except Exception as e:
                logger.log('warning', f'Failed to notify admin: {e}')
        
        await state.clear()
        
    except Exception as e:
        logger.log('error', f'support_description_handler error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при создании тикета", parse_mode=None)
        await state.clear()


async def command_support_my_tickets(message: Message) -> None:
    """
    Команда /mytickets - просмотр своих тикетов
    """
    try:
        account = message.from_user.id
        
        tickets = await get_user_tickets(account=account)
        
        if not tickets:
            await message.answer(
                "📭 У вас нет тикетов поддержки\n\n"
                "Используйте /support чтобы создать новый тикет",
                parse_mode=None
            )
            return
        
        text = f"<b>📋 Ваши тикеты ({len(tickets)})</b>\n\n"
        
        status_emoji = {
            'open': '🔵',
            'in_progress': '🟡',
            'resolved': '🟢',
            'closed': '⚫',
        }
        
        for ticket in tickets:
            status = ticket.status or 'open'
            emoji = status_emoji.get(status, '❓')
            text += (
                f"{emoji} <b>#{ticket.id}</b> - {ticket.title}\n"
                f"   Категория: {ticket.category}\n"
                f"   Создан: {fmt(ticket.created_at)}\n\n"
            )
        
        await message.answer(text)
        
    except Exception as e:
        logger.log('error', f'command_support_my_tickets error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при получении тикетов", parse_mode=None)


async def admin_support_queue(message: Message) -> None:
    """
    Команда администратора для просмотра очереди тикетов
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return
        
        tickets = await get_open_tickets()
        
        if not tickets:
            await message.answer(
                "✅ Нет открытых тикетов\n"
                "Все проблемы решены!",
                parse_mode=None
            )
            return
        
        text = f"<b>📞 Очередь поддержки ({len(tickets)} открытых)</b>\n\n"
        
        priority_emoji = {
            'critical': '🔴',
            'high': '🟠',
            'normal': '🟡',
            'low': '🟢',
        }
        
        for ticket in tickets:
            priority = ticket.priority or 'normal'
            emoji = priority_emoji.get(priority, '?')
            user_name = ticket.account_name or f"User {ticket.account}"
            
            text += (
                f"{emoji} <b>#{ticket.id}</b> - {ticket.title}\n"
                f"   От: {user_name} (ID: {ticket.account})\n"
                f"   Категория: {ticket.category}\n"
                f"   Приоритет: {priority}\n"
                f"   Создан: {fmt(ticket.created_at)}\n\n"
            )
        
        await message.answer(text)
        
    except Exception as e:
        logger.log('error', f'admin_support_queue error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при получении очереди", parse_mode=None)


async def admin_support_stats(message: Message) -> None:
    """
    Команда администратора для просмотра статистики поддержки
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return
        
        stats = await get_ticket_stats()
        
        text = "<b>📊 Статистика тикетов</b>\n\n"
        text += f"🔵 Открытых: {stats.get('open', 0)}\n"
        text += f"🟡 В работе: {stats.get('in_progress', 0)}\n"
        text += f"🟢 Решённых: {stats.get('resolved', 0)}\n"
        text += f"⚫ Закрытых: {stats.get('closed', 0)}\n\n"
        
        total = sum(stats.values())
        text += f"📈 Всего: {total}\n"
        
        if total > 0:
            open_count = stats.get('open', 0)
            percentage = (open_count / total) * 100
            text += f"⏳ Ожидание ответа: {percentage:.1f}%"
        
        await message.answer(text)
        
    except Exception as e:
        logger.log('error', f'admin_support_stats error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при получении статистики", parse_mode=None)
