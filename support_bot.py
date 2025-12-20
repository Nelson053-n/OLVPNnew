"""
Бот техподдержки для Outline VPN
Пересылает все сообщения от пользователей администратору
Администратор может отвечать на сообщения пользователей
"""
import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Импортируем настройки из основного бота
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Загружаем переменные окружения
load_dotenv()
if not os.getenv("SUPPORT_BOT_TOKEN"):
    temp_env_path = os.path.join(os.path.dirname(__file__), "core", "TEMP.env")
    if os.path.exists(temp_env_path):
        load_dotenv(temp_env_path)

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

# Словарь для хранения сопоставления пользователей и их последних сообщений
# Структура: {user_id: {'username': ..., 'full_name': ..., 'last_message_id': ..., 'messages': [...]}}
user_mapping = {}
# Словарь для связи сообщений администратора с пользователями
# Структура: {admin_message_id: user_id}
admin_messages = {}
# История сообщений для каждого пользователя
# Структура: {user_id: [{'text': ..., 'timestamp': ..., 'from': 'user'/'admin'}, ...]}
user_history = {}


async def send_notification_to_admin(text: str):
    """Отправка уведомления администратору"""
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=text,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Уведомление отправлено администратору: {text[:50]}...")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {e}")


def add_to_history(user_id: int, text: str, from_who: str):
    """Добавление сообщения в историю"""
    if user_id not in user_history:
        user_history[user_id] = []
    
    user_history[user_id].append({
        'text': text,
        'timestamp': datetime.now(),
        'from': from_who  # 'user' или 'admin'
    })
    
    # Ограничиваем историю последними 50 сообщениями
    if len(user_history[user_id]) > 50:
        user_history[user_id] = user_history[user_id][-50:]


def create_admin_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Создание клавиатуры с кнопками для администратора"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="↩️ Ответить",
                callback_data=f"reply_{user_id}"
            ),
            InlineKeyboardButton(
                text="📜 История",
                callback_data=f"history_{user_id}"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


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
    # Игнорируем сообщения от администратора (они обрабатываются отдельно)
    if message.from_user.id == ADMIN_ID:
        # Проверяем, является ли это ответом на сообщение пользователя
        if message.reply_to_message and message.reply_to_message.message_id in admin_messages:
            user_id = admin_messages[message.reply_to_message.message_id]
            
            # Добавляем ответ в историю
            add_to_history(user_id, message.text, 'admin')
            
            # Отправляем ответ пользователю
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"📬 <b>Ответ от службы поддержки:</b>\n\n{message.text}",
                    parse_mode=ParseMode.HTML
                )
                
                # Подтверждение администратору
                user_info = user_mapping.get(user_id, {})
                username = user_info.get('username', 'неизвестно')
                full_name = user_info.get('full_name', 'Неизвестный пользователь')
                
                await message.answer(
                    f"✅ Ответ отправлен пользователю:\n"
                    f"👤 {full_name} (@{username})\n"
                    f"🆔 ID: <code>{user_id}</code>",
                    parse_mode=ParseMode.HTML
                )
                
                logger.info(f"Администратор ответил пользователю {user_id}")
                
            except Exception as e:
                logger.error(f"Ошибка при отправке ответа пользователю: {e}")
                await message.answer(
                    f"❌ Ошибка при отправке ответа: {str(e)}",
                    parse_mode=ParseMode.HTML
                )
        else:
            # Обычное сообщение от администратора (не ответ)
            await message.answer(
                "ℹ️ Чтобы ответить пользователю, используйте Reply на его сообщение\n"
                "или команду /reply USER_ID текст",
                parse_mode=ParseMode.HTML
            )
        return
    
    user_id = message.from_user.id
    username = message.from_user.username or "нет username"
    full_name = message.from_user.full_name or "Неизвестный пользователь"
    
    # Сохраняем информацию о пользователе для возможности ответа
    user_mapping[user_id] = {
        'username': username,
        'full_name': full_name
    }
    
    # Добавляем сообщение в историю
    add_to_history(user_id, message.text, 'user')
    
    # Формируем сообщение для администратора
    admin_message_text = (
        f"📩 <b>Новое сообщение в техподдержку</b>\n\n"
        f"👤 <b>От:</b> {full_name}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"📧 <b>Username:</b> @{username}\n\n"
        f"💬 <b>Сообщение:</b>\n{message.text}"
    )
    
    try:
        # Создаём клавиатуру с кнопками
        keyboard = create_admin_keyboard(user_id)
        
        # Отправляем сообщение администратору с кнопками
        sent_message = await bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_message_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
        # Сохраняем связь между сообщением администратора и пользователем
        admin_messages[sent_message.message_id] = user_id
        user_mapping[user_id]['last_message_id'] = sent_message.message_id
        
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
        
        # Добавляем ответ в историю
        add_to_history(user_id, reply_text, 'admin')
        
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


@router.callback_query(F.data.startswith("reply_"))
async def callback_reply(callback: CallbackQuery):
    """Обработка нажатия кнопки 'Ответить'"""
    user_id = int(callback.data.split("_")[1])
    
    user_info = user_mapping.get(user_id, {})
    username = user_info.get('username', 'неизвестно')
    full_name = user_info.get('full_name', 'Неизвестный пользователь')
    
    await callback.answer()
    await callback.message.answer(
        f"✍️ <b>Ответ пользователю:</b>\n"
        f"👤 {full_name} (@{username})\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"Используйте команду:\n"
        f"<code>/reply {user_id} ваш_текст</code>\n\n"
        f"Или используйте Reply на исходное сообщение",
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("history_"))
async def callback_history(callback: CallbackQuery):
    """Обработка нажатия кнопки 'История'"""
    user_id = int(callback.data.split("_")[1])
    
    user_info = user_mapping.get(user_id, {})
    username = user_info.get('username', 'неизвестно')
    full_name = user_info.get('full_name', 'Неизвестный пользователь')
    
    history = user_history.get(user_id, [])
    
    if not history:
        await callback.answer("История сообщений пуста", show_alert=True)
        return
    
    # Формируем текст истории
    history_text = f"📜 <b>История диалога</b>\n\n"
    history_text += f"👤 <b>Пользователь:</b> {full_name} (@{username})\n"
    history_text += f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
    history_text += f"📊 <b>Всего сообщений:</b> {len(history)}\n\n"
    history_text += "─" * 30 + "\n\n"
    
    # Берём последние 10 сообщений
    recent_history = history[-10:]
    
    for idx, msg in enumerate(recent_history, 1):
        timestamp = msg['timestamp'].strftime("%d.%m.%Y %H:%M")
        from_who = "👤 Пользователь" if msg['from'] == 'user' else "👨‍💼 Поддержка"
        text = msg['text']
        
        # Обрезаем длинные сообщения
        if len(text) > 100:
            text = text[:97] + "..."
        
        history_text += f"<b>{idx}. {from_who}</b> ({timestamp})\n"
        history_text += f"{text}\n\n"
    
    if len(history) > 10:
        history_text += f"<i>Показаны последние 10 из {len(history)} сообщений</i>"
    
    await callback.answer()
    await callback.message.answer(
        history_text,
        parse_mode=ParseMode.HTML
    )


async def main():
    """Главная функция запуска бота"""
    # Регистрируем роутер
    dp.include_router(router)
    
    logger.info("Бот техподдержки запущен")
    
    # Отправляем уведомление администратору о запуске
    try:
        bot_info = await bot.get_me()
        startup_message = (
            f"🟢 <b>Бот техподдержки запущен</b>\n\n"
            f"🤖 <b>Бот:</b> @{bot_info.username}\n"
            f"🆔 <b>Bot ID:</b> <code>{bot_info.id}</code>\n"
            f"✅ <b>Статус:</b> Токен получен успешно\n"
            f"🔄 <b>Состояние:</b> Готов к приёму сообщений\n\n"
            f"<i>Все сообщения от пользователей будут пересылаться вам.\n"
            f"Отвечайте с помощью Reply на сообщения.</i>"
        )
        await send_notification_to_admin(startup_message)
    except Exception as e:
        error_message = (
            f"🔴 <b>Ошибка при запуске бота техподдержки</b>\n\n"
            f"❌ <b>Ошибка:</b> {str(e)}\n"
            f"⚠️ <b>Возможные причины:</b>\n"
            f"• Неверный токен SUPPORT_BOT_TOKEN\n"
            f"• Проблемы с подключением к Telegram API\n"
            f"• Токен заблокирован или отозван\n\n"
            f"<i>Проверьте настройки в .env файле</i>"
        )
        logger.error(f"Ошибка при получении информации о боте: {e}")
        # Попробуем отправить уведомление об ошибке
        try:
            await send_notification_to_admin(error_message)
        except:
            pass
        raise
    
    # Запускаем polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Отправляем уведомление об остановке бота
        try:
            shutdown_message = (
                f"🔴 <b>Бот техподдержки остановлен</b>\n\n"
                f"⏹️ <b>Статус:</b> Бот прекратил работу\n"
                f"🕐 <b>Время остановки:</b> {asyncio.get_event_loop().time()}\n\n"
                f"<i>Сообщения от пользователей не будут приниматься</i>"
            )
            await send_notification_to_admin(shutdown_message)
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об остановке: {e}")
        
        await bot.session.close()
        logger.info("Бот техподдержки остановлен")


if __name__ == "__main__":
    try:
        logger.info("=" * 50)
        logger.info("Запуск бота техподдержки...")
        logger.info(f"Токен бота: {'✓ Установлен' if SUPPORT_BOT_TOKEN else '✗ Отсутствует'}")
        logger.info(f"ID администратора: {ADMIN_ID}")
        logger.info("=" * 50)
        
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем (Ctrl+C)")
    except RuntimeError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        print(f"\n❌ ОШИБКА КОНФИГУРАЦИИ:\n{e}\n")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА:\n{e}\n")
