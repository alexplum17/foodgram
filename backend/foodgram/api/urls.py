from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import (
    FavoriteViewSet,
    FollowViewSet,
    IngredientViewSet,
    RecipeViewSet,
    ShoppingCartViewSet,
    TagViewSet,
    UserViewSet,
)

app_name = 'api'
router = DefaultRouter()
router.register('users', UserViewSet, basename='users')
router.register('tags', TagViewSet, basename='tags')
router.register('ingredients', IngredientViewSet, basename='ingredients')
router.register('recipes', RecipeViewSet, basename='recipes')

urlpatterns = [
    path('', include(router.urls)),
    path('', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
    path('recipes/<int:id>/favorite/', FavoriteViewSet.as_view({
        'post': 'create',
        'delete': 'destroy'
    }), name='favorite'),
    path('recipes/<int:id>/shopping_cart/', ShoppingCartViewSet.as_view({
        'post': 'create',
        'delete': 'destroy'
    }), name='shopping_cart'),
    path('users/subscriptions/', FollowViewSet.as_view({
        'get': 'list'
    }), name='subscriptions'),
    path('users/<int:id>/subscribe/', FollowViewSet.as_view({
        'post': 'create',
        'delete': 'destroy'
    }), name='subscribe'),
    path('recipes/download_shopping_cart/', ShoppingCartViewSet.as_view({
        'get': 'download'
    }), name='download_shopping_cart'),
]
