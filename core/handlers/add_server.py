from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import json
import traceback

from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()

# Словарь флагов стран (emoji)
COUNTRY_FLAGS = {
    'nederland': '🇳🇱',
    'netherlands': '🇳🇱',
    'germany': '🇩🇪',
    'france': '🇫🇷',
    'spain': '🇪🇸',
    'italy': '🇮🇹',
    'poland': '🇵🇱',
    'uk': '🇬🇧',
    'usa': '🇺🇸',
    'canada': '🇨🇦',
    'japan': '🇯🇵',
    'singapore': '🇸🇬',
    'australia': '🇦🇺',
    'brazil': '🇧🇷',
    'india': '🇮🇳',
    'turkey': '🇹🇷',
    'uae': '🇦🇪',
    'sweden': '🇸🇪',
    'norway': '🇳🇴',
    'finland': '🇫🇮',
    'switzerland': '🇨🇭',
    'austria': '🇦🇹',
    'belgium': '🇧🇪',
    'czech': '🇨🇿',
    'denmark': '🇩🇰',
    'ireland': '🇮🇪',
    'portugal': '🇵🇹',
    'romania': '🇷🇴',
    'ukraine': '🇺🇦',
}


class AddServerStates(StatesGroup):
    waiting_for_country = State()
    waiting_for_api_url = State()
    waiting_for_cert = State()


async def command_addserver(message: Message, state: FSMContext) -> None:
    """
    -- Админ-команда --
    /addserver
    Запускает процесс добавления нового Outline сервера.
    Пошагово запрашивает: страну, API URL, сертификат.
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
            return

        await state.set_state(AddServerStates.waiting_for_country)
        await message.answer(
            text=(
                '🌍 <b>Добавление нового Outline сервера</b>\n\n'
                'Шаг 1/3: Введите название страны на английском\n'
                '(например: germany, france, usa)\n\n'
                'Или отправьте /cancel для отмены'
            ),
            parse_mode='HTML'
        )
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_addserver error: {e}\n{tb}')
        await message.answer('❌ Ошибка при запуске команды', parse_mode=None)


async def process_country_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода названия страны"""
    try:
        if message.text == '/cancel':
            await state.clear()
            await message.answer('❌ Добавление сервера отменено', parse_mode=None)
            return

        country_name = message.text.strip().lower()
        
        # Проверяем, не существует ли уже сервер с таким именем
        config_file = 'core/api_s/outline/settings_api_outline.json'
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if country_name in config:
                await message.answer(
                    f'⚠️ Сервер "{country_name}" уже существует в конфигурации.\n'
                    'Используйте другое имя или отредактируйте файл вручную.',
                    parse_mode=None
                )
                return
        except FileNotFoundError:
            config = {}

        # Определяем флаг
        flag = COUNTRY_FLAGS.get(country_name, '🌐')
        
        # Сохраняем данные в состоянии
        await state.update_data(country_name=country_name, flag=flag)
        await state.set_state(AddServerStates.waiting_for_api_url)
        
        await message.answer(
            text=(
                f'✅ Страна: {flag} {country_name.title()}\n\n'
                'Шаг 2/3: Введите API URL сервера Outline\n'
                '(например: https://123.456.789.012:12345/aBcDeFgH)\n\n'
                'Или /cancel для отмены'
            ),
            parse_mode=None
        )
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'process_country_input error: {e}\n{tb}')
        await message.answer('❌ Ошибка при обработке названия страны', parse_mode=None)


async def process_api_url_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода API URL"""
    try:
        if message.text == '/cancel':
            await state.clear()
            await message.answer('❌ Добавление сервера отменено', parse_mode=None)
            return

        api_url = message.text.strip()
        
        # Простая валидация URL
        if not api_url.startswith('https://'):
            await message.answer(
                '⚠️ API URL должен начинаться с https://\n'
                'Попробуйте еще раз или отправьте /cancel',
                parse_mode=None
            )
            return

        # Сохраняем API URL
        await state.update_data(api_url=api_url)
        await state.set_state(AddServerStates.waiting_for_cert)
        
        data = await state.get_data()
        country_name = data.get('country_name', '')
        flag = data.get('flag', '🌐')
        
        await message.answer(
            text=(
                f'✅ Страна: {flag} {country_name.title()}\n'
                f'✅ API URL: {api_url}\n\n'
                'Шаг 3/3: Введите SHA256 сертификат\n'
                '(64-символьная строка шестнадцатеричных символов)\n\n'
                'Или /cancel для отмены'
            ),
            parse_mode=None
        )
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'process_api_url_input error: {e}\n{tb}')
        await message.answer('❌ Ошибка при обработке API URL', parse_mode=None)


async def process_cert_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода сертификата и сохранение конфигурации"""
    try:
        if message.text == '/cancel':
            await state.clear()
            await message.answer('❌ Добавление сервера отменено', parse_mode=None)
            return

        cert_sha256 = message.text.strip()
        
        # Простая валидация сертификата (должен быть 64 символа)
        if len(cert_sha256) != 64:
            await message.answer(
                '⚠️ SHA256 сертификат должен содержать ровно 64 символа\n'
                f'Получено: {len(cert_sha256)} символов\n\n'
                'Попробуйте еще раз или отправьте /cancel',
                parse_mode=None
            )
            return

        # Получаем все сохраненные данные
        data = await state.get_data()
        country_name = data.get('country_name', '')
        flag = data.get('flag', '🌐')
        api_url = data.get('api_url', '')
        
        # Читаем текущую конфигурацию
        config_file = 'core/api_s/outline/settings_api_outline.json'
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}

        # Добавляем новый сервер
        config[country_name] = {
            "name_en": country_name,
            "name_ru": f"{flag} {country_name.title()}",
            "api_url": api_url,
            "cert_sha256": cert_sha256,
            "is_active": True
        }

        # Сохраняем конфигурацию
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

        await state.clear()
        
        await message.answer(
            text=(
                '✅ <b>Сервер успешно добавлен!</b>\n\n'
                f'<b>Страна:</b> {flag} {country_name.title()}\n'
                f'<b>API URL:</b> {api_url}\n'
                f'<b>Сертификат:</b> {cert_sha256[:16]}...\n'
                f'<b>Статус:</b> Активен\n\n'
                'Сервер будет доступен пользователям после перезапуска бота.'
            ),
            parse_mode='HTML'
        )
        
        logger.log('info', f'Admin {message.from_user.id} added new server: {country_name}')
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'process_cert_input error: {e}\n{tb}')
        await message.answer('❌ Ошибка при сохранении конфигурации сервера', parse_mode=None)
        await state.clear()
