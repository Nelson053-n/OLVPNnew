from aiogram.types import Message
import traceback

from core.utils.admin_check import require_admin
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


@require_admin
async def command_mass_block(message: Message) -> None:
    """
    Команда администратора для немедленной массовой блокировки всех просроченных подписок.
    """
    try:
        from core.check_time_subscribe import finish_set_date_and_premium
        deleted_count = await finish_set_date_and_premium()
        
        if deleted_count == 0:
            await message.answer('✅ Просроченные ключи не найдены', parse_mode=None)
        else:
            await message.answer(f'✅ Массовая проверка выполнена.\n🔒 Заблокировано просроченных ключей: {deleted_count}', parse_mode=None)
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_mass_block error for admin {message.from_user.id}: {e}\n{tb}')
        try:
            await message.answer('Ошибка при выполнении массовой блокировки.', parse_mode=None)
        except Exception:
            pass
