from django import template
from django.conf import settings
from django.utils.html import mark_safe
from django.contrib.messages import DEBUG, INFO, SUCCESS, WARNING, ERROR

from markdown import markdown

register = template.Library()

MESSAGE_LEVEL_TO_CSS_CLASS = {
    INFO: 'primary',
    SUCCESS: 'success',
    WARNING: 'warning',
    ERROR: 'danger',
    DEBUG: 'secondary',
}


@register.simple_tag
def level_to_bootstrap_css_class(level: int) -> str:
    return MESSAGE_LEVEL_TO_CSS_CLASS.get(level) or 'primary'


@register.simple_tag
def render_markdown(content: str) -> str:
    return mark_safe(markdown(content, output_format='html5'))


@register.simple_tag
def get_env_css_class() -> str:
    css_class = f'environment-{settings.ENVIRONMENT}'
    if settings.DEBUG:
        css_class = f"{css_class} debug-enabled"

    return mark_safe(css_class)
