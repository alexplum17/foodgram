"""backend/api/urls.py."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import (
                       FollowViewSet,
                       IngredientViewSet,
                       RecipeViewSet,
                       TagViewSet,
                       UserViewSet,
)

app_name = 'api'
router = DefaultRouter()
router.register('users', UserViewSet, basename='users')
router.register('tags', TagViewSet, basename='tags')
router.register('ingredients', IngredientViewSet, basename='ingredients')
router.register('recipes', RecipeViewSet, basename='recipes')
router.register(
    r'users/(?P<id>\d+)/subscribe',
    FollowViewSet,
    basename='subscribe'
)

urlpatterns = [
    path('users/subscriptions/', FollowViewSet.as_view({'get': 'list'}), name='subscriptions'),
    path('users/<int:id>/subscribe/', FollowViewSet.as_view({
        'post': 'create'}), name='subscribe'),
    path('', include(router.urls)),
    path('', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
]
