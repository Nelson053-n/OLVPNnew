"""
Unit-тесты для PaymentService.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Тесты PaymentService.process_payment
# ---------------------------------------------------------------------------

class TestProcessPayment:
    @pytest.mark.asyncio
    async def test_success_with_payment_id(self):
        """Успешная обработка платежа с сохранением payment_id."""
        from core.services.payment_service import PaymentService

        svc = PaymentService()

        with patch(
            "core.services.payment_service.add_user_key",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.set_premium_status",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.set_date_to_table_users",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.set_region_server",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.set_key_to_table_users",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.add_payment_to_db",
            new_callable=AsyncMock,
        ) as mock_add_pay:
            result = await svc.process_payment(
                user_id=123,
                amount=150,
                days=30,
                region="nederland",
                access_url="ss://test-url",
                outline_id="42",
                payment_id="pay-abc123",
            )

        assert result["success"] is True
        assert result["days"] == 30
        assert result["region"] == "nederland"
        mock_add_pay.assert_called_once_with(
            account=123,
            paykey="pay-abc123",
        )

    @pytest.mark.asyncio
    async def test_success_without_payment_id(self):
        """Обработка платежа без payment_id — add_payment_to_db не вызывается."""
        from core.services.payment_service import PaymentService

        svc = PaymentService()

        with patch(
            "core.services.payment_service.add_user_key",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.set_premium_status",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.set_date_to_table_users",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.set_region_server",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.set_key_to_table_users",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.add_payment_to_db",
            new_callable=AsyncMock,
        ) as mock_add_pay:
            result = await svc.process_payment(
                user_id=123,
                amount=40,
                days=7,
                region="germany",
                access_url="ss://test-url",
                outline_id="99",
                payment_id=None,
            )

        assert result["success"] is True
        mock_add_pay.assert_not_called()

    @pytest.mark.asyncio
    async def test_expiry_date_calculated_correctly(self):
        """Дата истечения должна быть now + days."""
        from core.services.payment_service import PaymentService

        svc = PaymentService()
        before = datetime.now()

        with patch(
            "core.services.payment_service.add_user_key",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.set_premium_status",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.set_date_to_table_users",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.set_region_server",
            new_callable=AsyncMock,
        ), patch(
            "core.services.payment_service.set_key_to_table_users",
            new_callable=AsyncMock,
        ):
            result = await svc.process_payment(
                user_id=123,
                amount=150,
                days=30,
                region="nederland",
                access_url="ss://url",
                outline_id="1",
            )

        after = datetime.now()
        # Проверяем формат даты
        expiry_str = result["expiry_date"]
        expiry_dt = datetime.strptime(expiry_str, "%d.%m.%Y - %H:%M")
        expected_min = before + timedelta(days=30)
        expected_max = after + timedelta(days=30)
        # Допуск ±1 минута из-за усечения до минут при форматировании
        assert expected_min - timedelta(minutes=1) <= expiry_dt <= expected_max + timedelta(minutes=1)

    @pytest.mark.asyncio
    async def test_db_error_returns_failure(self):
        """При ошибке БД должен вернуть success=False с описанием ошибки."""
        from core.services.payment_service import PaymentService

        svc = PaymentService()

        with patch(
            "core.services.payment_service.add_user_key",
            new_callable=AsyncMock,
            side_effect=Exception("DB connection error"),
        ):
            result = await svc.process_payment(
                user_id=123,
                amount=150,
                days=30,
                region="nederland",
                access_url="ss://url",
                outline_id="1",
            )

        assert result["success"] is False
        assert "DB connection error" in result["error"]


# ---------------------------------------------------------------------------
# Тесты PaymentService.get_payment_history
# ---------------------------------------------------------------------------

class TestGetPaymentHistory:
    @pytest.mark.asyncio
    async def test_returns_history(self):
        """Должен возвращать историю платежей."""
        from core.services.payment_service import PaymentService

        svc = PaymentService()

        pay1 = MagicMock()
        pay1.paykey = "pay-001"
        pay1.time_added = datetime(2026, 1, 15, 12, 0)
        pay1.amount = 150
        pay1.account_id = 123

        pay2 = MagicMock()
        pay2.paykey = "pay-002"
        pay2.time_added = datetime(2026, 2, 1, 10, 30)
        pay2.amount = 40
        pay2.account_id = 123

        with patch(
            "core.services.payment_service.get_all_user_payments",
            new_callable=AsyncMock,
            return_value=[pay1, pay2],
        ):
            result = await svc.get_payment_history(user_id=123)

        assert result["success"] is True
        assert result["total_payments"] == 2
        assert result["payments"][0]["payment_id"] == "pay-001"
        assert result["payments"][1]["payment_id"] == "pay-002"

    @pytest.mark.asyncio
    async def test_empty_history(self):
        """При отсутствии платежей возвращает пустой список."""
        from core.services.payment_service import PaymentService

        svc = PaymentService()

        with patch(
            "core.services.payment_service.get_all_user_payments",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await svc.get_payment_history(user_id=456)

        assert result["success"] is True
        assert result["total_payments"] == 0
        assert result["payments"] == []

    @pytest.mark.asyncio
    async def test_db_error_returns_failure(self):
        """При ошибке БД должен вернуть success=False."""
        from core.services.payment_service import PaymentService

        svc = PaymentService()

        with patch(
            "core.services.payment_service.get_all_user_payments",
            new_callable=AsyncMock,
            side_effect=Exception("Query failed"),
        ):
            result = await svc.get_payment_history(user_id=123)

        assert result["success"] is False
        assert "Query failed" in result["error"]
