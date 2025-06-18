"""backend/food/utils.py."""

import logging

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """Кастомный обработчик исключений для API."""
    response = exception_handler(exc, context)
    if response is None and isinstance(exc, ObjectDoesNotExist):
        exc = NotFound(detail='Объект не найден')
        response = exception_handler(exc, context)
    if response and response.status_code == status.HTTP_404_NOT_FOUND:
        response.data = {
            "detail": 'Объект не найден'
        }
        logger.debug(f"404 Not Found - {context['request'].method}"
                     "{context['request'].path}")
    return response
