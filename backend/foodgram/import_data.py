import csv
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodgram.settings')
django.setup()

from food.models import Ingredient


def import_csv(filename):
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
