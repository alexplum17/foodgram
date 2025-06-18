"""backend/import_data.py."""

import csv
import os

import django
from food.models import Ingredient

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodgram.settings')
django.setup()


def import_csv(filename):
    """Импортирует данные из CSV-файла в модель Ingredient."""
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            Ingredient.objects.get_or_create(
                name=row[0].strip(),
                measurement_unit=row[1].strip(),
            )


if __name__ == '__main__':
    import_csv('foodgram/ingredients.csv')
