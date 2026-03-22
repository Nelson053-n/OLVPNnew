import json
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent.parent / 'api_s' / 'outline' / 'settings_api_outline.json'


async def get_region_name_from_json(region: str) -> str or None:
    """
    Получение названия сервера на русском, в читаемом формате
    Из файла settings_api_outline.json

    :param region: str - Название региона в формате для бота
    :return: str - строка с названием региона сервера либо None если нет
    """
    config_file = CONFIG_FILE
    with open(config_file, 'r') as f:
        config = json.load(f)
    for key, value in config.items():
        if value['name_en'] == region:
            return value['name_ru']
    return None
