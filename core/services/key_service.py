"""
Сервис для работы с ключами доступа.
Инкапсулирует логику создания, замены и управления ключами.
"""
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from core.api_s.outline.outline_api import OutlineManager, get_name_all_active_server_ol, get_server_display_name
from core.sql.function_db_user_vpn.users_vpn import (
    get_user_keys,
    get_all_user_keys,
    add_user_key,
    set_premium_status,
    set_date_to_table_users,
    set_region_server,
    set_key_to_table_users,
    set_promo_status,
    delete_user_key_record,
    get_user_data_from_table_users,
)


class KeyService:
    """Сервис для управления ключами пользователей"""

    def __init__(self):
        self.config_path = Path(__file__).parent.parent / 'settings_prices.json'

    async def get_least_busy_server(self, user_id: int) -> str:
        """
        Получить самый свободный сервер для пользователя.
        Исключает серверы, на которых у пользователя уже есть ключи.
        """
        try:
            user_keys = await get_user_keys(account=user_id)
            user_servers = {key.region_server for key in user_keys if key.region_server}

            all_servers = get_name_all_active_server_ol()
            available_servers = [s for s in all_servers if s not in user_servers]

            if not available_servers:
                available_servers = all_servers

            if not available_servers:
                return 'nederland'

            all_user_keys = await get_all_user_keys()
            server_load = {
                server: sum(
                    1 for key in all_user_keys
                    if key.region_server == server and key.premium
                )
                for server in available_servers
            }

            return min(server_load.items(), key=lambda x: x[1])[0]

        except Exception as e:
            return 'nederland'

    async def create_promo_key(
        self,
        user_id: int,
        days: int = 7,
        server: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создать промо-ключ для пользователя.

        :param user_id: ID пользователя
        :param days: Количество дней действия
        :param server: Сервер (если None, выбирается наименее загруженный)
        :return: dict с результатом операции
        """
        try:
            user = await get_user_data_from_table_users(account=user_id)
            if not user:
                return {'success': False, 'error': 'Пользователь не найден'}

            if server is None:
                server = await self.get_least_busy_server(user_id)

            expiry_date = datetime.now() + timedelta(days=days)
            date_str = expiry_date.strftime('%d.%m.%Y - %H:%M')

            unique_name = f"{user_id}-promo-{uuid.uuid4().hex[:8]}"
            olm = OutlineManager(region_server=server)

            key_data = olm._client.create_key(name=unique_name)
            if not key_data or not getattr(key_data, 'access_url', None):
                return {'success': False, 'error': 'Ошибка создания ключа на сервере'}

            outline_id = str(key_data.key_id)

            await add_user_key(
                account=user_id,
                access_url=key_data.access_url,
                outline_id=outline_id,
                region_server=server,
                date_str=date_str,
                promo=True,
            )
            await set_premium_status(account=user_id, value_premium=True)
            await set_date_to_table_users(account=user_id, value_date=date_str)
            await set_region_server(account=user_id, value_region=server)
            await set_key_to_table_users(account=user_id, value_key=key_data.access_url)
            await set_promo_status(account=user_id, value_promo=True)

            return {
                'success': True,
                'server': server,
                'server_display': get_server_display_name(server),
                'expiry_date': date_str,
                'days': days
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def replace_key(
        self,
        user_id: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Заменить ключ пользователя на новом сервере.

        :param user_id: ID пользователя
        :param reason: Причина замены (опционально)
        :return: dict с результатом операции
        """
        try:
            user = await get_user_data_from_table_users(account=user_id)
            if not user:
                return {'success': False, 'error': 'Пользователь не найден'}

            user_keys = await get_user_keys(account=user_id)
            now = datetime.now()
            active_keys = [
                key for key in user_keys
                if key.date and key.date > now and key.premium
            ]

            if not active_keys:
                return {'success': False, 'error': 'Нет активных ключей для замены'}

            target_key = active_keys[0]
            old_server = target_key.region_server
            old_outline_id = target_key.outline_id

            all_servers = get_name_all_active_server_ol()
            available_servers = [s for s in all_servers if s != old_server]

            if not available_servers:
                return {'success': False, 'error': 'Нет доступных серверов'}

            all_user_keys = await get_all_user_keys()
            server_load = {
                server: sum(
                    1 for key in all_user_keys
                    if key.region_server == server and key.premium
                )
                for server in available_servers
            }
            new_server = min(server_load.items(), key=lambda x: x[1])[0]

            try:
                olm_new = OutlineManager(new_server)
                unique_name = f"{user_id}-replaced-{uuid.uuid4().hex[:8]}"
                new_key = olm_new._client.create_key(name=unique_name)

                if not new_key:
                    return {'success': False, 'error': 'Не удалось создать новый ключ'}

                new_outline_id = str(getattr(new_key, 'key_id', None))
                new_access_url = getattr(new_key, 'access_url', None)

                if not new_outline_id or not new_access_url:
                    return {'success': False, 'error': 'Новый ключ некорректен'}

                expiry_date = target_key.date if target_key.date and target_key.date > now else now + timedelta(days=30)
                date_str = expiry_date.strftime('%d.%m.%Y - %H:%M')

                await add_user_key(
                    account=user_id,
                    outline_id=new_outline_id,
                    access_url=new_access_url,
                    region_server=new_server,
                    date_str=date_str,
                    promo=False
                )
                await set_premium_status(account=user_id, value_premium=True)
                await set_date_to_table_users(account=user_id, value_date=date_str)
                await set_region_server(account=user_id, value_region=new_server)
                await set_key_to_table_users(account=user_id, value_key=new_access_url)

            except Exception as e:
                return {'success': False, 'error': f'Ошибка создания ключа: {e}'}

            try:
                olm_old = OutlineManager(old_server)
                olm_old.delete_key_by_id(old_outline_id)
            except Exception:
                pass

            try:
                await delete_user_key_record(target_key.id)
            except Exception:
                pass

            return {
                'success': True,
                'old_server': old_server,
                'old_server_display': get_server_display_name(old_server),
                'new_server': new_server,
                'new_server_display': get_server_display_name(new_server),
                'expiry_date': date_str
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def get_key_info(self, user_id: int) -> Dict[str, Any]:
        """
        Получить информацию о ключах пользователя.

        :param user_id: ID пользователя
        :return: dict с информацией о ключах
        """
        try:
            user_keys = await get_user_keys(account=user_id)
            now = datetime.now()

            active_keys = []
            expired_keys = []

            for key in user_keys:
                key_info = {
                    'outline_id': key.outline_id,
                    'region_server': key.region_server,
                    'region_display': get_server_display_name(key.region_server) if key.region_server else 'Unknown',
                    'expiry_date': key.date.strftime('%d.%m.%Y - %H:%M') if key.date else None,
                    'is_active': key.date and key.date > now and key.premium,
                    'is_premium': key.premium,
                    'is_promo': key.promo
                }

                if key_info['is_active']:
                    active_keys.append(key_info)
                else:
                    expired_keys.append(key_info)

            return {
                'success': True,
                'user_id': user_id,
                'active_keys': active_keys,
                'expired_keys': expired_keys,
                'total_active': len(active_keys),
                'total_expired': len(expired_keys)
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def delete_key(self, user_id: int, outline_id: str) -> Dict[str, Any]:
        """
        Удалить ключ пользователя.

        :param user_id: ID пользователя
        :param outline_id: ID ключа в Outline
        :return: dict с результатом операции
        """
        try:
            user_keys = await get_user_keys(account=user_id)
            target_key = next((k for k in user_keys if k.outline_id == outline_id), None)

            if not target_key:
                return {'success': False, 'error': 'Ключ не найден'}

            try:
                olm = OutlineManager(region_server=target_key.region_server)
                olm.delete_key_by_id(outline_id)
            except Exception:
                pass

            try:
                await delete_user_key_record(target_key.id)
            except Exception:
                pass

            return {'success': True, 'deleted': True}

        except Exception as e:
            return {'success': False, 'error': str(e)}


key_service = KeyService()
