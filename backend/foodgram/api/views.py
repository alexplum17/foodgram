from io import BytesIO

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from djoser.views import UserViewSet as DjoserUserViewSet
from food.models import Favorite, Follow, Ingredient, Recipe, ShoppingCart, Tag
from reportlab.pdfgen import canvas
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from api.serializers import (
    AvatarUpdateSerializer,
    FavoriteSerializer,
    FollowSerializer,
    IngredientSerializer,
    RecipeSerializer,
    ShoppingCartSerializer,
    TagSerializer,
    UserSerializer,
)

User = get_user_model()


class UserViewSet(DjoserUserViewSet):
    http_method_names = ['get', 'post', 'put', 'del']
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        if self.action in ['create', 'set_password']:
            return super().get_serializer_class()
        return UserSerializer

    @action(['post'], detail=False)
    def set_password(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.request.user.set_password(serializer.data['new_password'])
        self.request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['put', 'delete'], url_path='me/avatar')
    def avatar(self, request):
        user = request.user
        if request.method == 'PUT':
            serializer = AvatarUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            serializer.update(user, serializer.validated_data)
            return Response(
                {'avatar': user.profile.avatar.url},
                status=status.HTTP_200_OK
            )
        elif request.method == 'DELETE':
            if not user.profile.avatar:
                return Response(
                    {"detail": "Аватар не найден"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.profile.avatar.delete()
            user.profile.avatar = None
            user.profile.save()
            return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(viewsets.ModelViewSet):
    """ViewSet для управления тегами."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = PageNumberPagination
    http_method_names = ['get']


class IngredientViewSet(viewsets.ModelViewSet):
    """ViewSet для управления ингридиентами."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = PageNumberPagination
    http_method_names = ['get']
    search_fields = ['=name']

    def get_queryset(self):
        queryset = self.queryset
        search_query = self.request.query_params.get('query', None)
        if search_query:
            queryset = queryset.filter(name__startswith=search_query)
        return queryset


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    pagination_class = PageNumberPagination
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        is_favorited = self.request.query_params.get('is_favorited')
        if is_favorited and user.is_authenticated:
            if is_favorited == '1':
                queryset = queryset.filter(favorite__user=user)
            elif is_favorited == '0':
                queryset = queryset.exclude(favorite__user=user)
        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart'
        )
        if is_in_shopping_cart and user.is_authenticated:
            if is_in_shopping_cart == '1':
                queryset = queryset.filter(shopping_cart__user=user)
            elif is_in_shopping_cart == '0':
                queryset = queryset.exclude(shopping_cart__user=user)
        author_id = self.request.query_params.get('author')
        if author_id:
            queryset = queryset.filter(author_id=author_id)
        tags = self.request.query_params.getlist('tags')
        if tags:
            queryset = queryset.filter(tags__slug__in=tags).distinct()
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({'request': self.request})
        return context


class FollowViewSet(viewsets.ModelViewSet):
    queryset = Follow.objects.all()
    serializer_class = FollowSerializer
    pagination_class = PageNumberPagination
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        return Follow.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        following_id = kwargs.get('id')
        following = get_object_or_404(User, id=following_id)

        if request.user == following:
            return Response(
                {'errors': 'Нельзя подписаться на самого себя'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if Follow.objects.filter(
            user=request.user, following=following
        ).exists():
            return Response(
                {'errors': 'Вы уже подписаны на этого пользователя'},
                status=status.HTTP_400_BAD_REQUEST
            )
        follow = Follow.objects.create(user=request.user, following=following)
        serializer = self.get_serializer(follow)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        following_id = kwargs.get('id')
        following = get_object_or_404(User, id=following_id)
        follow = Follow.objects.filter(
            user=request.user,
            following=following
        ).first()
        if not follow:
            return Response(
                {'errors': 'Вы не подписаны на этого пользователя'},
                status=status.HTTP_400_BAD_REQUEST
            )
        follow.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShoppingCartViewSet(viewsets.ModelViewSet):
    queryset = ShoppingCart.objects.all()
    serializer_class = ShoppingCartSerializer
    http_method_names = ['get', 'post', 'delete']

    def create(self, request, *args, **kwargs):
        recipe_id = kwargs.get('id')
        recipe = get_object_or_404(Recipe, id=recipe_id)
        if ShoppingCart.objects.filter(user=request.user, recipe=recipe).exists():
            return Response(
                {'errors': 'Рецепт уже в списке покупок'},
                status=status.HTTP_400_BAD_REQUEST
            )
        shopping_cart = ShoppingCart.objects.create(
            user=request.user,
            recipe=recipe
        )
        serializer = self.get_serializer(shopping_cart)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        recipe_id = kwargs.get('id')
        recipe = get_object_or_404(Recipe, id=recipe_id)

        shopping_cart = ShoppingCart.objects.filter(
            user=request.user,
            recipe=recipe
        ).first()
        if not shopping_cart:
            return Response(
                {'errors': 'Рецепта нет в списке покупок'},
                status=status.HTTP_400_BAD_REQUEST
            )
        shopping_cart.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def download(self, request):
        user = request.user
        shopping_cart = user.shopping_cart.all()
        ingredients = {}
        for item in shopping_cart:
            for ri in item.recipe.recipe_ingredients.all():
                key = (ri.ingredient.name, ri.ingredient.measurement_unit)
                if key in ingredients:
                    ingredients[key] += ri.quantity
                else:
                    ingredients[key] = ri.quantity
        format = request.query_params.get('format', 'txt')
        if format == 'txt':
            response = HttpResponse(content_type='text/plain')
            response[
                'Content-Disposition'
            ] = 'attachment; filename="shopping_list.txt"'

            text = 'Список покупок:\n\n'
            for (name, unit), amount in ingredients.items():
                text += f"- {name} ({unit}) — {amount}\n"
            response.write(text)
            return response
        elif format == 'pdf':
            buffer = BytesIO()
            p = canvas.Canvas(buffer)
            p.drawString(100, 800, 'Список покупок:')
            y = 780
            for (name, unit), amount in ingredients.items():
                p.drawString(100, y, f"- {name} ({unit}) — {amount}")
                y -= 20
            p.showPage()
            p.save()
            pdf = buffer.getvalue()
            buffer.close()
            response = HttpResponse(content_type='application/pdf')
            response[
                'Content-Disposition'
            ] = 'attachment; filename="shopping_list.pdf"'
            response.write(pdf)
            return response
        return Response({'error': 'Неподдерживаемый формат'}, status=400)


class FavoriteViewSet(viewsets.ModelViewSet):

    queryset = Favorite.objects.all()
    serializer_class = FavoriteSerializer
    pagination_class = PageNumberPagination
    http_method_names = ['post', 'del']
    search_fields = ['=name']
