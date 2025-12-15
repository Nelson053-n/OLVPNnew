import json
from pathlib import Path
from core.api_s.outline.outline_api import OutlineManager


# Маппинг стран на флаги (по кодам ISO 3166-1 Alpha-2)
COUNTRY_FLAGS = {
    "netherlands": "🇳🇱",
    "germany": "🇩🇪",
    "france": "🇫🇷",
    "usa": "🇺🇸",
    "united states": "🇺🇸",
    "uk": "🇬🇧",
    "united kingdom": "🇬🇧",
    "canada": "🇨🇦",
    "australia": "🇦🇺",
    "japan": "🇯🇵",
    "russia": "🇷🇺",
    "china": "🇨🇳",
    "india": "🇮🇳",
    "brazil": "🇧🇷",
    "mexico": "🇲🇽",
    "spain": "🇪🇸",
    "italy": "🇮🇹",
    "poland": "🇵🇱",
    "sweden": "🇸🇪",
    "norway": "🇳🇴",
    "denmark": "🇩🇰",
    "finland": "🇫🇮",
    "greece": "🇬🇷",
    "portugal": "🇵🇹",
    "turkey": "🇹🇷",
    "switzerland": "🇨🇭",
    "austria": "🇦🇹",
    "belgium": "🇧🇪",
    "ireland": "🇮🇪",
    "singapore": "🇸🇬",
    "hong kong": "🇭🇰",
    "south korea": "🇰🇷",
    "thailand": "🇹🇭",
    "vietnam": "🇻🇳",
    "philippines": "🇵🇭",
    "indonesia": "🇮🇩",
    "malaysia": "🇲🇾",
}


def get_country_flag(country_name: str) -> str:
    """
    Возвращает флаг страны по её названию
    Ищет в словаре, игнорируя регистр

    :param country_name: str - название страны
    :return: str - флаг страны или "🌍" если не найдена
    """
    country_lower = country_name.lower().strip()
    return COUNTRY_FLAGS.get(country_lower, "🌍")


def get_server_key_from_name(name: str) -> str:
    """
    Генерирует ключ для сервера (для использования в JSON) из названия страны
    Преобразует в нижний регистр и удаляет пробелы

    :param name: str - название страны
    :return: str - ключ для JSON
    """
    return name.lower().replace(" ", "_").strip()


async def add_server_to_config(
    country_name: str,
    api_url: str,
    cert_sha256: str,
    max_keys: int = 100,
    is_active: bool = True
) -> bool:
    """
    Добавляет новый сервер в settings_api_outline.json

    :param country_name: str - название страны
    :param api_url: str - URL API Outline сервера
    :param cert_sha256: str - SHA256 сертификата сервера
    :param max_keys: int - максимальное количество выдаваемых ключей (по умолчанию 100)
    :param is_active: bool - активен ли сервер при добавлении
    :return: bool - успешно ли добавлена запись
    """
    config_file = Path('core/api_s/outline/settings_api_outline.json')

    try:
        # Читаем существующий конфиг
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Генерируем ключ сервера
        server_key = get_server_key_from_name(country_name)

        # Проверяем, что такого сервера ещё нет
        if server_key in config:
            return False  # Сервер уже существует

        # Получаем флаг страны
        flag = get_country_flag(country_name)
        name_ru = f"{flag} {country_name.title()}"
        name_en = server_key

        # Добавляем новый сервер
        config[server_key] = {
            "name_en": name_en,
            "name_ru": name_ru,
            "api_url": api_url,
            "cert_sha256": cert_sha256,
            "max_keys": max_keys,
            "is_active": is_active
        }

        # Сохраняем обновленный конфиг
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

        return True

    except Exception as e:
        return False


async def check_server_key_limit(region_server: str) -> tuple[bool, int, int]:
    """
    Проверяет, не превышен ли лимит ключей для сервера

    :param region_server: str - название региона сервера
    :return: tuple[bool, int, int] - (доступен ли сервер, текущее кол-во ключей, лимит)
    """
    config_file = Path('core/api_s/outline/settings_api_outline.json')

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Получаем максимальное количество ключей для сервера
        server_key = get_server_key_from_name(region_server)
        if server_key not in config:
            return False, 0, 0

        max_keys = config[server_key].get('max_keys', 100)

        # Получаем текущее количество ключей на сервере
        try:
            olm = OutlineManager(region_server=region_server)
            all_keys = olm._client.get_keys()
            current_keys = len(all_keys)

            # Проверяем, не превышен ли лимит
            is_available = current_keys < max_keys

            return is_available, current_keys, max_keys

        except Exception as e:
            # Если ошибка получения ключей, считаем сервер недоступным
            return False, 0, max_keys

    except Exception as e:
        return False, 0, 0
