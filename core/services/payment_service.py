"""
Сервис для работы с платежами.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List

from core.sql.function_db_user_payments.users_payments import (
    add_payment_to_db,
    get_user_payments,
)
from core.sql.function_db_user_vpn.users_vpn import (
    get_user_data_from_table_users,
    add_user_key,
    set_premium_status,
    set_date_to_table_users,
    set_region_server,
    set_key_to_table_users,
)


class PaymentService:
    """Сервис для управления платежами"""

    async def process_payment(
        self,
        user_id: int,
        amount: int,
        days: int,
        region: str,
        access_url: str,
        outline_id: str,
        payment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Обработать успешный платеж.

        :param user_id: ID пользователя
        :param amount: Сумма платежа
        :param days: Количество дней
        :param region: Регион сервера
        :param access_url: URL доступа
        :param outline_id: ID ключа в Outline
        :param payment_id: ID платежа (опционально)
        :return: dict с результатом
        """
        try:
            now = datetime.now()
            expiry_date = now + timedelta(days=days)
            date_str = expiry_date.strftime('%d.%m.%Y - %H:%M')

            await add_user_key(
                account=user_id,
                access_url=access_url,
                outline_id=outline_id,
                region_server=region,
                date_str=date_str,
                promo=False
            )
            await set_premium_status(account=user_id, value_premium=True)
            await set_date_to_table_users(account=user_id, value_date=date_str)
            await set_region_server(account=user_id, value_region=region)
            await set_key_to_table_users(account=user_id, value_key=access_url)

            if payment_id:
                await add_payment_to_db(
                    account_id=user_id,
                    paykey=payment_id,
                    amount=amount
                )

            return {
                'success': True,
                'expiry_date': date_str,
                'days': days,
                'region': region
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def get_payment_history(self, user_id: int) -> Dict[str, Any]:
        """
        Получить историю платежей пользователя.

        :param user_id: ID пользователя
        :return: dict с историей платежей
        """
        try:
            payments = await get_user_payments(account_id=user_id)

            payment_list = []
            for pay in payments:
                payment_list.append({
                    'payment_id': pay.paykey,
                    'time_added': pay.time_added.strftime('%d.%m.%Y %H:%M') if pay.time_added else None,
                    'amount': getattr(pay, 'amount', 0)
                })

            return {
                'success': True,
                'user_id': user_id,
                'payments': payment_list,
                'total_payments': len(payment_list)
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}


payment_service = PaymentService()
