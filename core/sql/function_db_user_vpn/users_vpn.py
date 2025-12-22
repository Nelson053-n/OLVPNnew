from datetime import datetime
from typing import Union
from sqlalchemy import create_engine
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session
import uuid

from core.api_s.outline.outline_api import OutlineManager
from core.sql.base import Base, Users, UserKey

DATABASE_URL = 'sqlite:///olvpnbot.db'
engine = create_engine(DATABASE_URL, echo=True)
Base.metadata.create_all(engine)


async def add_user_to_db(account: int, account_name: str) -> None:
    """
    Добавить нового пользователя в таблицу users_vpn

    :param account: int - id пользователя телеграм
    :param account_name: str - Имя пользователя телеграм
    :return: None
    """
    with Session(engine) as session:
        record_id = f"{account}_{uuid.uuid4()}"
        referal_link = f"id_{account}"

        new_record = Users(
            id=record_id,
            account=account,
            account_name=account_name,
            referal_link=referal_link
        )

        session.add(new_record)
        session.commit()


async def get_all_records_from_table_users() -> list[Users]:
    """
    Вывод всех записей таблицы users_vpn
    :return: list[Users] - Все записи из таблицы
    """
    session = Session(engine)
    try:
        result_all_records = session.query(Users).all()
        return result_all_records
    finally:
        session.close()


async def get_user_data_from_table_users(account: int) -> Users:
    """
    Находит и возвращает данные из таблицы users_vpn

    :param account:  int - id пользователя телеграм
    :return: Users - Данные из таблицы
    """
    with Session(engine) as session:
        try:
            user_data = session.query(Users).filter_by(account=account).one()
            return user_data
        except NoResultFound:
            return None


async def set_key_to_table_users(account: int, value_key: OutlineManager) -> bool:
    """
    Изменение ключа в таблице users_vpn

    :param account: int - Идентификатор записи
    :param value_key: str or None - Новое значение ключа outline vpn
    :return: bool - True в случае успеха, False в противном
    """
    with Session(engine) as session:
        try:
            user_record = session.query(Users).filter_by(account=account).one()
            if value_key != user_record.key:
                user_record.key = value_key
                session.commit()
            return True
        except NoResultFound:
            return False


async def get_key_from_table_users(account: int) -> str or bool:
    """
    Получение ключа пользователя из таблицы users_vpn

    :param account: int - Идентификатор записи
    :return: str - Ключ в виде строки в случае успеха, False в противном
    """
    with Session(engine) as session:
        try:
            user_record = session.query(Users).filter_by(account=account).one()
            return user_record.key
        except NoResultFound:
            return False


async def set_premium_status(account: int, value_premium: bool) -> bool:
    """
    Установка статуса премиум для указанного пользователя

    :param account: int - Данные из таблицы users_vpn
    :param value_premium: bool - Значение премиума
    :return: bool - True в случае успеха, False в противном
    """
    with Session(engine) as session:
        try:
            user_record = session.query(Users).filter_by(account=account).one()
            if value_premium != user_record.premium:
                user_record.premium = value_premium
                session.commit()
            return True
        except NoResultFound:
            return False


async def get_premium_status(account: int) -> bool:
    """
    Получение статуса премиум для указанного пользователя

    :param account: int - Данные из таблицы users_vpn
    :return: bool - True если у пользователя стоит флаг премиум, False в противном случае
    """
    with Session(engine) as session:
        try:
            user_record = session.query(Users).filter_by(account=account).one()
            return user_record.premium
        except NoResultFound:
            return False


async def set_date_to_table_users(account: int, value_date: str) -> bool:
    """
    Установка даты до которого действует премиум

    :param account: int - Данные из таблицы
    :param value_date: str - Дата в формате ДД.ММ.ГГГГ - ЧЧ:ММ
    :return: bool - True в случае успеха, False в противном
    """
    with Session(engine) as session:
        try:
            user_record = session.query(Users).filter_by(account=account).one()
            if value_date:
                date = datetime.strptime(value_date, '%d.%m.%Y - %H:%M')
            elif value_date is None:
                date = datetime.strptime('01.01.2000 - 00:00', '%d.%m.%Y - %H:%M')
            if date != user_record.date:
                user_record.date = date
                session.commit()
            return True
        except NoResultFound:
            return False


async def set_promo_status(account: int, value_promo: bool) -> bool:
    """

    :param account: int - Данные из таблицы users_vpn
    :param value_promo: bool - Значение получен промо-ключ или нет
    :return: bool - True в случае успеха, False в противном
    """
    with Session(engine) as session:
        try:
            user_record = session.query(Users).filter_by(account=account).one()
            if value_promo != user_record.promo_key:
                user_record.promo_key = value_promo
                session.commit()
            return True
        except NoResultFound:
            return False


async def get_promo_status(account: int) -> bool:
    """
    Получение статуса промо для указанного пользователя

    :param account: int - Данные из таблицы users_vpn
    :return: bool - True если пользователь получал промо-ключ, False в противном случае
    """
    with Session(engine) as session:
        try:
            user_record = session.query(Users).filter_by(account=account).one()
            return user_record.promo_key
        except NoResultFound:
            return False


async def set_region_server(account: int, value_region: str) -> bool:
    """

    :param account: int - Данные из таблицы users_vpn
    :param value_region: str - Значение региона сервера
    :return: bool - True в случае успеха, False в противном
    """
    with Session(engine) as session:
        try:
            user_record = session.query(Users).filter_by(account=account).one()
            if value_region != user_record.region_server:
                user_record.region_server = value_region
                session.commit()
            return True
        except NoResultFound:
            return False


async def get_region_server(account: int) -> str:
    """
    Получение присвоенного региона для указанного пользователя

    :param account: int - Данные из таблицы users_vpn
    :return: str - Значение присвоенного региона сервера, False в противном случае
    """
    with Session(engine) as session:
        try:
            user_record = session.query(Users).filter_by(account=account).one()
            return user_record.region_server
        except NoResultFound:
            return None


# --- Multiple keys support ---

async def add_user_key(account: int, access_url: str, outline_id: str, region_server: str, date_str: Union[str, datetime], promo: bool) -> bool:
    """
    Добавить новый ключ пользователя в таблицу user_keys
    
    :param account: ID пользователя Telegram
    :param access_url: URL доступа к VPN ключу
    :param outline_id: ID ключа в Outline
    :param region_server: Регион сервера
    :param date_str: Дата истечения в формате '%d.%m.%Y - %H:%M' (str) или объект datetime
    :param promo: Флаг промо-ключа
    :return: True в случае успеха, False при ошибке
    """
    with Session(engine) as session:
        try:
            record_id = f"{account}_key_{uuid.uuid4()}"
            # Парсим дату
            if date_str:
                # Проверяем, не является ли date_str уже объектом datetime
                if isinstance(date_str, datetime):
                    date = date_str
                elif isinstance(date_str, str):
                    date = datetime.strptime(date_str, '%d.%m.%Y - %H:%M')
                else:
                    raise ValueError(f"date_str must be str or datetime, got {type(date_str)}")
            else:
                date = None
            
            new_key = UserKey(
                id=record_id,
                account=account,
                access_url=access_url,
                outline_id=outline_id,
                region_server=region_server,
                premium=True,
                date=date,
                promo=promo,
            )
            session.add(new_key)
            session.commit()
            return True
        except ValueError as e:
            # Ошибка парсинга даты
            print(f"ERROR add_user_key: Invalid date format '{date_str}' (type: {type(date_str)}): {e}")
            return False
        except Exception as e:
            # Другие ошибки БД
            print(f"ERROR add_user_key: Database error for user {account}: {e}")
            import traceback
            traceback.print_exc()
            return False


async def get_user_keys(account: int) -> list[UserKey]:
    session = Session(engine)
    try:
        return session.query(UserKey).filter_by(account=account).all()
    finally:
        session.close()


async def get_all_user_keys() -> list[UserKey]:
    session = Session(engine)
    try:
        return session.query(UserKey).all()
    finally:
        session.close()


async def get_user_key_by_id(key_id: str) -> UserKey | None:
    session = Session(engine)
    try:
        return session.query(UserKey).filter_by(id=key_id).one()
    except NoResultFound:
        return None
    finally:
        session.close()


async def delete_user_key_record(key_id: str) -> bool:
    with Session(engine) as session:
        try:
            k: UserKey = session.query(UserKey).filter_by(id=key_id).one()
            session.delete(k)
            session.commit()
            return True
        except NoResultFound:
            return False



async def add_block_record(account: int, admin_id: int, reason: str, key: str) -> bool:
    """
    Добавляет запись о блокировке ключа в таблицу block_history

    :param account: int - id пользователя
    :param admin_id: int - id администратора
    :param reason: str - причина блокировки
    :param key: str - сам ключ или access_url
    :return: bool
    """
    with Session(engine) as session:
        try:
            record_id = f"{account}_block_{uuid.uuid4()}"
            from core.sql.base import BlockHistory

            new_record = BlockHistory(
                id=record_id,
                account=account,
                admin_id=admin_id,
                reason=reason,
                key=key,
            )
            session.add(new_record)
            session.commit()
            return True
        except Exception:
            return False

