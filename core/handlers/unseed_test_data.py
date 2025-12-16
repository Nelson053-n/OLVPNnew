from aiogram.types import Message
import traceback

from core.settings import admin_tlg
from core.api_s.outline.outline_api import OutlineManager
from core.sql.function_db_user_vpn.users_vpn import (
    get_all_user_keys,
    get_all_records_from_table_users,
    get_user_keys,
    delete_user_key_record,
    set_key_to_table_users,
    set_premium_status,
    set_region_server,
    set_date_to_table_users,
)


def is_test_user(account_name: str | None, account_id: int | None) -> bool:
    """Проверяет, является ли пользователь тестовым"""
    if account_name and account_name.startswith('test_'):
        return True
    return False


def is_test_key(outline_id: str | None) -> bool:
    """Проверяет, является ли ключ тестовым"""
    if outline_id and outline_id.startswith('test_'):
        return True
    return False


async def _delete_user_from_db(user_id: int):
    """Удаляет пользователя из таблицы Users"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from core.sql.base import Users
    
    DATABASE_URL = 'sqlite:///olvpnbot.db'
    engine = create_engine(DATABASE_URL, echo=True)
    
    with Session(engine) as session:
        try:
            user = session.query(Users).filter_by(account=user_id).first()
            if user:
                session.delete(user)
                session.commit()
                return True
        except Exception:
            pass
    return False


async def _delete_user_payments(user_id: int):
    """Удаляет платежи пользователя из таблицы UserPay"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from core.sql.base import UserPay
    
    DATABASE_URL = 'sqlite:///olvpnbot.db'
    engine = create_engine(DATABASE_URL, echo=True)
    
    with Session(engine) as session:
        try:
            payments = session.query(UserPay).filter_by(account_id=user_id).all()
            count = len(payments)
            for payment in payments:
                session.delete(payment)
            session.commit()
            return count
        except Exception:
            pass
    return 0


async def command_unseed(message: Message) -> None:
    """
    -- Админ-команда --
    /unseed
    Удаляет всех тестовых пользователей (с именами test_*) и их данные:
    - Блокирует и удаляет все ключи на сервере Outline
    - Удаляет записи о ключах из БД
    - Удаляет платежи пользователя
    - Удаляет самого пользователя из БД
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
            return

        # Находим всех тестовых пользователей
        all_users = await get_all_records_from_table_users()
        test_users = [u for u in all_users if is_test_user(u.account_name, u.account)]
        
        if not test_users:
            await message.answer('✅ Тестовые пользователи не найдены', parse_mode=None)
            return

        deleted_keys_count = 0
        deleted_payments_count = 0
        deleted_users_count = 0
        errors = []

        for user in test_users:
            user_id = user.account
            user_name = user.account_name or f'ID {user_id}'
            
            try:
                # 1. Получаем все ключи пользователя
                user_keys = await get_user_keys(account=user_id)
                
                # 2. Удаляем ключи с Outline сервера и из БД
                for key in user_keys:
                    try:
                        # Удаляем с Outline если это тестовый ключ
                        if is_test_key(key.outline_id):
                            olm = OutlineManager(region_server=key.region_server or 'nederland')
                            try:
                                olm.delete_key_by_id(key.outline_id)
                            except Exception as e:
                                from logs.log_main import RotatingFileLogger
                                logger = RotatingFileLogger()
                                logger.log('warning', f'Failed to delete key {key.outline_id} from Outline: {e}')
                        
                        # Удаляем из БД
                        await delete_user_key_record(key.id)
                        deleted_keys_count += 1
                    except Exception as e:
                        errors.append(f'Ошибка удаления ключа {key.id}: {str(e)}')
                
                # 3. Удаляем платежи пользователя
                payments_deleted = await _delete_user_payments(user_id)
                deleted_payments_count += payments_deleted
                
                # 4. Удаляем самого пользователя из таблицы Users
                if await _delete_user_from_db(user_id):
                    deleted_users_count += 1
                else:
                    errors.append(f'Не удалось удалить пользователя {user_name}')
                    
            except Exception as e:
                errors.append(f'Ошибка обработки пользователя {user_name}: {str(e)}')

        # Формируем ответ
        response_lines = [
            '✅ Очистка тестовых данных завершена\n',
            f'<b>Удалено пользователей:</b> {deleted_users_count}',
            f'<b>Удалено ключей:</b> {deleted_keys_count}',
            f'<b>Удалено платежей:</b> {deleted_payments_count}',
        ]
        
        if errors:
            response_lines.append(f'\n<b>⚠️ Предупреждения ({len(errors)}):</b>')
            for error in errors[:5]:  # Показываем только первые 5 ошибок
                response_lines.append(f'  • {error}')
            if len(errors) > 5:
                response_lines.append(f'  • ...и ещё {len(errors) - 5}')

        await message.answer(
            text='\n'.join(response_lines),
            parse_mode='HTML',
        )
        
    except Exception as e:
        tb = traceback.format_exc()
        from logs.log_main import RotatingFileLogger
        logger = RotatingFileLogger()
        logger.log('error', f'command_unseed error: {e}\n{tb}')
        try:
            await message.answer(f'❌ Ошибка при удалении тестовых данных:\n{str(e)}', parse_mode=None)
        except Exception:
            pass
