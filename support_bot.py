"""
Бот техподдержки для Outline VPN
Пересылает все сообщения от пользователей администратору
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

# Импортируем настройки из основного бота
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.settings import admin_tlg

# Получаем токен бота техподдержки из переменных окружения
SUPPORT_BOT_TOKEN = os.getenv("SUPPORT_BOT_TOKEN")

if not SUPPORT_BOT_TOKEN:
    raise RuntimeError(
        "Отсутствует переменная окружения SUPPORT_BOT_TOKEN. "
        "Добавьте её в .env или core/TEMP.env"
    )

# Проверяем наличие admin_tlg
if not admin_tlg:
    raise RuntimeError(
        "Отсутствует переменная окружения ADMIN_TLG. "
        "Добавьте её в .env или core/TEMP.env"
    )

# Преобразуем admin_tlg в int для использования
ADMIN_ID = int(admin_tlg)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=SUPPORT_BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Словарь для хранения сопоставления пользователей (для ответов администратора)
user_mapping = {}


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    welcome_text = (
        "👋 Здравствуйте!\n\n"
        "Это служба поддержки Outline Solutions.\n\n"
        "⚠️ <b>Важное уведомление:</b>\n"
        "Мы не предоставляем потребительские VPN-услуги. "
        "Outline Solutions — это B2B-платформа для организации частных сетей.\n\n"
        "Если у вас есть вопросы по работе сервиса для бизнеса "
        "(удаленный доступ к серверу, защита разработки), "
        "напишите ваш вопрос, и мы ответим в ближайшее время."
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)


@router.message(F.text)
async def forward_to_admin(message: Message):
    """Пересылка сообщений от пользователей администратору"""
    user_id = message.from_user.id
    username = message.from_user.username or "нет username"
    full_name = message.from_user.full_name or "Неизвестный пользователь"
    
    # Сохраняем информацию о пользователе для возможности ответа
    user_mapping[user_id] = {
        'username': username,
        'full_name': full_name
    }
    
    # Формируем сообщение для администратора
    admin_message = (
        f"📩 <b>Новое сообщение в техподдержку</b>\n\n"
        f"👤 <b>От:</b> {full_name}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"📧 <b>Username:</b> @{username}\n\n"
        f"💬 <b>Сообщение:</b>\n{message.text}\n\n"
        f"<i>Чтобы ответить, используйте команду:</i>\n"
        f"<code>/reply {user_id} ваш_ответ</code>"
    )
    
    try:
        # Отправляем сообщение администратору
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_message,
            parse_mode=ParseMode.HTML
        )
        
        # Подтверждение пользователю
        await message.answer(
            "✅ Ваше сообщение получено и передано в службу поддержки. "
            "Мы ответим в ближайшее время.",
            parse_mode=ParseMode.HTML
        )
        
        logger.info(f"Сообщение от пользователя {user_id} переслано администратору")
        
    except Exception as e:
        logger.error(f"Ошибка при пересылке сообщения: {e}")
        await message.answer(
            "❌ Произошла ошибка при отправке сообщения. "
            "Пожалуйста, попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


@router.message(Command("reply"))
async def reply_to_user(message: Message):
    """Ответ администратора пользователю"""
    # Проверяем, что это администратор
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет доступа к этой команде")
        return
    
    # Парсим команду: /reply USER_ID текст ответа
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.answer(
                "Использование: /reply USER_ID текст_ответа\n"
                "Пример: /reply 123456789 Спасибо за обращение!"
            )
            return
        
        user_id = int(parts[1])
        reply_text = parts[2]
        
        # Отправляем ответ пользователю
        await bot.send_message(
            chat_id=user_id,
            text=f"📬 <b>Ответ от службы поддержки:</b>\n\n{reply_text}",
            parse_mode=ParseMode.HTML
        )
        
        # Подтверждение администратору
        user_info = user_mapping.get(user_id, {})
        username = user_info.get('username', 'неизвестно')
        full_name = user_info.get('full_name', 'Неизвестный пользователь')
        
        await message.answer(
            f"✅ Ответ отправлен пользователю:\n"
            f"👤 {full_name} (@{username})\n"
            f"🆔 ID: {user_id}",
            parse_mode=ParseMode.HTML
        )
        
        logger.info(f"Администратор ответил пользователю {user_id}")
        
    except ValueError:
        await message.answer("Ошибка: USER_ID должен быть числом")
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа: {e}")
        await message.answer(f"❌ Ошибка при отправке ответа: {str(e)}")


@router.message(F.photo | F.video | F.document | F.voice | F.sticker)
async def handle_media(message: Message):
    """Обработка медиафайлов - уведомление о поддержке только текста"""
    await message.answer(
        "⚠️ В настоящее время поддерживаются только текстовые сообщения. "
        "Пожалуйста, опишите ваш вопрос текстом.",
        parse_mode=ParseMode.HTML
    )


async def main():
    """Главная функция запуска бота"""
    # Регистрируем роутер
    dp.include_router(router)
    
    logger.info("Бот техподдержки запущен")
    
    # Запускаем polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
