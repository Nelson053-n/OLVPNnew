from os.path import join
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT_TEMPLATES = 'core/templates'  # Папка с шаблонами

_env = Environment(
    loader=FileSystemLoader(ROOT_TEMPLATES),
    autoescape=select_autoescape(['html'], default=True),
)


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
        html_content = template.render(**kwargs)
    except Exception:
        html_content = await create_answer_from_html("error", **kwargs)
    finally:
        return html_content
