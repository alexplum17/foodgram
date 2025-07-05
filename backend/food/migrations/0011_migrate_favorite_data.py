from django.db import migrations


def transfer_favorite_data(apps, schema_editor):
    Favorite = apps.get_model('food', 'Favorite')
    for fav in Favorite.objects.all():
        if hasattr(fav, 'favorite'):
            fav.recipe = fav.favorite
            fav.save()

def reverse_transfer(apps, schema_editor):
    Favorite = apps.get_model('food', 'Favorite')
    for fav in Favorite.objects.all():
        if hasattr(fav, 'recipe'):
            fav.favorite_id = fav.recipe_id
            fav.save()

class Migration(migrations.Migration):
    dependencies = [
        ('food', '0010_remove_profile_user_alter_favorite_options_and_more'),
    ]

    operations = [
        migrations.RunPython(transfer_favorite_data, reverse_transfer),
    ]