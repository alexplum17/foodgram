import csv
from collections import defaultdict
from io import BytesIO, StringIO

import reportlab
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewSet
from food.models import (
    Favorite,
    Follow,
    Ingredient,
    Profile,
    Recipe,
    ShoppingCart,
    Tag,
    User,
    generate_hash,
)
from reportlab.pdfgen import canvas
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from api.filters import RecipeFilter
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


class UserViewSet(DjoserUserViewSet):
    http_method_names = ['get', 'post', 'put', 'delete']
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action in ['create', 'set_password']:
            return super().get_serializer_class()
        return UserSerializer

    def paginate_queryset(self, queryset):
        """
        Переопределяем пагинацию для поддержки параметра 'limit'
        """
        if self.paginator is None:
            return None
        limit = self.request.query_params.get('limit')
        if limit is not None:
            try:
                limit = int(limit)
                if limit > 0:
                    max_limit = getattr(settings, 'MAX_PAGE_SIZE', 100)
                    limit = min(limit, max_limit)
                    self.paginator.page_size = limit
            except (ValueError, TypeError):
                # Если limit не является числом,
                # используем значение по умолчанию
                pass
        return self.paginator.paginate_queryset(
            queryset, self.request, view=self)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data.get('email'):
            return Response(
                {'email': 'Email обязателен для регистрации.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not serializer.validated_data.get('first_name'):
            return Response(
                {'first_name': 'Имя обязательно для регистрации.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not serializer.validated_data.get('last_name'):
            return Response(
                {'last_name': 'Фамилия обязательна для регистрации.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if User.objects.filter(email=serializer.validated_data['email']
                               ).exists():
            return Response(
                {'email': 'Пользователь с таким email уже существует.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    @action(['post'], detail=False, permission_classes=[IsAuthenticated])
    def set_password(self, request, *args, **kwargs):
        # Смена пароля только для авторизованных
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.request.user.set_password(serializer.data['new_password'])
        self.request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['put', 'delete'], url_path='me/avatar',
            permission_classes=[IsAuthenticated])
    def avatar(self, request):
        # Изменение аватара только для авторизованных
        user = request.user
        profile, created = Profile.objects.get_or_create(user=user)
        if request.method == 'PUT':
            serializer = AvatarUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST)
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

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated]
            )
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


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

    def get_queryset(self):
        queryset = self.queryset
        search_query = self.request.query_params.get('name', None)
        if search_query:
            queryset = queryset.filter(name__istartswith=search_query)
        return queryset


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all().order_by('-created_at')
    serializer_class = RecipeSerializer
    pagination_class = PageNumberPagination
    http_method_names = ['get', 'post', 'patch', 'delete']
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = RecipeFilter


    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related('tags', 'ingredients')

    @action(detail=True,
            methods=('get',),
            url_path='get-link',
            url_name='get-link'
            )
    def get_link(self, request, pk=None):
        """Генерирует короткую ссылку на рецепт."""
        recipe = self.get_object()
        if not recipe.short_link:
            recipe.short_link = generate_hash()
            recipe.save()
        return Response({
            'short-link': request.build_absolute_uri(
                f'/s/{recipe.short_link}/')
        })

    def paginate_queryset(self, queryset):
        """
        Переопределяем пагинацию для поддержки параметра 'limit'
        """
        if self.paginator is None:
            return None
        limit = self.request.query_params.get('limit')
        if limit is not None:
            try:
                limit = int(limit)
                if limit > 0:
                    max_limit = getattr(settings, 'MAX_PAGE_SIZE', 100)
                    limit = min(limit, max_limit)
                    self.paginator.page_size = limit
            except (ValueError, TypeError):
                # Если limit не является числом,
                # используем значение по умолчанию
                pass
        return self.paginator.paginate_queryset(
            queryset, self.request, view=self)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_permissions(self):
        """Определяет уровень доступа для разных действий."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated]
        elif self.action in ['favorite', 'shopping_cart']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticatedOrReadOnly]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        """Автоматически устанавливает автора рецепта."""
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        """Проверяет, что пользователь может редактировать рецепт."""
        if serializer.instance.author != self.request.user:
            raise PermissionDenied(
                'Вы можете редактировать только свои рецепты'
            )
        serializer.save()

    @action(detail=True, methods=['delete'],
            permission_classes=[IsAuthorOrReadOnly])
    def perform_destroy(self, instance):
        if instance.author != self.request.user:
            raise PermissionDenied('Вы можете удалять только свои рецепты')
        instance.delete()

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        """Добавление/удаление рецепта из избранного, для авторизованных"""
        recipe = self.get_object()
        if request.method == 'POST':
            if Favorite.objects.filter(
                user=request.user,
                recipe=recipe
            ).exists():
                return Response(
                    {'errors': 'Рецепт уже в избранном'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            favorite = Favorite.objects.create(
                user=request.user,
                recipe=recipe
            )
            serializer = FavoriteSerializer(favorite)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        elif request.method == 'DELETE':
            favorite = Favorite.objects.filter(
                user=request.user, recipe=recipe
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
    def shopping_cart(self, request, pk=None):
        """Добавление/удаление рецепта из списка покупок, для авторизованных"""
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
        elif request.method == 'DELETE':
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


class FollowViewSet(viewsets.ModelViewSet):
    """Управление подписками. Доступно только авторизованным пользователям."""

    queryset = Follow.objects.all()
    serializer_class = FollowSerializer
    pagination_class = PageNumberPagination
    http_method_names = ['get', 'post', 'delete']
    permission_classes = [IsAuthenticated]

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
    """
    Управление списком покупок.
    Доступно только авторизованным пользователям.
    Поддерживает скачивание списка ингредиентов в форматах TXT, PDF и CSV.
    """
    permission_classes = [IsAuthenticated]
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
        """
        Скачивание списка ингредиентов для рецептов в корзине.
        Поддерживаемые форматы: TXT, PDF, CSV (передается в параметре format)
        Можно указать конкретные рецепты через параметр recipe_ids (через запятую)
        """
        user = request.user
        recipe_ids = request.query_params.get('recipe_ids')
        # Получаем рецепты из корзины пользователя
        if recipe_ids:
            try:
                recipe_ids = [int(id) for id in recipe_ids.split(',')]
                shopping_cart = user.shopping_cart.filter(recipe_id__in=recipe_ids)
            except ValueError:
                return Response(
                    {'error': 'Некорректный формат recipe_ids'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            shopping_cart = user.shopping_cart.all()

        # Собираем ингредиенты с учетом количества
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

    def _generate_txt_response(self, ingredients):
        """Генерация TXT файла со списком ингредиентов"""
        response = HttpResponse(content_type='text/plain; charset=utf-8')
        response['Content-Disposition'
                 ] = 'attachment; filename="shopping_list.txt"'

        text = 'Список покупок:\n\n'
        for (name, unit), amount in sorted(ingredients.items()):
            text += f"- {name} ({unit}) — {amount}\n"
        response.write(text)
        return response

    def _generate_pdf_response(self, ingredients):
        """Генерация PDF файла со списком ингредиентов"""
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, 800, "Список покупок:")
        p.setFont("Helvetica", 12)
        y_position = 770
        for (name, unit), amount in sorted(ingredients.items()):
            if y_position < 50:
                p.showPage()
                y_position = 800
                p.setFont("Helvetica", 12)
            p.drawString(50, y_position, f"- {name} ({unit}) — {amount}")
            y_position -= 20
        p.showPage()
        p.save()
        pdf = buffer.getvalue()
        buffer.close()
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'
                 ] = 'attachment; filename="shopping_list.pdf"'
        response.write(pdf)
        return response

    def _generate_csv_response(self, ingredients):
        """Генерация CSV файла со списком ингредиентов"""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'
                 ] = 'attachment; filename="shopping_list.csv"'
        writer = csv.writer(response)
        writer.writerow(['Ингредиент', 'Единица измерения', 'Количество'])
        for (name, unit), amount in sorted(ingredients.items()):
            writer.writerow([name, unit, amount])
        return response


class FavoriteViewSet(viewsets.ModelViewSet):

    queryset = Favorite.objects.all()
    serializer_class = FavoriteSerializer
    pagination_class = PageNumberPagination
    http_method_names = ['post', 'del']
    search_fields = ['=name']
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = RecipeFilter

    def get_queryset(self):
        """Возвращает только избранное текущего пользователя."""
        return self.queryset.filter(user=self.request.user).select_related(
            'favorite', 'favorite__author'
        ).prefetch_related('favorite__tags')

    def create(self, request, *args, **kwargs):
        """Добавление рецепта в избранное."""
        recipe_id = request.data.get('id')
        if not recipe_id:
            return Response(
                {'error': 'Не указан ID рецепта'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            recipe = Recipe.objects.get(id=recipe_id)
        except Recipe.DoesNotExist:
            raise NotFound({'error': 'Рецепт не найден'})

        if Favorite.objects.filter(user=request.user, favorite=recipe
                                   ).exists():
            raise ValidationError({'error': 'Рецепт уже в избранном'})

        favorite = Favorite.objects.create(user=request.user, favorite=recipe)
        serializer = self.get_serializer(favorite)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'])
    def delete(self, request, pk=None):
        """Удаление рецепта из избранного."""
        try:
            favorite = Favorite.objects.get(
                user=request.user,
                favorite_id=pk
            )
            favorite.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Favorite.DoesNotExist:
            raise NotFound({'error': 'Рецепт не найден в избранном'})
