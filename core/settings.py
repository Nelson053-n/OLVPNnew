from dotenv import load_dotenv
import os


# Загружаем переменные окружения из .env; если пусто — пытаемся из core/TEMP.env
load_dotenv()
if not os.getenv("API_KEY_TLG") or not os.getenv("ADMIN_TLG"):
    temp_env_path = os.path.join(os.path.dirname(__file__), "TEMP.env")
    if os.path.exists(temp_env_path):
        load_dotenv(temp_env_path, override=False)

# Для бота tlg
api_key_tlg = os.getenv("API_KEY_TLG")
admin_tlg = os.getenv("ADMIN_TLG")

# Для сервера outline — в json (core/api_s/outline/settings_api_outline.json)

# Для юкасса
client_id = os.getenv("YOUKASSA_ID")
secret_key = os.getenv("YOUKASSA_SECRET")

# В продакшене не запрашиваем ввод. Падаем с понятной ошибкой, если чего-то не хватает.
missing = []
if not api_key_tlg:
    missing.append("API_KEY_TLG")
if not admin_tlg:
    missing.append("ADMIN_TLG")
if not client_id:
    missing.append("YOUKASSA_ID")
if not secret_key:
    missing.append("YOUKASSA_SECRET")

if missing:
    raise RuntimeError(
        "Отсутствуют переменные окружения: " + ", ".join(missing) +
        ". Заполните файл .env (или core/TEMP.env для локального запуска) и перезапустите."
    )

