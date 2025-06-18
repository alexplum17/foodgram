"""backend/food/apps.py."""

from django.apps import AppConfig


class FoodConfig(AppConfig):
    """Конфигурация приложения Food."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'food'
    verbose_name = 'Фудграм'
