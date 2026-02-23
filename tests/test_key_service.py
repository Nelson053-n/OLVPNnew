"""
Unit-тесты для KeyService.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Вспомогательные фикстуры
# ---------------------------------------------------------------------------

def _make_mock_user(account: int = 123, account_name: str = "test_user"):
    """Создать мок объекта пользователя."""
    user = MagicMock()
    user.account = account
    user.account_name = account_name
    return user


def _make_mock_key(
    outline_id: str = "42",
    region_server: str = "nederland",
    access_url: str = "ss://test-url",
    premium: bool = True,
    promo: bool = False,
    days_offset: int = 30,
):
    """Создать мок объекта UserKey."""
    key = MagicMock()
    key.id = "123_key_abcdef12"
    key.outline_id = outline_id
    key.region_server = region_server
    key.access_url = access_url
    key.premium = premium
    key.promo = promo
    key.date = datetime.now() + timedelta(days=days_offset)
    return key


def _make_mock_outline_key(key_id: int = 42, access_url: str = "ss://test-url"):
    """Создать мок объекта Outline ключа."""
    k = MagicMock()
    k.key_id = key_id
    k.access_url = access_url
    return k


# ---------------------------------------------------------------------------
# Тесты KeyService.get_least_busy_server
# ---------------------------------------------------------------------------

class TestGetLeastBusyServer:
    @pytest.mark.asyncio
    async def test_returns_least_loaded_server(self):
        """Должен возвращать сервер с наименьшей нагрузкой."""
        from core.services.key_service import KeyService

        svc = KeyService()
        mock_key_nl = _make_mock_key(region_server="nederland", premium=True)
        mock_key_de = _make_mock_key(region_server="germany", premium=True)

        with patch(
            "core.services.key_service.get_user_keys",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.services.key_service.get_name_all_active_server_ol",
            return_value=["nederland", "germany"],
        ), patch(
            "core.services.key_service.get_all_user_keys",
            new_callable=AsyncMock,
            return_value=[mock_key_nl, mock_key_nl, mock_key_de],
        ):
            result = await svc.get_least_busy_server(user_id=999)

        assert result == "germany"

    @pytest.mark.asyncio
    async def test_fallback_on_no_servers(self):
        """При отсутствии серверов должен вернуть 'nederland' по умолчанию."""
        from core.services.key_service import KeyService

        svc = KeyService()

        with patch(
            "core.services.key_service.get_user_keys",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.services.key_service.get_name_all_active_server_ol",
            return_value=[],
        ), patch(
            "core.services.key_service.get_all_user_keys",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await svc.get_least_busy_server(user_id=999)

        assert result == "nederland"

    @pytest.mark.asyncio
    async def test_excludes_user_existing_servers(self):
        """Должен исключить серверы, на которых у пользователя уже есть ключи."""
        from core.services.key_service import KeyService

        svc = KeyService()
        user_key = _make_mock_key(region_server="nederland")

        with patch(
            "core.services.key_service.get_user_keys",
            new_callable=AsyncMock,
            return_value=[user_key],
        ), patch(
            "core.services.key_service.get_name_all_active_server_ol",
            return_value=["nederland", "germany"],
        ), patch(
            "core.services.key_service.get_all_user_keys",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await svc.get_least_busy_server(user_id=123)

        assert result == "germany"


# ---------------------------------------------------------------------------
# Тесты KeyService.create_promo_key
# ---------------------------------------------------------------------------

class TestCreatePromoKey:
    @pytest.mark.asyncio
    async def test_success(self):
        """Успешное создание промо-ключа."""
        from core.services.key_service import KeyService

        svc = KeyService()
        mock_user = _make_mock_user()
        mock_outline_key = _make_mock_outline_key()

        mock_olm = MagicMock()
        mock_olm._client.create_key.return_value = mock_outline_key

        with patch(
            "core.services.key_service.get_user_data_from_table_users",
            new_callable=AsyncMock,
            return_value=mock_user,
        ), patch.object(svc, "get_least_busy_server", new_callable=AsyncMock, return_value="nederland"), patch(
            "core.services.key_service.OutlineManager",
            return_value=mock_olm,
        ), patch(
            "core.services.key_service.add_user_key",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "core.services.key_service.set_premium_status",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.set_date_to_table_users",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.set_region_server",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.set_key_to_table_users",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.set_promo_status",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.get_server_display_name",
            return_value="🇳🇱 Нидерланды",
        ):
            result = await svc.create_promo_key(user_id=123, days=7)

        assert result["success"] is True
        assert result["days"] == 7
        assert result["server"] == "nederland"
        mock_olm._client.create_key.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        """Если пользователь не найден — вернуть ошибку."""
        from core.services.key_service import KeyService

        svc = KeyService()

        with patch(
            "core.services.key_service.get_user_data_from_table_users",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await svc.create_promo_key(user_id=999)

        assert result["success"] is False
        assert "не найден" in result["error"]

    @pytest.mark.asyncio
    async def test_outline_key_creation_fails(self):
        """Если Outline API не создал ключ — вернуть ошибку."""
        from core.services.key_service import KeyService

        svc = KeyService()
        mock_user = _make_mock_user()
        mock_olm = MagicMock()
        mock_olm._client.create_key.return_value = None

        with patch(
            "core.services.key_service.get_user_data_from_table_users",
            new_callable=AsyncMock,
            return_value=mock_user,
        ), patch.object(
            svc, "get_least_busy_server", new_callable=AsyncMock, return_value="nederland"
        ), patch(
            "core.services.key_service.OutlineManager",
            return_value=mock_olm,
        ):
            result = await svc.create_promo_key(user_id=123, days=7)

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_custom_server_used(self):
        """Если сервер передан явно — использовать его."""
        from core.services.key_service import KeyService

        svc = KeyService()
        mock_user = _make_mock_user()
        mock_outline_key = _make_mock_outline_key()
        mock_olm = MagicMock()
        mock_olm._client.create_key.return_value = mock_outline_key

        with patch(
            "core.services.key_service.get_user_data_from_table_users",
            new_callable=AsyncMock,
            return_value=mock_user,
        ), patch(
            "core.services.key_service.OutlineManager",
            return_value=mock_olm,
        ), patch(
            "core.services.key_service.add_user_key",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "core.services.key_service.set_premium_status",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.set_date_to_table_users",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.set_region_server",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.set_key_to_table_users",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.set_promo_status",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.get_server_display_name",
            return_value="🇩🇪 Германия",
        ):
            result = await svc.create_promo_key(user_id=123, days=7, server="germany")

        assert result["success"] is True
        assert result["server"] == "germany"


# ---------------------------------------------------------------------------
# Тесты KeyService.replace_key
# ---------------------------------------------------------------------------

class TestReplaceKey:
    @pytest.mark.asyncio
    async def test_success(self):
        """Успешная замена ключа."""
        from core.services.key_service import KeyService

        svc = KeyService()
        mock_user = _make_mock_user()
        active_key = _make_mock_key(
            outline_id="old-id",
            region_server="nederland",
            days_offset=10,
        )
        new_outline_key = _make_mock_outline_key(key_id=99, access_url="ss://new-url")
        mock_olm_new = MagicMock()
        mock_olm_new._client.create_key.return_value = new_outline_key
        mock_olm_old = MagicMock()

        with patch(
            "core.services.key_service.get_user_data_from_table_users",
            new_callable=AsyncMock,
            return_value=mock_user,
        ), patch(
            "core.services.key_service.get_user_keys",
            new_callable=AsyncMock,
            return_value=[active_key],
        ), patch(
            "core.services.key_service.get_name_all_active_server_ol",
            return_value=["nederland", "germany"],
        ), patch(
            "core.services.key_service.get_all_user_keys",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.services.key_service.OutlineManager",
            side_effect=[mock_olm_new, mock_olm_old],
        ), patch(
            "core.services.key_service.add_user_key",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "core.services.key_service.set_premium_status",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.set_date_to_table_users",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.set_region_server",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.set_key_to_table_users",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.delete_user_key_record",
            new_callable=AsyncMock,
        ), patch(
            "core.services.key_service.get_server_display_name",
            return_value="🇩🇪 Германия",
        ):
            result = await svc.replace_key(user_id=123)

        assert result["success"] is True
        assert result["new_server"] == "germany"
        assert result["old_server"] == "nederland"
        assert result["new_access_url"] == "ss://new-url"

    @pytest.mark.asyncio
    async def test_no_active_keys(self):
        """Если нет активных ключей — вернуть ошибку."""
        from core.services.key_service import KeyService

        svc = KeyService()
        mock_user = _make_mock_user()

        with patch(
            "core.services.key_service.get_user_data_from_table_users",
            new_callable=AsyncMock,
            return_value=mock_user,
        ), patch(
            "core.services.key_service.get_user_keys",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await svc.replace_key(user_id=123)

        assert result["success"] is False
        assert "Нет активных ключей" in result["error"]

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        """Если пользователь не найден — вернуть ошибку."""
        from core.services.key_service import KeyService

        svc = KeyService()

        with patch(
            "core.services.key_service.get_user_data_from_table_users",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await svc.replace_key(user_id=999)

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_no_available_servers(self):
        """Если нет других серверов — вернуть ошибку."""
        from core.services.key_service import KeyService

        svc = KeyService()
        mock_user = _make_mock_user()
        active_key = _make_mock_key(region_server="nederland", days_offset=10)

        with patch(
            "core.services.key_service.get_user_data_from_table_users",
            new_callable=AsyncMock,
            return_value=mock_user,
        ), patch(
            "core.services.key_service.get_user_keys",
            new_callable=AsyncMock,
            return_value=[active_key],
        ), patch(
            "core.services.key_service.get_name_all_active_server_ol",
            return_value=["nederland"],
        ), patch(
            "core.services.key_service.get_all_user_keys",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await svc.replace_key(user_id=123)

        assert result["success"] is False
        assert "серверов" in result["error"]


# ---------------------------------------------------------------------------
# Тесты KeyService.get_key_info
# ---------------------------------------------------------------------------

class TestGetKeyInfo:
    @pytest.mark.asyncio
    async def test_returns_active_and_expired(self):
        """Должен разделять активные и просроченные ключи."""
        from core.services.key_service import KeyService

        svc = KeyService()
        active_key = _make_mock_key(days_offset=10, premium=True)
        expired_key = _make_mock_key(days_offset=-1, premium=False)

        with patch(
            "core.services.key_service.get_user_keys",
            new_callable=AsyncMock,
            return_value=[active_key, expired_key],
        ), patch(
            "core.services.key_service.get_server_display_name",
            return_value="🇳🇱 Нидерланды",
        ):
            result = await svc.get_key_info(user_id=123)

        assert result["success"] is True
        assert result["total_active"] == 1
        assert result["total_expired"] == 1

    @pytest.mark.asyncio
    async def test_empty_keys(self):
        """При отсутствии ключей должен вернуть пустые списки."""
        from core.services.key_service import KeyService

        svc = KeyService()

        with patch(
            "core.services.key_service.get_user_keys",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await svc.get_key_info(user_id=123)

        assert result["success"] is True
        assert result["total_active"] == 0
        assert result["total_expired"] == 0


# ---------------------------------------------------------------------------
# Тесты KeyService.delete_key
# ---------------------------------------------------------------------------

class TestDeleteKey:
    @pytest.mark.asyncio
    async def test_success(self):
        """Успешное удаление ключа."""
        from core.services.key_service import KeyService

        svc = KeyService()
        target_key = _make_mock_key(outline_id="del-id")
        mock_olm = MagicMock()

        with patch(
            "core.services.key_service.get_user_keys",
            new_callable=AsyncMock,
            return_value=[target_key],
        ), patch(
            "core.services.key_service.OutlineManager",
            return_value=mock_olm,
        ), patch(
            "core.services.key_service.delete_user_key_record",
            new_callable=AsyncMock,
        ):
            result = await svc.delete_key(user_id=123, outline_id="del-id")

        assert result["success"] is True
        assert result["deleted"] is True

    @pytest.mark.asyncio
    async def test_key_not_found(self):
        """Если ключ не найден — вернуть ошибку."""
        from core.services.key_service import KeyService

        svc = KeyService()

        with patch(
            "core.services.key_service.get_user_keys",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await svc.delete_key(user_id=123, outline_id="missing-id")

        assert result["success"] is False
        assert "не найден" in result["error"]
