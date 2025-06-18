"""backend/food/admin.py."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from food.models import (
    Favorite,
    Follow,
    Ingredient,
    Profile,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
    User,
)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Админ-панель для управления тегами."""

    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')
    empty_value_display = '-пусто-'


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    """Админ-панель для управления ингредиентами."""

    list_display = ('name', 'measurement_unit')
    search_fields = ('name',)
    empty_value_display = '-пусто-'


class RecipeIngredientInline(admin.TabularInline):
    """Inline-админ для связи рецептов и ингредиентов."""

    model = RecipeIngredient
    extra = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Админ-панель для управления рецептами."""

    list_display = ('name', 'author', 'favorite_count')
    search_fields = ('name', 'author__username')
    list_filter = ('tags',)
    inlines = (RecipeIngredientInline,)
    filter_horizontal = ('tags',)
    empty_value_display = '-пусто-'

    def favorite_count(self, obj):
        """Возвращает количество добавлений рецепта в избранное."""
        return obj.favorite.count()
    favorite_count.short_description = 'Добавлений в избранное'


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    """Админ-панель для связи рецептов и ингредиентов."""

    list_display = ('recipe', 'ingredient', 'amount')
    search_fields = ('recipe__name', 'ingredient__name')
    empty_value_display = '-пусто-'


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Админ-панель для профилей пользователей."""

    list_display = ('user',)
    search_fields = ('user__username', 'user__email')
    empty_value_display = '-пусто-'


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    """Админ-панель для подписок пользователей."""

    list_display = ('user', 'following')
    search_fields = ('user__username', 'following__username')
    empty_value_display = '-пусто-'


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """Админ-панель для избранных рецептов."""

    list_display = ('user', 'favorite')
    search_fields = ('user__username', 'favorite__name')
    empty_value_display = '-пусто-'


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    """Админ-панель для списка покупок."""

    list_display = ('user', 'recipe')
    search_fields = ('user__username', 'recipe__name')
    empty_value_display = '-пусто-'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Админ-панель для пользователей."""

    list_display = ('username',
                    'email',
                    'first_name',
                    'last_name',
                    'is_staff',
                    'is_active'
                    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_active')
    empty_value_display = '-пусто-'

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields':
                         ('is_active', 'is_staff', 'is_superuser',
                          'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name',
                       'last_name', 'password1', 'password2'),
        }),
    )
