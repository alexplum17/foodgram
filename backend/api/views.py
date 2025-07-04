"""backend/api/views.py."""

import csv
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db.models import (
    BooleanField,
    Exists,
    OuterRef,
    QuerySet,
    Sum,
    Value,
)
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewSet
from food.constants import (
    MAX_PAGE_SIZE,
    PDF_FONT_BOLD,
    PDF_FONT_REGULAR,
    PDF_LINE_HEIGHT,
    PDF_MIN_Y,
    PDF_REGULAR_FONT_SIZE,
    PDF_START_X,
    PDF_START_Y,
    PDF_TITLE_FONT_SIZE,
    PDF_TITLE_Y,
    SHOPPING_LIST_CSV_FILENAME,
    SHOPPING_LIST_PDF_FILENAME,
    SHOPPING_LIST_TXT_FILENAME,
)
from food.models import (
    Follow,
    Ingredient,
    Recipe,
    RecipeIngredient,
    Tag,
    User,
    generate_hash,
)
from reportlab.pdfgen import canvas
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response

from api.filters import IngredientSearchFilter, RecipeFilter
from api.permissions import IsAuthorOrReadOnly
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
        if request.method == 'PUT':
            serializer = AvatarUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST)
            serializer.update(user, serializer.validated_data)
            return Response(
                {'avatar': user.avatar.url if user.avatar else None},
                status=status.HTTP_200_OK
            )
        if not user.avatar:
            return Response(
                {"detail": "Аватар не найден"},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.avatar.delete()
        user.avatar = None
        user.save()
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
        """Создает/удаляет подписку на пользователя."""
        user = request.user
        following = get_object_or_404(User, id=kwargs['id'])
        if request.method == 'POST':
            if user == following:
                return Response(
                    {'errors': 'Нельзя подписаться на самого себя'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if user.following.filter(following=following).exists():
                return Response(
                    {'errors': 'Вы уже подписаны на этого пользователя'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            follow = user.following.create(following=following)
            serializer = FollowSerializer(
                follow,
                context={'request': request}
            )
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
                headers=self.get_success_headers(serializer.data)
            )
        follow = user.following.filter(following=following).first()
        if not follow:
            return Response(
                {'errors': 'Подписка не найдена'},
                status=status.HTTP_400_BAD_REQUEST
            )
        follow.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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
    filter_backends = [IngredientSearchFilter]
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
                    self.request.user.favorite_user.filter(
                        recipe=OuterRef('pk')
                    ), output_field=BooleanField()
                ),
                is_in_shopping_cart=Exists(
                    self.request.user.shoppingcart_user.filter(
                        recipe=OuterRef('pk')
                    ), output_field=BooleanField()
                )
            )
        else:
            queryset = queryset.annotate(
                is_favorited=Value(False, output_field=BooleanField()),
                is_in_shopping_cart=Value(False, output_field=BooleanField())
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
        if self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]
        elif self.action == 'create' or (
            self.action in (
                ['favorite', 'shopping_cart', 'download_shopping_cart'])):
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticatedOrReadOnly]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer: Any) -> None:
        """Устанавливает автора рецепта."""
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        """Добавление/удаление рецепта в избранное."""
        return self._handle_recipe_action(
            request=request,
            action_type='favorite',
            serializer_class=FavoriteSerializer,
            exists_message='Рецепт уже в избранном'
        )

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def shopping_cart(self, request, pk=None):
        """Добавление/удаление рецепта из списка покупок."""
        return self._handle_recipe_action(
            request=request,
            action_type='shopping_cart',
            serializer_class=ShoppingCartSerializer,
            exists_message='Рецепт уже в списке покупок'
        )

    def _handle_recipe_action(self,
                              request,
                              action_type,
                              serializer_class,
                              exists_message
                              ):
        recipe = self.get_object()
        if action_type == 'favorite':
            relation_manager = request.user.favorite_user
        elif action_type == 'shopping_cart':
            relation_manager = request.user.shoppingcart_user
        else:
            return Response(
                {'errors': 'Неизвестный тип действия'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.method == 'POST':
            exists = relation_manager.filter(recipe=recipe).exists()
            if exists:
                return Response(
                    {'errors': exists_message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            relation = relation_manager.create(recipe=recipe)
            serializer = serializer_class(relation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        relation = relation_manager.filter(recipe=recipe).first()
        if not relation:
            return Response(
                {'errors': 'Рецепт не найден в списке'},
                status=status.HTTP_400_BAD_REQUEST
            )
        relation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            url_path='download_shopping_cart')
    def download_shopping_cart(self, request) -> Response:
        """Скачивание списка ингредиентов для рецептов в корзине."""
        user = request.user
        recipe_ids = request.query_params.get('recipe_ids')
        shopping_cart = user.shoppingcart_user.all()
        if recipe_ids:
            try:
                recipe_ids = [int(id) for id in recipe_ids.split(',')]
                shopping_cart = shopping_cart.filter(recipe_id__in=recipe_ids)
            except ValueError:
                return Response(
                    {'error': 'Некорректный формат recipe_ids'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        ingredients_data = (
            RecipeIngredient.objects
            .filter(recipe__shoppingcart_recipe__user=user)
            .values(
                'ingredient__name',
                'ingredient__measurement_unit'
            )
            .annotate(total_amount=Sum('amount'))
            .order_by('ingredient__name')
        )

        if not ingredients_data:
            return Response(
                {'error': 'Нет ингредиентов для скачивания'},
                status=status.HTTP_400_BAD_REQUEST
            )
        ingredients = {
            (item['ingredient__name'], item['ingredient__measurement_unit']
             ): item['total_amount']
            for item in ingredients_data
        }
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
        for (name, unit), amount in ingredients.items():
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
        for (name, unit), amount in ingredients.items():
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
        for (name, unit), amount in ingredients.items():
            writer.writerow([name, unit, amount])
        return response