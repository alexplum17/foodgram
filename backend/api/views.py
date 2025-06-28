"""backend/api/views.py."""

import csv
from collections import defaultdict
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from api.filters import RecipeFilter
from api.permissions import IsAuthorOrReadOnly
from api.serializers import (AvatarUpdateSerializer, FavoriteSerializer,
                             FollowSerializer, IngredientSerializer,
                             RecipeSerializer, ShoppingCartSerializer,
                             TagSerializer, UserSerializer)
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db.models import Exists, OuterRef, QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewSet
from food.constants import (MAX_PAGE_SIZE, PDF_FONT_BOLD, PDF_FONT_REGULAR,
                            PDF_LINE_HEIGHT, PDF_MIN_Y, PDF_REGULAR_FONT_SIZE,
                            PDF_START_X, PDF_START_Y, PDF_TITLE_FONT_SIZE,
                            PDF_TITLE_Y, SHOPPING_LIST_CSV_FILENAME,
                            SHOPPING_LIST_PDF_FILENAME,
                            SHOPPING_LIST_TXT_FILENAME)
from food.models import (Favorite, Follow, Ingredient, Profile, Recipe,
                         ShoppingCart, Tag, User, generate_hash)
from reportlab.pdfgen import canvas
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response


def short_link_redirect(request: HttpRequest, short_link: str
                        ) -> HttpResponseRedirect:
    """Перенаправляет пользователя на полный URL рецепта по короткой ссылке."""
    recipe = get_object_or_404(Recipe, short_link=short_link)
    return redirect(f'/recipes/{recipe.id}/')


class BaseViewSet(viewsets.ViewSet):
    """Базовый ViewSet с общим методом для всех наследников."""

    def paginate_queryset(self, queryset: QuerySet) -> Optional[QuerySet]:
        """Переопределяет пагинацию для поддержки параметра 'limit'."""
        if self.paginator is None:
            return None
        limit = self.request.query_params.get('limit')
        if limit is not None:
            try:
                limit = int(limit)
                if limit > 0:
                    max_limit = getattr(
                        settings, 'MAX_PAGE_SIZE', MAX_PAGE_SIZE)
                    limit = min(limit, max_limit)
                    self.paginator.page_size = limit
            except (ValueError, TypeError):
                # Если limit не является числом,
                # используем значение по умолчанию
                pass
        return self.paginator.paginate_queryset(
            queryset, self.request, view=self)


class UserViewSet(DjoserUserViewSet, BaseViewSet):
    """ViewSet для управления пользователями."""

    http_method_names = ['get', 'post', 'put', 'delete']
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_class(self) -> Any:
        """Определяет класс сериализатора в зависимости от действия."""
        if self.action in ['create', 'set_password']:
            return super().get_serializer_class()
        elif self.action in ['subscribe', 'subscriptions']:
            return FollowSerializer
        return UserSerializer

    @action(['post'], detail=False, permission_classes=[IsAuthenticated])
    def set_password(self, request: HttpRequest, *args: Any, **kwargs: Any
                     ) -> Response:
        """Изменяет пароль текущего пользователя."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.request.user.set_password(serializer.data['new_password'])
        self.request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['put', 'delete'], url_path='me/avatar',
            permission_classes=[IsAuthenticated])
    def avatar(self, request: HttpRequest) -> Response:
        """Управление аватаром пользователя."""
        user = request.user
        try:
            profile = user.profile
        except ObjectDoesNotExist:
            profile = Profile.objects.create(user=user)
        if request.method == 'PUT':
            serializer = AvatarUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST)
            serializer.update(user, serializer.validated_data)
            return Response(
                {'avatar': profile.avatar.url},
                status=status.HTTP_200_OK
            )
        if not profile.avatar:
            return Response(
                {"detail": "Аватар не найден"},
                status=status.HTTP_400_BAD_REQUEST
            )
        profile.avatar.delete()
        profile.avatar = None
        profile.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated])
    def me(self, request: HttpRequest) -> Response:
        """Возвращает данные текущего пользователя."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(['post', 'delete'], detail=True, url_path='subscribe',
            permission_classes=[IsAuthenticated])
    def subscribe(self, request: HttpRequest, **kwargs) -> Response:
        """Создает подписку на пользователя."""
        user = request.user
        following = get_object_or_404(User, id=kwargs['id'])
        if request.method == 'POST':
            serializer = FollowSerializer(data={},
                                          context={'request': request,
                                                   'following': following})
            serializer.is_valid(raise_exception=True)
            serializer.save(user=user, following=following)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data,
                            status=status.HTTP_201_CREATED,
                            headers=headers)
        elif request.method == 'DELETE':
            try:
                follow = Follow.objects.get(user=user, following=following)
                follow.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Follow.DoesNotExist:
                return Response(
                    {'detail': 'Подписка не найдена'},
                    status=status.HTTP_400_BAD_REQUEST
                )

    @action(['get'], detail=False, permission_classes=[IsAuthenticated],
            url_path='subscriptions')
    def subscriptions(self, request: HttpRequest) -> Response:
        """Возвращает список подписок текущего пользователя."""
        queryset = Follow.objects.filter(user=request.user
                                         ).select_related('following')
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class TagViewSet(viewsets.ModelViewSet):
    """ViewSet для управления тегами."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    http_method_names = ['get']
    pagination_class = None


class IngredientViewSet(viewsets.ModelViewSet):
    """ViewSet для управления ингридиентами."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    http_method_names = ['get']
    search_fields = ['=name']
    pagination_class = None

    def get_queryset(self) -> QuerySet:
        """Фильтрует ингредиенты по имени, если указан параметр name."""
        queryset = self.queryset
        search_query = self.request.query_params.get('name', None)
        if search_query:
            queryset = queryset.filter(name__istartswith=search_query)
        return queryset


class RecipeViewSet(viewsets.ModelViewSet, BaseViewSet):
    """ViewSet для управления рецептами."""

    queryset = Recipe.objects.all().order_by('-created_at')
    serializer_class = RecipeSerializer
    pagination_class = PageNumberPagination
    http_method_names = ['get', 'post', 'patch', 'delete']
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = RecipeFilter

    def get_queryset(self) -> QuerySet:
        """Оптимизирует запросы."""
        queryset = super().get_queryset()
        queryset = queryset.prefetch_related('tags', 'ingredients')
        if self.request.user.is_authenticated:
            queryset = queryset.annotate(
                is_favorited=Exists(
                    Favorite.objects.filter(
                        user=self.request.user,
                        favorite=OuterRef('pk')
                    )
                ),
                is_in_shopping_cart=Exists(
                    ShoppingCart.objects.filter(
                        user=self.request.user,
                        recipe=OuterRef('pk')
                    )
                )
            )
        else:
            from django.db.models import Value
            queryset = queryset.annotate(
                is_favorited=Value(False),
                is_in_shopping_cart=Value(False)
            )
        return queryset

    @action(detail=False, methods=['get'], url_path='s/(?P<short_link>[^/.]+)')
    def retrieve_by_short_link(
        self, request: HttpRequest, short_link: Optional[str] = None
    ) -> Response:
        """Получает рецепт по короткой ссылке."""
        recipe = get_object_or_404(Recipe, short_link=short_link)
        serializer = self.get_serializer(recipe)
        return Response(serializer.data)

    @action(detail=True,
            methods=('get',),
            url_path='get-link',
            url_name='get-link'
            )
    def get_link(self, request: HttpRequest, pk: Optional[int] = None
                 ) -> Response:
        """Генерирует короткую ссылку на рецепт."""
        recipe = self.get_object()
        if not recipe.short_link:
            recipe.short_link = generate_hash()
            recipe.save()
        return Response({
            'short-link': request.build_absolute_uri(
                f'/s/{recipe.short_link}/')
        })

    def get_serializer_context(self) -> Dict[str, Any]:
        """Добавляет запрос в контекст сериализатора."""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_permissions(self) -> List[Any]:
        """Определяет уровень доступа для разных действий."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated]
        elif self.action in (['favorite',
                              'shopping_cart',
                              'download_shopping_cart']):
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticatedOrReadOnly]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer: Any) -> None:
        """Устанавливает автора рецепта."""
        serializer.save(author=self.request.user)

    def perform_update(self, serializer: Any) -> None:
        """Проверяет, что пользователь может редактировать рецепт."""
        if serializer.instance.author != self.request.user:
            raise PermissionDenied(
                'Вы можете редактировать только свои рецепты'
            )
        serializer.save()

    @action(detail=True, methods=['delete'],
            permission_classes=[IsAuthorOrReadOnly])
    def perform_destroy(self, instance: Recipe) -> None:
        """Удаляет рецепт с проверкой прав."""
        if instance.author != self.request.user:
            raise PermissionDenied('Вы можете удалять только свои рецепты')
        instance.delete()

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def favorite(self, request: HttpRequest, pk: Optional[int] = None
                 ) -> Response:
        """Добавление/удаление рецепта из избранного."""
        recipe = self.get_object()
        if request.method == 'POST':
            if Favorite.objects.filter(
                user=request.user,
                favorite=recipe
            ).exists():
                return Response(
                    {'errors': 'Рецепт уже в избранном'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            favorite = Favorite.objects.create(
                user=request.user,
                favorite=recipe
            )
            serializer = FavoriteSerializer(favorite)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        favorite = Favorite.objects.filter(
            user=request.user,
            favorite=recipe
        ).first()
        if not favorite:
            return Response(
                {'errors': 'Рецепта нет в избранном'},
                status=status.HTTP_400_BAD_REQUEST
            )
        favorite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def shopping_cart(self, request: HttpRequest, pk: Optional[int] = None
                      ) -> Response:
        """Добавление/удаление рецепта из списка покупок."""
        recipe = self.get_object()
        if request.method == 'POST':
            if ShoppingCart.objects.filter(user=request.user,
                                           recipe=recipe
                                           ).exists():
                return Response(
                    {'errors': 'Рецепт уже в списке покупок'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            shopping_cart = ShoppingCart.objects.create(
                user=request.user, recipe=recipe
            )
            serializer = ShoppingCartSerializer(shopping_cart)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        shopping_cart = ShoppingCart.objects.filter(
            user=request.user, recipe=recipe
        ).first()
        if not shopping_cart:
            return Response(
                {'errors': 'Рецепта нет в списке покупок'},
                status=status.HTTP_400_BAD_REQUEST
            )
        shopping_cart.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            url_path='download_shopping_cart')
    def download_shopping_cart(self, request) -> Response:
        """Скачивание списка ингредиентов для рецептов в корзине."""
        user = request.user
        recipe_ids = request.query_params.get('recipe_ids')
        if recipe_ids:
            try:
                recipe_ids = [int(id) for id in recipe_ids.split(',')]
                shopping_cart = user.shopping_cart.filter(
                    recipe_id__in=recipe_ids
                )
            except ValueError:
                return Response(
                    {'error': 'Некорректный формат recipe_ids'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            shopping_cart = user.shopping_cart.all()
        ingredients = defaultdict(int)
        for item in shopping_cart:
            for ri in item.recipe.recipe_ingredients.all():
                key = (ri.ingredient.name, ri.ingredient.measurement_unit)
                ingredients[key] += ri.amount

        if not ingredients:
            return Response(
                {'error': 'Нет ингредиентов для скачивания'},
                status=status.HTTP_400_BAD_REQUEST
            )

        format = request.query_params.get('format', 'txt').lower()
        if format == 'txt':
            return self._generate_txt_response(ingredients)
        elif format == 'pdf':
            return self._generate_pdf_response(ingredients)
        elif format == 'csv':
            return self._generate_csv_response(ingredients)
        else:
            return Response(
                {'error': 'Неподдерживаемый формат. Доступны: txt, pdf, csv'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _generate_txt_response(self, ingredients: Dict[Tuple[str, str], int]
                               ) -> HttpResponse:
        """Генерация TXT файла со списком ингредиентов."""
        response = HttpResponse(content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="{SHOPPING_LIST_TXT_FILENAME}"'
        )
        text = 'Список покупок:\n\n'
        for (name, unit), amount in sorted(ingredients.items()):
            text += f"- {name} ({unit}) — {amount}\n"
        response.write(text)
        return response

    def _generate_pdf_response(self, ingredients: Dict[Tuple[str, str], int]
                               ) -> HttpResponse:
        """Генерация PDF файла со списком ингредиентов."""
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        p.setFont(PDF_FONT_BOLD, PDF_TITLE_FONT_SIZE)
        p.drawString(PDF_START_X, PDF_START_Y, 'Список покупок:')
        p.setFont(PDF_FONT_REGULAR, PDF_REGULAR_FONT_SIZE)
        y_position = PDF_TITLE_Y
        for (name, unit), amount in sorted(ingredients.items()):
            if y_position < PDF_MIN_Y:
                p.showPage()
                y_position = PDF_START_Y
                p.setFont(PDF_FONT_REGULAR, PDF_REGULAR_FONT_SIZE)
            p.drawString(
                PDF_START_X,
                y_position,
                f'- {name} ({unit}) — {amount}'
            )
            y_position -= PDF_LINE_HEIGHT
        p.showPage()
        p.save()
        pdf = buffer.getvalue()
        buffer.close()
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{SHOPPING_LIST_PDF_FILENAME}"'
        )
        response.write(pdf)
        return response

    def _generate_csv_response(self, ingredients: Dict[Tuple[str, str], int]
                               ) -> HttpResponse:
        """Генерация CSV файла со списком ингредиентов."""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="{SHOPPING_LIST_CSV_FILENAME}"'
        )
        writer = csv.writer(response)
        writer.writerow(['Ингредиент', 'Единица измерения', 'Количество'])
        for (name, unit), amount in sorted(ingredients.items()):
            writer.writerow([name, unit, amount])
        return response
