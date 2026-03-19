import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Абсолютный путь к шаблонам (работает из любого рабочего каталога)
ROOT_TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')

_env = Environment(
    loader=FileSystemLoader(ROOT_TEMPLATES),
    autoescape=select_autoescape(['html'], default=True),
)

_FALLBACK_ERROR = "Произошла ошибка. Попробуйте позже."


async def create_answer_from_html(name_temp: str, **kwargs) -> str:
    """
    Генерация ответа из шаблонов html

    :param name_temp: str - строка с названием шаблона
    :param kwargs: dict - параметры для передачи в шаблон
    :return str - строка с ответом из шаблона
    """
    page = name_temp.removeprefix('/')
    try:
        template = _env.get_template(f"{page}.html")
        return template.render(**kwargs)
    except Exception:
        if page != "error":
            try:
                template = _env.get_template("error.html")
                return template.render(**kwargs)
            except Exception:
                pass
        return _FALLBACK_ERROR
