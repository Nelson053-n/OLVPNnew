from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from core.settings import admin_tlg
from core.sql.function_db_user_vpn.users_vpn import get_all_records_from_table_users, get_all_user_keys


async def command_active_keys(message: Message) -> None:
    """
    -- Админ-команда --
    Обработчик команды /activekeys.
    Выводит список всех пользователей с активными ключами и датой окончания.
    Может отфильтровать по дате если указана опция.

    :param message: Message - Объект Message, полученный при вызове команды.
    """
    if message.from_user.id != int(admin_tlg):
        await message.answer("❌ У вас нет доступа к этой команде")
        return

    try:
        # Получаем пользователей и все ключи
        all_users = await get_all_records_from_table_users()
        all_keys = await get_all_user_keys()

        # Группируем ключи по пользователю и фильтруем только ещё действующие
        now = datetime.now()
        keys_by_user: dict[int, list] = {}
        for k in all_keys:
            # Ключ активен, если есть дата и она в будущем
            if k.date and k.date > now:
                keys_by_user.setdefault(k.account, []).append(k)

        if not keys_by_user:
            await message.answer("❌ Нет пользователей с активными ключами")
            return

        # Подготовим мапу user_id -> Users запись для имён/ника
        user_map = {u.account: u for u in all_users}

        # Список пользователей с суммарной ближайшей датой (для сортировки)
        user_summaries = []
        for uid, keys in keys_by_user.items():
            nearest = min(k.date for k in keys if k.date)
            user_summaries.append((uid, keys, nearest))
        user_summaries.sort(key=lambda x: x[2])

        # Формируем текст
        total_active_keys = sum(len(v) for v in keys_by_user.values())
        lines = ["<b>📋 Активные ключи по пользователям</b>\n"]
        for idx, (uid, keys, _) in enumerate(user_summaries, 1):
            u = user_map.get(uid)
            uname = getattr(u, 'account_name', '—') if u else '—'
            lines.append(f"<b>{idx}.</b> <code>{uid}</code> | <b>{uname}</b>")
            for k in sorted(keys, key=lambda x: x.date):
                days_remaining = (k.date - now).days if k.date else 0
                if days_remaining <= 1:
                    emoji = "🔴"
                elif days_remaining <= 3:
                    emoji = "🟡"
                else:
                    emoji = "🟢"
                date_str = k.date.strftime("%d.%m.%Y %H:%M") if k.date else '—'
                lines.append(
                    f"   {emoji} Регион: {k.region_server or 'не указан'} | "
                    f"Окончание: {date_str} ({days_remaining} дн.)"
                )
            lines.append("")

        lines.append(f"<b>Всего активных ключей:</b> {total_active_keys}")
        response_text = "\n".join(lines)

        if len(response_text) > 4096:
            # Рубим по пользователям, по 10 пользователей в сообщении
            chunk_size = 10
            for i in range(0, len(user_summaries), chunk_size):
                chunk = user_summaries[i:i+chunk_size]
                chunk_lines = [f"<b>📋 Активные ключи ({i+1}-{min(i+chunk_size, len(user_summaries))} из {len(user_summaries)})</b>\n"]
                kb = InlineKeyboardBuilder()
                for idx, (uid, keys, _) in enumerate(chunk, i+1):
                    u = user_map.get(uid)
                    uname = getattr(u, 'account_name', '—') if u else '—'
                    chunk_lines.append(f"<b>{idx}.</b> <code>{uid}</code> | <b>{uname}</b>")
                    # Кнопка для подробностей по пользователю
                    kb.button(text=f"ℹ️ {uid}", callback_data=f"check_user_key_{uid}")
                    for k in sorted(keys, key=lambda x: x.date):
                        days_remaining = (k.date - now).days if k.date else 0
                        if days_remaining <= 1:
                            emoji = "🔴"
                        elif days_remaining <= 3:
                            emoji = "🟡"
                        else:
                            emoji = "🟢"
                        date_str = k.date.strftime("%d.%m.%Y %H:%M") if k.date else '—'
                        chunk_lines.append(
                            f"   {emoji} Регион: {k.region_server or 'не указан'} | "
                            f"Окончание: {date_str} ({days_remaining} дн.)"
                        )
                    chunk_lines.append("")
                kb.adjust(3)
                await message.answer("\n".join(chunk_lines), reply_markup=kb.as_markup())
        else:
            kb = InlineKeyboardBuilder()
            for uid, _, _ in user_summaries:
                kb.button(text=f"ℹ️ {uid}", callback_data=f"check_user_key_{uid}")
            kb.adjust(3)
            await message.answer(response_text, reply_markup=kb.as_markup())
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении списка: {str(e)}")
