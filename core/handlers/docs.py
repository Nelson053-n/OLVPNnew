"""
Обработчик отображения документации
"""
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from core.utils.create_view import create_answer_from_html
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


async def docs_handler(callback: CallbackQuery) -> None:
    """
    Обработчик для отображения документации.
    Вызывается при нажатии на кнопку "📄 Документация"
    
    :param callback: CallbackQuery - объект callback запроса
    """
    try:
        # Загружаем шаблон документации
        content = await create_answer_from_html(name_temp='/docs')
        
        # Создаем клавиатуру с кнопкой "Назад"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text='🔙 Назад в меню', callback_data='back_start')
        
        # Отправляем документацию
        await callback.message.edit_text(
            text=content,
            reply_markup=keyboard.as_markup(),
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.log('error', f'Error in docs_handler: {e}')
        await callback.answer('❌ Ошибка загрузки документации', show_alert=True)


async def command_docs(message: Message) -> None:
    """
    Обработчик команды /docs
    
    :param message: Message - объект сообщения
    """
    try:
        # Загружаем шаблон документации
        content = await create_answer_from_html(name_temp='/docs')
        
        # Создаем клавиатуру с кнопкой "Назад"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text='🔙 Назад в меню', callback_data='back_start')
        
        # Отправляем документацию
        await message.answer(
            text=content,
            reply_markup=keyboard.as_markup(),
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.log('error', f'Error in command_docs: {e}')
        await message.answer('❌ Ошибка загрузки документации')
