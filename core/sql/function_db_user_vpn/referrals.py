"""
Функции работы с реферальной программой
"""
from datetime import datetime
from sqlalchemy import create_engine, func
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session
import uuid

from core.sql.base import Base, Referral

DATABASE_URL = 'sqlite:///olvpnbot.db'
engine = create_engine(DATABASE_URL, echo=False)
Base.metadata.create_all(engine)


async def add_referral(referrer_id: int, referred_id: int, bonus_days: int = 7) -> bool:
    """
    Добавить запись о реферале
    Проверяет, что запись не добавляется дважды для одной пары (referrer_id, referred_id)
    
    :param referrer_id: ID пригласившего
    :param referred_id: ID приглашённого
    :param bonus_days: Количество дней бонуса
    :return: bool
    """
    with Session(engine) as session:
        try:
            # Проверяем, есть ли уже такая запись
            existing = session.query(Referral).filter(
                Referral.referrer_id == referrer_id,
                Referral.referred_id == referred_id
            ).first()
            
            if existing:
                # Запись уже существует, не добавляем дубликат
                return False
            
            referral = Referral(
                id=f"{referrer_id}_{referred_id}_{uuid.uuid4()}",
                referrer_id=referrer_id,
                referred_id=referred_id,
                bonus_days=bonus_days,
                bonus_given=False
            )
            session.add(referral)
            session.commit()
            return True
        except Exception as e:
            print(f"ERROR add_referral: {e}")
            return False


async def get_referral_bonus_status(referred_id: int) -> dict | None:
    """
    Получить статус реферального бонуса
    
    :param referred_id: ID приглашённого пользователя
    :return: dict с информацией о реферале или None
    """
    with Session(engine) as session:
        try:
            referral = session.query(Referral).filter_by(referred_id=referred_id).one()
            return {
                'referrer_id': referral.referrer_id,
                'bonus_days': referral.bonus_days,
                'bonus_given': referral.bonus_given,
                'referral_date': referral.referral_date
            }
        except NoResultFound:
            return None


async def mark_referral_bonus_given(referred_id: int) -> bool:
    """
    Отметить что бонус реферала был выдан
    
    :param referred_id: ID приглашённого пользователя
    :return: bool
    """
    with Session(engine) as session:
        try:
            referral = session.query(Referral).filter_by(referred_id=referred_id).one()
            referral.bonus_given = True
            referral.bonus_date = datetime.now()
            session.commit()
            return True
        except Exception as e:
            print(f"ERROR mark_referral_bonus_given: {e}")
            return False


async def get_user_referrals(referrer_id: int) -> list[dict]:
    """
    Получить всех приглашённых пользователей и статус бонусов
    
    :param referrer_id: ID пригласившего
    :return: list с информацией о рефералах
    """
    with Session(engine) as session:
        try:
            referrals = session.query(Referral).filter_by(referrer_id=referrer_id).all()
            result = []
            for ref in referrals:
                result.append({
                    'referred_id': ref.referred_id,
                    'bonus_days': ref.bonus_days,
                    'bonus_given': ref.bonus_given,
                    'referral_date': ref.referral_date
                })
            return result
        except Exception as e:
            print(f"ERROR get_user_referrals: {e}")
            return []


async def get_referral_count_by_user(referrer_id: int, only_with_bonus: bool = False) -> int:
    """
    Получить количество успешных рефералов пользователя
    
    :param referrer_id: ID пригласившего
    :param only_with_bonus: Только рефералы с выданным бонусом
    :return: int
    """
    with Session(engine) as session:
        try:
            query = session.query(Referral).filter_by(referrer_id=referrer_id)
            if only_with_bonus:
                query = query.filter_by(bonus_given=True)
            return query.count()
        except Exception as e:
            print(f"ERROR get_referral_count_by_user: {e}")
            return 0


async def get_referral_counts_for_users(referrer_ids: list[int]) -> dict[int, int]:
    """
    Получить количества рефералов пачкой для списка пользователей.

    :param referrer_ids: список ID рефереров
    :return: словарь {referrer_id: count}
    """
    if not referrer_ids:
        return {}

    with Session(engine) as session:
        try:
            rows = (
                session.query(
                    Referral.referrer_id,
                    func.count(Referral.id)
                )
                .filter(Referral.referrer_id.in_(referrer_ids))
                .group_by(Referral.referrer_id)
                .all()
            )
            return {int(referrer_id): int(count) for referrer_id, count in rows}
        except Exception as e:
            print(f"ERROR get_referral_counts_for_users: {e}")
            return {}
