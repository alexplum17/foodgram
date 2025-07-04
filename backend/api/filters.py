"""backend/api/filters.py."""

from django_filters import rest_framework as filters
from food.models import Recipe, Tag
from rest_framework import filters as drf_filters


class RecipeFilter(filters.FilterSet):
    """Фильтр для рецептов."""

    tags = filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all(),
    )
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart'
    )

    class Meta:
        """Мета-класс для RecipeFilter."""

        model = Recipe
        fields = ['author', 'tags', 'is_favorited', 'is_in_shopping_cart']

    def filter_is_favorited(self, queryset, name, value):
        """Фильтрует рецепты в избранном."""
        if value and self.request.user.is_authenticated:
            return queryset.filter(favorite_recipe__user=self.request.user)
        return queryset

    def filter_is_in_shopping_cart(self, queryset, name, value):
        """Фильтрует рецепты в списке покупок."""
        if value and self.request.user.is_authenticated:
            return queryset.filter(shoppingcart_recipe__user=self.request.user)
        return queryset


class IngredientSearchFilter(drf_filters.SearchFilter):
    """Фильтр для поиска ингредиентов по начальным буквам названия."""

    def filter_queryset(self, request, queryset, view):
        """Фильтрует queryset по параметру 'name'."""
        search_query = self.get_search_terms(request)
        if not search_query:
            return queryset
        search_term = search_query[0]
        return queryset.filter(name__istartswith=search_term)
