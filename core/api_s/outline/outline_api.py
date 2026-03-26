import json
import os

from outline_vpn.outline_vpn import OutlineVPN, OutlineServerErrorException

_CONFIG_FILE = 'core/api_s/outline/settings_api_outline.json'

# Кеш JSON-конфига серверов с проверкой mtime
_server_config_cache: dict | None = None
_server_config_mtime: float = 0


def _load_server_config() -> dict:
    """Кеш JSON-конфига серверов с проверкой mtime файла."""
    global _server_config_cache, _server_config_mtime
    try:
        current_mtime = os.path.getmtime(_CONFIG_FILE)
    except OSError:
        current_mtime = 0
    if _server_config_cache is not None and current_mtime == _server_config_mtime:
        return _server_config_cache
    with open(_CONFIG_FILE, 'r') as f:
        _server_config_cache = json.load(f)
    _server_config_mtime = current_mtime
    return _server_config_cache


# Кеш экземпляров OutlineManager по region_server
_outline_manager_cache: dict[str, "OutlineManager"] = {}


def invalidate_outline_cache(region_server: str = None) -> None:
    """Сбросить кеш после изменения конфига серверов."""
    global _server_config_cache, _server_config_mtime
    _server_config_cache = None
    _server_config_mtime = 0
    if region_server:
        _outline_manager_cache.pop(region_server, None)
    else:
        _outline_manager_cache.clear()


def get_name_all_active_server_ol() -> list:
    """
    Получение всех активных серверов

    :return: list - name_en всех активных серверов
    """
    config = _load_server_config()
    return [v['name_en'] for v in config.values() if v['is_active']]


def get_server_display_name(region_server: str) -> str:
    """
    Получить отображаемое имя сервера с флагом страны

    :param region_server: название региона (name_en)
    :return: отображаемое имя с флагом (name_ru)
    """
    try:
        config = _load_server_config()
        if region_server in config:
            return config[region_server].get('name_ru', region_server)
        return region_server
    except Exception:
        return region_server


class OutlineManager:
    """
    Класс для управления ключами в Outline VPN.
    Singleton по region_server — один экземпляр на каждый сервер.
    """

    def __new__(cls, region_server: str = 'nederland'):
        if region_server in _outline_manager_cache:
            return _outline_manager_cache[region_server]
        instance = super().__new__(cls)
        instance._initialized = False
        _outline_manager_cache[region_server] = instance
        return instance

    def __init__(self, region_server: str = 'nederland'):
        if self._initialized:
            return
        self._initialized = True
        self.region_server = region_server
        self._client = self.__client_init()

    def __client_init(self) -> OutlineVPN:
        """
        Инициализация клиента

        :return: OutlineVPN - Объект OutlineVPN
        """
        config = _load_server_config()
        data_server = config[self.region_server]
        api_url = data_server['api_url']
        cert_sha256 = data_server['cert_sha256']
        return OutlineVPN(api_url=api_url,
                          cert_sha256=cert_sha256)

    def get_key_from_ol(self, id_user: str) -> str | None:
        """
        Получить ключ для указанного пользователя.

        Args:
        - id_user: str - Идентификатор пользователя.
        Returns:
        - str or None: Ключ пользователя или None, если ключ не найден.
        """
        try:
            key = self._client.get_key(id_user)
        except OutlineServerErrorException:
            key = None
        return key

    def create_key_from_ol(self, id_user: str) -> dict:
        """
        Создать новый ключ для пользователя.

        Args:
        - id_user: str - Идентификатор пользователя.

        Returns:
        - dict: Информация о созданном ключе.
        """
        return self._client.create_key(key_id=id_user, name=id_user)

    def delete_key_from_ol(self, id_user: str) -> bool:
        """
        Удалить ключ указанного пользователя.

        Args:
        - id_user: str - Идентификатор пользователя.

        Returns:
        - bool: True, если ключ успешно удален, False в противном случае.
        """
        key = self.get_key_from_ol(id_user=id_user)
        if key is None:
            return False
        return self._client.delete_key(key.key_id)

    # --- Multiple keys support ---
    def get_key_by_id(self, outline_id: str) -> str | None:
        """
        Получить ключ по его уникальному идентификатору outline_id.

        Args:
        - outline_id: str - Уникальный идентификатор ключа в Outline.
        Returns:
        - Key or None
        """
        try:
            key = self._client.get_key(outline_id)
        except OutlineServerErrorException:
            key = None
        return key

    def delete_key_by_id(self, outline_id: str) -> bool:
        """
        Удалить ключ по его уникальному идентификатору outline_id.

        Args:
        - outline_id: str - Уникальный идентификатор ключа в Outline.

        Returns:
        - bool: True, если удаление прошло успешно, иначе False.
        """
        try:
            # Попытка прямого удаления; большинство API допускают удаление по key_id
            return self._client.delete_key(outline_id)
        except OutlineServerErrorException:
            # Пытаемся проверить существование ключа; если его нет — считаем удалённым
            try:
                key = self._client.get_key(outline_id)
                if not key:
                    return True
            except OutlineServerErrorException:
                return True
            return False


if __name__ == "__main__":
    ol = OutlineManager()
