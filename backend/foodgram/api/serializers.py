import base64
from typing import Any, Dict, List, Optional, Union

from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from food.models import (
    Favorite,
    Follow,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
    User,
)
from rest_framework import serializers, status


class Base64ImageField(serializers.ImageField):
    """Кастомное поле для работы с изображениями в формате base64."""

    def to_internal_value(self, data: Union[str, ContentFile]) -> ContentFile:
        """Преобразует base64 строку в файл или возвращает исходный файл."""
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)
        return super().to_internal_value(data)

    def to_representation(self, value: Any) -> Optional[str]:
        """Возвращает полный URL изображения."""
        if not value:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(value.url)
        return value.url


class AvatarUpdateSerializer(serializers.Serializer):
    avatar = Base64ImageField()

    def update(self, instance, validated_data):
        instance.profile.avatar = validated_data['avatar']
        instance.profile.save()
        return instance


class IsFavoritedField(serializers.Field):
    """Кастомное поле для проверки, находится ли рецепт в избранном."""

    def to_representation(self, obj: Recipe) -> bool:
        """Проверяет, добавлен ли рецепт в избранное."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(
                user=request.user,
                favorite=obj
            ).exists()
        return False


class IsInShoppingCartField(serializers.Field):
    """Кастомное поле для проверки, находится ли рецепт в корзине покупок."""

    def to_representation(self, obj: Recipe) -> bool:
        """Проверяет, добавлен ли рецепт в корзину у текущего пользователя."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ShoppingCart.objects.filter(
                user=request.user,
                recipe=obj
            ).exists()
        return False


class IsFollowedField(serializers.Field):
    """Кастомное поле для проверки подписки на пользователя."""

    def to_representation(self, obj: User) -> bool:
        """Проверяет, подписан ли текущий пользователь на автора."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Follow.objects.filter(
                user=request.user,
                following=obj
            ).exists()
        return False


class RecipeFollowFieldSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения рецептов в подписках."""

    image = Base64ImageField()

    class Meta:
        """Мета-класс для настройки сериализатора рецептов в подписках.

        Определяет:
        - Модель, с которой работает сериализатор (Recipe)
        - Поля, которые включаются в сериализацию
        """

        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для тегов."""

    class Meta:
        """Мета-класс для настройки сериализатора тегов.

        Определяет:
        - Модель, с которой работает сериализатор (Tag)
        - Поля, которые включаются в сериализацию
        """

        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для ингредиентов."""

    class Meta:
        """Мета-класс для настройки сериализатора ингредиентов.

        Определяет:
        - Модель, с которой работает сериализатор (Ingredient)
        - Поля, которые включаются в сериализацию
        """

        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class UserCreateSerializer(BaseUserCreateSerializer):
    first_name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=150
    )
    last_name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=150
    )
    email = serializers.EmailField(
        required=True,
        max_length=254
    )
    username = serializers.CharField(
        max_length=150,
        validators=[AbstractUser.username_validator]
    )

    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'password'
        )
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        required_fields = ['email', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                raise serializers.ValidationError(
                    {field: 'Это поле обязательно для заполнения.'},
                    code=status.HTTP_400_BAD_REQUEST
                )
            if field in ['first_name', 'last_name'] and not data[field
                                                                 ].strip():
                raise serializers.ValidationError(
                    {field: 'Это поле не может быть пустым.'},
                    code=status.HTTP_400_BAD_REQUEST
                )
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError(
                {'email': 'Пользователь с таким email уже существует.'},
                code=status.HTTP_400_BAD_REQUEST
            )
        return data

    def validate_username(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                'Имя пользователя не может быть пустым.',
                code=status.HTTP_400_BAD_REQUEST
            )
        if len(value) > 150:
            raise serializers.ValidationError(
                'Имя пользователя не может превышать 150 символов.',
                code=status.HTTP_400_BAD_REQUEST
            )
        return value.strip()

    def validate_email(self, value):
        if len(value) > 254:
            raise serializers.ValidationError(
                'Email не может превышать 254 символа.',
                code=status.HTTP_400_BAD_REQUEST
            )
        return value

    def validate_password(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                'Пароль не может быть пустым.',
                code=status.HTTP_400_BAD_REQUEST
            )
        return value


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для пользователей."""

    is_subscribed = IsFollowedField(default=True)
    avatar = Base64ImageField(source='profile.avatar', required=False)

    class Meta:
        """Мета-класс для настройки сериализатора пользователей.

        Определяет:
        - Модель, с которой работает сериализатор (User)
        - Поля, которые включаются в сериализацию
        - Дополнительные поля (is_subscribed, avatar)
        """

        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'avatar'
        )


class RecipeIngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для связи рецепта и ингредиента."""

    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )
    amount = serializers.IntegerField(source='quantity')

    class Meta:
        """Мета-класс для настройки сериализатора связи рецепта и ингредиента.

        Определяет:
        - Модель, с которой работает сериализатор (RecipeIngredient)
        - Поля, которые включаются в сериализацию
        - Переопределенные поля (id, name, measurement_unit, amount)
        """

        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для рецептов."""

    tags = TagSerializer(many=True)
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        many=True,
        source='recipe_ingredients'
    )
    is_favorited = IsFavoritedField(read_only=True)
    is_in_shopping_cart = IsInShoppingCartField(read_only=True)
    image = Base64ImageField()

    class Meta:
        """Мета-класс для настройки сериализатора рецептов.

        Определяет:
        - Модель, с которой работает сериализатор (Recipe)
        - Поля, которые включаются в сериализацию
        - Вложенные сериализаторы (tags, author, ingredients)
        - Кастомные поля (is_favorited, is_in_shopping_cart)
        """

        model = Recipe
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time'
        )

    def create(self, validated_data: Dict[str, Any]) -> Recipe:
        """Создает новый рецепт с ингредиентами и тегами."""
        ingredients_data = self.initial_data.get('ingredients', [])
        tags_data = self.initial_data.get('tags', [])
        if not ingredients_data:
            raise serializers.ValidationError(
                {'ingredients': 'Добавьте хотя бы один ингредиент'})
        if not tags_data:
            raise serializers.ValidationError(
                {'tags': 'Добавьте хотя бы один тег'})
        validated_data.pop('recipe_ingredients', None)
        validated_data.pop('tags', None)
        recipe = Recipe.objects.create(
            author=self.context['request'].user,
            **validated_data
        )
        for ingredient_data in ingredients_data:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient_id=ingredient_data['id'],
                quantity=ingredient_data['amount']
            )
        recipe.tags.set(tags_data)
        return recipe

    def update(self, instance: Recipe, validated_data: Dict[str, Any]
               ) -> Recipe:
        """Обновляет существующий рецепт."""
        if self.context['request'].user != instance.author:
            raise serializers.ValidationError(
                'У вас нет прав редактировать рецепт'
            )
        ingredients_data = self.initial_data.get('ingredients', [])
        tags_data = self.initial_data.get('tags', [])
        validated_data.pop('recipe_ingredients', None)
        validated_data.pop('tags', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if tags_data:
            instance.tags.set(tags_data)
        if ingredients_data:
            instance.recipe_ingredients.all().delete()
            for ingredient_data in ingredients_data:
                RecipeIngredient.objects.create(
                    recipe=instance,
                    ingredient_id=ingredient_data['id'],
                    quantity=ingredient_data['amount']
                )
        instance.save()
        return instance

    def validate_ingredients(
            self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Проверяет, что передан хотя бы один ингредиент."""
        if not value:
            raise serializers.ValidationError(
                'Добавьте хотя бы один ингредиент'
            )
        return value

    def validate_tags(self, value: List[Tag]) -> List[Tag]:
        """Проверяет, что передан хотя бы один тег."""
        if not value:
            raise serializers.ValidationError('Добавьте хотя бы один тег')
        return value

    def validate_cooking_time(self, value):
        if value < 1:
            raise serializers.ValidationError(
                'Время приготовления должно быть не менее 1 минуты'
            )
        return value


class FavoriteSerializer(serializers.ModelSerializer):
    """Сериализатор для избранных рецептов."""

    id = serializers.ReadOnlyField(source='recipe.id')
    name = serializers.ReadOnlyField(source='recipe.name')
    image = Base64ImageField(source='recipe')
    cooking_time = serializers.ReadOnlyField(source='recipe.cooking_time')

    class Meta:
        """Мета-класс для настройки сериализатора избранных рецептов.

        Определяет:
        - Модель, с которой работает сериализатор (Favorite)
        - Поля, которые включаются в сериализацию
        - Источники данных для полей (через recipe)
        """

        model = Favorite
        fields = ('id', 'name', 'image', 'cooking_time')


class ShoppingCartSerializer(serializers.ModelSerializer):
    """Сериализатор для корзины покупок."""

    id = serializers.ReadOnlyField(source='recipe.id')
    name = serializers.ReadOnlyField(source='recipe.name')
    image = Base64ImageField(source='recipe')
    cooking_time = serializers.ReadOnlyField(source='recipe.cooking_time')

    class Meta:
        """Мета-класс для настройки сериализатора корзины покупок.

        Определяет:
        - Модель, с которой работает сериализатор (ShoppingCart)
        - Поля, которые включаются в сериализацию
        - Источники данных для полей (через recipe)
        """

        model = ShoppingCart
        fields = ('id', 'name', 'image', 'cooking_time')


class FollowSerializer(serializers.ModelSerializer):
    """Сериализатор для подписок."""

    is_subscribed = IsFollowedField(default=True)
    email = serializers.ReadOnlyField(source='following.email')
    id = serializers.ReadOnlyField(source='following.id')
    username = serializers.ReadOnlyField(source='following.username')
    first_name = serializers.ReadOnlyField(source='following.first_name')
    last_name = serializers.ReadOnlyField(source='following.last_name')
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        source='following.recipes.count',
        read_only=True
    )
    avatar = Base64ImageField(source='following.profile.avatar')

    def get_recipes(self, obj: Follow) -> List[Dict[str, Any]]:
        """Получает список рецептов с возможностью ограничения количества."""
        request = self.context.get('request')
        recipes = obj.following.recipes.order_by('-created_at')
        if request:
            recipes_limit = request.query_params.get('recipes_limit', 3)
            if recipes_limit and recipes_limit.isdigit():
                recipes = recipes[:int(recipes_limit)]
        return RecipeFollowFieldSerializer(
            recipes,
            many=True,
            context=self.context).data

    class Meta:
        """Мета-класс для настройки сериализатора подписок.

        Определяет:
        - Модель, с которой работает сериализатор (Follow)
        - Поля, которые включаются в сериализацию
        - Источники данных для полей (через following)
        - Дополнительные вычисляемые поля (recipes, recipes_count)
        """

        model = Follow
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'recipes',
            'recipes_count',
            'avatar'
        )

    def validate(self, data):
        if self.context['request'].user == data['following']:
            raise serializers.ValidationError(
                'Нельзя подписаться на самого себя'
            )
        return data
