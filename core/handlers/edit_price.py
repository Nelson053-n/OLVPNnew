"""
Обработчик команды /editprice - редактирование цен на подписки
"""
import json
import os
import traceback
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()
router = Router()

PRICES_FILE = 'core/settings_prices.json'


class EditPriceStates(StatesGroup):
    waiting_for_new_price = State()


def load_prices() -> dict:
    """Загрузить цены из JSON файла"""
    try:
        with open(PRICES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Значения по умолчанию
        default_prices = {
            "day": {"amount": 7, "days": 1, "word_days": "день"},
            "month": {"amount": 150, "days": 30, "word_days": "дней"},
            "year": {"amount": 1500, "days": 365, "word_days": "дней"}
        }
        save_prices(default_prices)
        return default_prices


def save_prices(prices: dict) -> None:
    """Сохранить цены в JSON файл"""
    with open(PRICES_FILE, 'w', encoding='utf-8') as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)


@router.message(Command('editprice'))
async def editprice_handler(message: Message, state: FSMContext) -> None:
    """
    Команда редактирования цен на подписки (только для администратора)
    Показывает текущие цены и кнопки для редактирования
    """
    try:
        # Проверка прав администратора
        if not admin_tlg or message.from_user.id != admin_tlg:
            await message.answer('❌ Эта команда доступна только администратору', parse_mode=None)
            return

        # Загружаем текущие цены
        prices = load_prices()
        
        # Создаем клавиатуру с кнопками для редактирования
        builder = InlineKeyboardBuilder()
        
        # Кнопка для дня
        day_price = prices.get('day', {}).get('amount', 7)
        builder.button(text=f'📅 День - {day_price}₽', callback_data='edprc_day')
        
        # Кнопка для месяца
        month_price = prices.get('month', {}).get('amount', 150)
        builder.button(text=f'📆 Месяц - {month_price}₽', callback_data='edprc_month')
        
        # Кнопка для года
        year_price = prices.get('year', {}).get('amount', 1500)
        builder.button(text=f'📅 Год - {year_price}₽', callback_data='edprc_year')
        
        # Кнопка для промо периода (только количество дней)
        promo_days = prices.get('promo', {}).get('days', 7)
        builder.button(text=f'🎁 Промо период - {promo_days} дней', callback_data='edprc_promo')
        
        builder.adjust(1)  # Каждая кнопка на отдельной строке
        
        await message.answer(
            text=(
                '💰 <b>Редактирование цен</b>\n\n'
                f'<b>День (1 день):</b> {day_price}₽\n'
                f'<b>Месяц (30 дней):</b> {month_price}₽\n'
                f'<b>Год (365 дней):</b> {year_price}₽\n'
                f'<b>Промо период:</b> {promo_days} дней\n\n'
                'Выберите период для изменения:'
            ),
            reply_markup=builder.as_markup(),
            parse_mode='HTML'
        )

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'editprice_handler error: {e}\n{tb}')
        await message.answer('❌ Ошибка при загрузке цен', parse_mode=None)


@router.callback_query(lambda c: c.data and c.data.startswith('edprc_'))
async def select_period_to_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик выбора периода для редактирования
    Запрашивает новую цену
    """
    try:
        await callback.answer()

        # Проверка прав администратора
        if not admin_tlg or callback.from_user.id != admin_tlg:
            return

        # Извлекаем период (day, month, year)
        period = callback.data.replace('edprc_', '')

        valid_periods = {'day', 'month', 'year', 'promo'}
        if period not in valid_periods:
            await callback.message.answer("Некорректный период.", parse_mode=None)
            return

        # Загружаем текущие цены
        prices = load_prices()
        current_price = prices.get(period, {}).get('amount', 0)
        
        # Определяем название периода на русском
        period_names = {
            'day': 'День (1 день)',
            'month': 'Месяц (30 дней)',
            'year': 'Год (365 дней)',
            'promo': 'Промо период (количество дней)'
        }
        period_name = period_names.get(period, period)
        
        # Для промо показываем только дни, для остальных - цену
        if period == 'promo':
            current_value = prices.get('promo', {}).get('days', 7)
            value_text = f'{current_value} дней'
            prompt_text = 'Введите количество дней для промо периода (только число):\nНапример: 7'
        else:
            current_value = prices.get(period, {}).get('amount', 0)
            value_text = f'{current_value}₽'
            prompt_text = 'Введите новую цену в рублях (только число):\nНапример: 50'
        
        # Сохраняем период в состоянии
        await state.update_data(edit_period=period)
        await state.set_state(EditPriceStates.waiting_for_new_price)
        
        await callback.message.edit_text(
            text=(
                f'💰 <b>Изменение: {period_name}</b>\n\n'
                f'Текущее значение: <b>{value_text}</b>\n\n'
                f'{prompt_text}\n\n'
                'Или отправьте /cancel для отмены'
            ),
            parse_mode='HTML'
        )
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'select_period_to_edit error: {e}\n{tb}')
        await callback.message.edit_text('❌ Ошибка при обработке запроса', parse_mode=None)


@router.message(EditPriceStates.waiting_for_new_price)
async def process_new_price(message: Message, state: FSMContext) -> None:
    """
    Обработка ввода новой цены
    """
    try:
        # Проверка прав администратора
        if not admin_tlg or message.from_user.id != admin_tlg:
            await state.clear()
            return

        if message.text == '/cancel':
            await state.clear()
            await message.answer('❌ Изменение цены отменено', parse_mode=None)
            return
        
        # Проверяем, что введено число
        try:
            new_price = int(message.text.strip())
            if new_price <= 0:
                await message.answer(
                    '❌ Цена должна быть положительным числом. Попробуйте снова:',
                    parse_mode=None
                )
                return
        except ValueError:
            await message.answer(
                '❌ Неверный формат. Введите только число, например: 50',
                parse_mode=None
            )
            return
        
        # Получаем сохраненный период
        data = await state.get_data()
        period = data.get('edit_period')
        
        if not period:
            await message.answer('❌ Ошибка: период не выбран', parse_mode=None)
            await state.clear()
            return
        
        # Загружаем текущие цены
        prices = load_prices()
        
        # Определяем что редактируем
        is_promo = (period == 'promo')
        
        if is_promo:
            # Для промо сохраняем только дни
            old_value = prices.get('promo', {}).get('days', 7)
            if 'promo' not in prices:
                prices['promo'] = {'days': new_price, 'word_days': 'дней'}
            else:
                prices['promo']['days'] = new_price
            value_type = 'дней'
        else:
            # Для остальных - цену
            old_value = prices.get(period, {}).get('amount', 0)
            if period in prices:
                prices[period]['amount'] = new_price
            else:
                days_map = {'day': 1, 'month': 30, 'year': 365}
                word_map = {'day': 'день', 'month': 'дней', 'year': 'дней'}
                prices[period] = {
                    'amount': new_price,
                    'days': days_map.get(period, 1),
                    'word_days': word_map.get(period, 'дней')
                }
            value_type = '₽'
        
        # Сохраняем в файл
        save_prices(prices)
        
        # Определяем название периода
        period_names = {
            'day': 'День',
            'month': 'Месяц',
            'year': 'Год',
            'promo': 'Промо период'
        }
        period_name = period_names.get(period, period)
        
        # Очищаем состояние
        await state.clear()
        
        # Логируем изменение
        logger.log('info', f'Settings changed by admin {message.from_user.id}: {period} {old_value}{value_type} -> {new_price}{value_type}')
        
        # Выводим все текущие цены
        promo_days = prices.get('promo', {}).get('days', 7)
        all_prices_text = (
            f'✅ <b>Настройка успешно изменена!</b>\n\n'
            f'<b>{period_name}:</b> {old_value}{value_type} → {new_price}{value_type}\n\n'
            f'📊 <b>Текущие настройки:</b>\n'
            f'• День (1 день): {prices["day"]["amount"]}₽\n'
            f'• Месяц (30 дней): {prices["month"]["amount"]}₽\n'
            f'• Год (365 дней): {prices["year"]["amount"]}₽\n'
            f'• Промо период: {promo_days} дней\n\n'
            f'⚠️ Изменения вступают в силу немедленно.'
        )
        
        await message.answer(text=all_prices_text, parse_mode='HTML')
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'process_new_price error: {e}\n{tb}')
        await message.answer('❌ Ошибка при сохранении цены', parse_mode=None)
        await state.clear()
