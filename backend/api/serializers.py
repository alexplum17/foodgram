"""backend/api/seralizers.py."""

import base64
from typing import Any, Dict, List, Optional, Union

from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError

from food.constants import (MAX_EMAIL_LENGTH, MAX_FIRST_NAME_LENGTH,
                            MAX_LAST_NAME_LENGTH, MAX_USERNAME_LENGTH,
                            MIN_COOKING_TIME, MIN_INGREDIENT_AMOUNT)
from food.models import (Favorite, Follow, Ingredient, Recipe,
                         RecipeIngredient, ShoppingCart, Tag, User)


class Base64ImageField(serializers.ImageField):
    """Кастомное поле для работы с изображениями в формате base64.

    Позволяет:
    - Принимать изображения как в виде base64 строки, так и файлов
    - Конвертировать base64 строку в файл изображения
    - Предоставлять URL изображения в API
    """

    def to_internal_value(self, data: Union[str, ContentFile]) -> ContentFile:
        """Преобразует base64 строку в файл или возвращает исходный файл."""
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)
        return super().to_internal_value(data)

    def to_representation(self, value: Optional[Union[str, ContentFile]]
                          ) -> Optional[str]:
        """Преобразует файл в URL для API."""
        if not value:
            return None
        if isinstance(value, str):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(value)
            return value
        try:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(value.url)
            return value.url
        except AttributeError:
            return str(value)


class AvatarUpdateSerializer(serializers.Serializer):
    """Сериализатор для обновления аватара пользователя."""

    avatar = Base64ImageField()

    def update(self, instance: User, validated_data: Dict[str, Any]) -> User:
        """Обновляет аватар пользователя."""
        instance.avatar = validated_data['avatar']
        instance.save()
        return instance


class IsFavoritedField(serializers.Field):
    """Кастомное поле для проверки, находится ли рецепт в избранном."""

    def to_representation(self, value: Recipe) -> bool:
        """Проверяет, добавлен ли рецепт в избранное."""
        if isinstance(value, bool):
            return value
        if value is None or not isinstance(value, Recipe):
            return False
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return value.favorite_recipe.filter(user=request.user).exists()
        return False


class IsInShoppingCartField(serializers.Field):
    """Кастомное поле для проверки, находится ли рецепт в корзине покупок."""

    def to_representation(self, value: Recipe) -> bool:
        """Проверяет, добавлен ли рецепт в корзину у текущего пользователя."""
        if isinstance(value, bool):
            return value
        if value is None or not isinstance(value, Recipe):
            return False
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return value.shoppingcart_recipe.filter(user=request.user).exists()
        return False


class IsFollowedField(serializers.Field):
    """Кастомное поле для проверки подписки на пользователя."""

    def to_representation(self, obj: User) -> bool:
        """Проверяет, подписан ли текущий пользователь на автора."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return request.user.following.filter(following=obj).exists()
        return False


class RecipeFollowFieldSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения рецептов в подписках."""

    image = Base64ImageField()

    class Meta:
        """Мета-класс для настройки сериализатора рецептов в подписках."""

        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для тегов."""

    class Meta:
        """Мета-класс для настройки сериализатора тегов."""

        model = Tag
        fields = ('__all__')


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для ингредиентов.

    Обеспечивает сериализацию/десериализацию объектов Ingredient.
    """

    class Meta:
        """Мета-класс для настройки сериализатора ингредиентов."""

        model = Ingredient
        fields = ('__all__')


class UserCreateSerializer(BaseUserCreateSerializer):
    """Сериализатор для создания пользователя."""

    first_name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=MAX_FIRST_NAME_LENGTH,
        error_messages={
            'required': 'Имя обязательно для регистрации.',
            'blank': 'Имя не может быть пустым.',
            'max_length': f'Имя не может превышать '
                          f'{MAX_FIRST_NAME_LENGTH} символов.'
        }
    )
    last_name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=MAX_LAST_NAME_LENGTH,
        error_messages={
            'required': 'Фамилия обязательна для регистрации.',
            'blank': 'Фамилия не может быть пустой.',
            'max_length': f'Фамилия не может превышать '
                          f'{MAX_LAST_NAME_LENGTH} символов.'
        }
    )
    email = serializers.EmailField(
        required=True,
        max_length=MAX_EMAIL_LENGTH,
        error_messages={
            'required': 'Email обязателен для регистрации.',
            'invalid': ('Введите корректный email адрес.'
                        'Email должен содержать символ "@"'),
            'max_length': f'Email не может превышать '
                          f'{MAX_EMAIL_LENGTH} символов.'
        }
    )
    username = serializers.CharField(
        max_length=MAX_USERNAME_LENGTH,
        validators=[AbstractUser.username_validator],
        error_messages={
            'blank': 'Имя пользователя не может быть пустым.',
            'max_length': f'Имя пользователя не может превышать '
                          f'{MAX_USERNAME_LENGTH} символов.',
        }
    )

    class Meta(BaseUserCreateSerializer.Meta):
        """Мета-класс для настройки сериализатора создания пользователя."""

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
            'password': {
                'write_only': True,
                'error_messages': {
                    'blank': 'Пароль не может быть пустым.'
                }
            }
        }

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Проверяет валидность данных пользователя."""
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError(
                {'email': 'Пользователь с таким email уже существует.'},
                code=status.HTTP_400_BAD_REQUEST
            )
        return data


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для пользователей."""

    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False)

    class Meta:
        """Мета-класс для настройки сериализатора пользователей."""

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

    def get_is_subscribed(self, obj):
        """Проверяет, подписан ли текущий пользователь на автора."""
        field = IsFollowedField()
        field._context = self.context
        return field.to_representation(obj)


class RecipeIngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для связи рецепта и ингредиента."""

    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    name = serializers.ReadOnlyField(source='ingredient.name', read_only=True)
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit',
        read_only=True
    )
    amount = serializers.IntegerField()

    class Meta:
        """Мета-класс для настройки сериализатора рецепта и ингредиента."""

        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')

    def validate_amount(self, value: int) -> int:
        """Проверяет, что количество игредиентов не меньше одного."""
        if value < MIN_INGREDIENT_AMOUNT:
            raise serializers.ValidationError(
                'Количество ингредиентов не может быть меньше одного'
            )
        return value


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения рецептов (только для чтения)."""

    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        many=True,
        source='recipe_ingredients',
        read_only=True
    )
    is_favorited = IsFavoritedField(read_only=True)
    is_in_shopping_cart = IsInShoppingCartField(read_only=True)
    image = Base64ImageField(read_only=True)

    class Meta:
        """Мета-класс для настройки сериализатора для чтения рецептов."""

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


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для рецептов."""

    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        required=True
    )
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        many=True,
        source='recipe_ingredients',
        required=True
    )
    is_favorited = IsFavoritedField(read_only=True)
    is_in_shopping_cart = IsInShoppingCartField(read_only=True)
    image = Base64ImageField()

    class Meta:
        """Мета-класс для настройки сериализатора рецептов."""

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

    def to_representation(self, instance):
        """Используется RecipeReadSerializer для отображения."""
        if self.context['request'].method == 'GET':
            return RecipeReadSerializer(instance, context=self.context).data
        representation = super().to_representation(instance)
        representation['tags'] = TagSerializer(
            instance.tags.all(),
            many=True,
            context=self.context
        ).data
        representation['is_favorited'] = IsFavoritedField(
        ).to_representation(instance)
        representation['is_in_shopping_cart'] = IsInShoppingCartField(
        ).to_representation(instance)
        return representation

    def _process_ingredients(
            self, recipe: Recipe, ingredients_data: List[Dict[str, Any]]
    ) -> None:
        """Обрабатывает ингредиенты рецепта (создание/обновление)."""
        recipe.recipe_ingredients.all().delete()
        RecipeIngredient.objects.bulk_create([
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient_data['id'],
                amount=ingredient_data['amount']
            )
            for ingredient_data in ingredients_data
        ])

    def create(self, validated_data: Dict[str, Any]) -> Recipe:
        """Создает новый рецепт с тегами и ингредиентами."""
        tags_data = validated_data.pop('tags', [])
        ingredients_data = validated_data.pop('recipe_ingredients', [])
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags_data)
        self._process_ingredients(recipe, ingredients_data)
        return recipe

    def update(self, instance: Recipe, validated_data: Dict[str, Any]
               ) -> Recipe:
        """Обновляет существующий рецепт, его теги и ингредиенты."""
        tags_data = validated_data.pop('tags', None)
        ingredients_data = validated_data.pop('recipe_ingredients', None)
        instance = super().update(instance, validated_data)
        if tags_data is not None:
            instance.tags.set(tags_data)
        if ingredients_data is not None:
            self._process_ingredients(instance, ingredients_data)
        return instance

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Проверяет данные рецепта перед сохранением."""
        required_fields = ['tags', 'recipe_ingredients']
        for field in required_fields:
            if field not in data:
                raise ValidationError({field: 'Это поле обязательно.'})
        if 'recipe_ingredients' in data and not data['recipe_ingredients']:
            raise ValidationError({'recipe_ingredients': (
                'Список ингредиентов не может быть пустым.')})
        if 'tags' in data and not data['tags']:
            raise ValidationError({'tags': (
                'Список тегов не может быть пустым.')})
        ingredients = data['recipe_ingredients']
        ingredient_ids = [ingredient['id'].id for ingredient in (
            ingredients)]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                {'ingredients': (
                    'Ингредиенты в рецепте не должны повторяться.')}
            )
        tags = data['tags']
        tag_ids = [tag.id for tag in tags]
        if len(tag_ids) != len(set(tag_ids)):
            raise serializers.ValidationError(
                {'tags': 'Теги не должны повторяться.'}
            )
        if 'cooking_time' in data and data['cooking_time'] < MIN_COOKING_TIME:
            raise serializers.ValidationError(
                {'cooking_time': (
                    'Время приготовления должно быть не менее 1 минуты.')}
            )
        return data


class FavoriteSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Favorite (избранные рецепты)."""

    name = serializers.ReadOnlyField(source='recipe.name')
    image = Base64ImageField(source='recipe.image')
    cooking_time = serializers.ReadOnlyField(source='recipe.cooking_time')

    class Meta:
        """Мета-класс для настройки сериализатора FavoriteSerializer."""

        model = Favorite
        fields = ('id', 'name', 'image', 'cooking_time')


class ShoppingCartSerializer(serializers.ModelSerializer):
    """Сериализатор для модели ShoppingCart (корзина покупок)."""

    id = serializers.ReadOnlyField(source='recipe.id')
    name = serializers.ReadOnlyField(source='recipe.name')
    image = Base64ImageField(source='recipe')
    cooking_time = serializers.ReadOnlyField(source='recipe.cooking_time')

    class Meta:
        """Мета-класс для настройки сериализатора ShoppingCartSerializer."""

        model = ShoppingCart
        fields = ('id', 'name', 'image', 'cooking_time')


class FollowSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Follow (подписки на пользователей)."""

    is_subscribed = IsFollowedField(source='following',
                                    read_only=True,
                                    default=True)
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
    avatar = Base64ImageField(source='following.avatar', read_only=True)

    class Meta:
        """Мета-класс для настройки сериализатора FollowSerializer."""

        model = Follow
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name',
            'is_subscribed', 'recipes', 'recipes_count', 'avatar'
        )

    def get_recipes(self, obj):
        """Получает список рецептов автора."""
        request = self.context.get('request')
        recipes = obj.following.recipes.all()
        if request:
            recipes_limit = request.query_params.get('recipes_limit')
            if recipes_limit:
                if isinstance(recipes_limit, str) and recipes_limit.isdigit():
                    recipes_limit = int(recipes_limit)
                    if recipes_limit > 0:
                        recipes = recipes[:recipes_limit]
                elif isinstance(recipes_limit, int) and recipes_limit > 0:
                    recipes = recipes[:recipes_limit]
        return RecipeFollowFieldSerializer(
            recipes, many=True, context=self.context
        ).data

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Проверяет данные перед созданием подписки."""
        following = self.context.get('following')
        user = self.context['request'].user
        if user == following:
            raise serializers.ValidationError(
                {'errors': 'Нельзя подписаться на самого себя'},
                code=status.HTTP_400_BAD_REQUEST
            )
        if user.following.filter(following=following).exists():
            raise serializers.ValidationError(
                {'errors': 'Вы уже подписаны на этого пользователя'},
                code=status.HTTP_400_BAD_REQUEST
            )
        return data

    def create(self, validated_data: Dict[str, Any]) -> Follow:
        """Создает подписку на пользователя."""
        following = self.context.get('following')
        return Follow.objects.create(
            user=self.context['request'].user,
            following=following
        )
