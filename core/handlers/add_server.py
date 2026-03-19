from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import json
import traceback

from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()

# Словарь флагов стран (настоящие emoji символы)
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
    'russia': '🇷🇺',
    'kazakhstan': '🇰🇿',
}


class AddServerStates(StatesGroup):
    waiting_for_country_ru = State()
    waiting_for_api_url = State()
    waiting_for_cert = State()


async def command_addserver(message: Message, state: FSMContext) -> None:
    """
    -- Админ-команда --
    /addserver
    Запускает процесс добавления нового Outline сервера.
    Пошагово запрашивает: страну (через кнопки), русское название, API URL, сертификат.
    """
    try:
        if not admin_tlg or message.from_user.id != admin_tlg:
            await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
            return

        # Создаем кнопки со странами
        builder = InlineKeyboardBuilder()
        
        # Сортируем страны по алфавиту для удобства
        sorted_countries = sorted(COUNTRY_FLAGS.items())
        
        for country_key, flag in sorted_countries:
            # Название кнопки: флаг + название страны
            button_text = f"{flag} {country_key.title()}"
            builder.button(
                text=button_text,
                callback_data=f"addsvr_{country_key}"
            )
        
        # Располагаем по 2 кнопки в ряд
        builder.adjust(2)
        
        await message.answer(
            text=(
                '🌍 <b>Добавление нового Outline сервера</b>\n\n'
                'Шаг 1/4: Выберите страну из списка\n\n'
                'Или отправьте /cancel для отмены'
            ),
            reply_markup=builder.as_markup(),
            parse_mode='HTML'
        )
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_addserver error: {e}\n{tb}')
        await message.answer('❌ Ошибка при запуске команды', parse_mode=None)


async def process_country_choice(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора страны через кнопку"""
    try:
        await callback.answer()
        
        # Извлекаем название страны из callback_data
        country_name = callback.data.replace('addsvr_', '')
        
        # Определяем флаг
        flag = COUNTRY_FLAGS.get(country_name, '🌐')
        
        # Сохраняем данные в состоянии
        await state.update_data(country_name=country_name, flag=flag)
        await state.set_state(AddServerStates.waiting_for_country_ru)
        
        await callback.message.edit_text(
            text=(
                f'✅ Страна (EN): {country_name}\n'
                f'✅ Флаг: {flag}\n\n'
                'Шаг 2/4: Введите название страны на РУССКОМ языке\n'
                '(например: Германия, Франция, США, Казахстан)\n\n'
                'Или /cancel для отмены'
            ),
            parse_mode=None
        )
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'process_country_choice error: {e}\n{tb}')
        await callback.message.answer('❌ Ошибка при обработке выбора страны', parse_mode=None)


async def process_country_ru_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода названия страны на русском"""
    try:
        if message.text == '/cancel':
            await state.clear()
            await message.answer('❌ Добавление сервера отменено', parse_mode=None)
            return

        country_name_ru = message.text.strip()
        
        # Сохраняем русское название
        await state.update_data(country_name_ru=country_name_ru)
        await state.set_state(AddServerStates.waiting_for_api_url)
        
        data = await state.get_data()
        country_name = data.get('country_name', '')
        flag = data.get('flag', '🌐')
        
        await message.answer(
            text=(
                f'✅ Страна (EN): {country_name}\n'
                f'✅ Страна (RU): {country_name_ru}\n'
                f'✅ Флаг: {flag}\n\n'
                'Шаг 3/4: Введите API URL сервера Outline\n'
                '(например: https://123.456.789.012:12345/aBcDeFgH)\n\n'
                'Или /cancel для отмены'
            ),
            parse_mode=None
        )
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'process_country_ru_input error: {e}\n{tb}')
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
        country_name_ru = data.get('country_name_ru', '')
        flag = data.get('flag', '🌐')
        
        await message.answer(
            text=(
                f'✅ Страна (EN): {country_name}\n'
                f'✅ Страна (RU): {country_name_ru}\n'
                f'✅ Флаг: {flag}\n'
                f'✅ API URL: {api_url}\n\n'
                'Шаг 4/4: Введите SHA256 сертификат\n'
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
        country_name_ru = data.get('country_name_ru', '')
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
            "name_ru": f"{flag} {country_name_ru}",
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
                f'<b>Страна (EN):</b> {country_name}\n'
                f'<b>Страна (RU):</b> {flag} {country_name_ru}\n'
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
