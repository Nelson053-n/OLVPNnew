from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.settings import admin_tlg
from core.utils.server_config import get_country_flag, add_server_to_config


class AddServerStates(StatesGroup):
    """Состояния для диалога добавления нового сервера"""
    waiting_for_country_name = State()
    waiting_for_api_url = State()
    waiting_for_cert_sha256 = State()
    waiting_for_max_keys = State()
    confirming_server = State()


async def command_add_server(message: Message, state: FSMContext) -> None:
    """
    -- Админ-команда --
    Обработчик команды /addserver.
    Запускает диалоговый режим добавления нового VPN сервера.

    Этапы:
    1. Запрашиваем название страны (флаг выбирается автоматически)
    2. Запрашиваем API URL сервера
    3. Запрашиваем SHA256 сертификата
    4. Показываем превью и подтверждаем добавление

    :param message: Message - объект сообщения
    :param state: FSMContext - контекст состояния
    """
    if message.from_user.id != int(admin_tlg):
        await message.answer("❌ У вас нет доступа к этой команде")
        return

    await message.answer(
        "🌍 <b>Добавление нового VPN сервера</b>\n\n"
        "Введите <b>название страны</b> (например: Нидерланды, США, Германия)"
    )
    await state.set_state(AddServerStates.waiting_for_country_name)


async def process_country_name(message: Message, state: FSMContext) -> None:
    """Обработчик ввода названия страны"""
    country_name = message.text.strip()

    if not country_name or len(country_name) < 2:
        await message.answer("❌ Название страны должно содержать минимум 2 символа")
        return

    # Получаем флаг
    flag = get_country_flag(country_name)

    await state.update_data(country_name=country_name, flag=flag)
    await message.answer(
        f"{flag} <b>{country_name.title()}</b>\n\n"
        "Теперь введите <b>API URL</b> сервера Outline\n"
        "(пример: https://ip:port или https://example.com:port)"
    )
    await state.set_state(AddServerStates.waiting_for_api_url)


async def process_api_url(message: Message, state: FSMContext) -> None:
    """Обработчик ввода API URL"""
    api_url = message.text.strip()

    if not api_url.startswith("https://"):
        await message.answer("❌ API URL должен начинаться с https://")
        return

    await state.update_data(api_url=api_url)
    await message.answer(
        "Теперь введите <b>SHA256 сертификата</b> сервера\n"
        "(строка вида: aabbccdd...)"
    )
    await state.set_state(AddServerStates.waiting_for_cert_sha256)


async def process_cert_sha256(message: Message, state: FSMContext) -> None:
    """Обработчик ввода сертификата"""
    cert_sha256 = message.text.strip()

    if not cert_sha256 or len(cert_sha256) < 10:
        await message.answer("❌ SHA256 сертификата должен быть корректным (минимум 10 символов)")
        return

    await state.update_data(cert_sha256=cert_sha256)
    await message.answer(
        "Введите <b>максимальное количество ключей</b> для этого сервера\n"
        "(пример: 100 или 500)"
    )
    await state.set_state(AddServerStates.waiting_for_max_keys)


async def process_max_keys(message: Message, state: FSMContext) -> None:
    """Обработчик ввода максимального количества ключей"""
    max_keys_str = message.text.strip()

    try:
        max_keys = int(max_keys_str)
        if max_keys < 1:
            await message.answer("❌ Количество ключей должно быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число")
        return

    data = await state.get_data()
    country_name = data.get("country_name")
    flag = data.get("flag")
    api_url = data.get("api_url")
    cert_sha256 = data.get("cert_sha256")

    await state.update_data(max_keys=max_keys)

    # Показываем превью
    preview = (
        f"<b>✅ Проверьте данные сервера:</b>\n\n"
        f"{flag} <b>Страна:</b> {country_name.title()}\n"
        f"<b>API URL:</b> <code>{api_url}</code>\n"
        f"<b>SHA256:</b> <code>{cert_sha256[:20]}...</code>\n"
        f"<b>Макс. ключей:</b> {max_keys}\n\n"
        f"Добавить сервер? (Введите <b>да</b> для подтверждения или <b>нет</b> для отмены)"
    )
    await message.answer(preview)
    await state.set_state(AddServerStates.confirming_server)


async def process_confirmation(message: Message, state: FSMContext) -> None:
    """Обработчик подтверждения добавления сервера"""
    response = message.text.strip().lower()

    if response in ("да", "yes", "y", "д"):
        data = await state.get_data()
        country_name = data.get("country_name")
        api_url = data.get("api_url")
        cert_sha256 = data.get("cert_sha256")
        max_keys = data.get("max_keys", 100)
        flag = data.get("flag")

        # Добавляем сервер в конфиг
        result = await add_server_to_config(
            country_name=country_name,
            api_url=api_url,
            cert_sha256=cert_sha256,
            max_keys=max_keys,
            is_active=True
        )

        if result:
            await message.answer(
                f"✅ <b>Сервер успешно добавлен!</b>\n\n"
                f"{flag} {country_name.title()}\n"
                f"<b>Макс. ключей:</b> {max_keys}\n\n"
                f"Сервер будет доступен пользователям при выборе региона."
            )
        else:
            await message.answer(
                f"❌ <b>Ошибка при добавлении сервера</b>\n\n"
                f"Возможно, сервер с таким названием уже существует."
            )

    elif response in ("нет", "no", "n", "н"):
        await message.answer("❌ Добавление отменено")
    else:
        await message.answer("❓ Пожалуйста, введите <b>да</b> или <b>нет</b>")
        return

    await state.clear()
