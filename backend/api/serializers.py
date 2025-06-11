import base64
from typing import Any, Dict, List, Union

from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from food.constants import (
    DEFAULT_PAGE_SIZE,
    MAX_EMAIL_LENGTH,
    MAX_FIRST_NAME_LENGTH,
    MAX_INGREDIENT_NAME_LENGTH,
    MAX_LAST_NAME_LENGTH,
    MAX_MEASUREMENT_UNIT_LENGTH,
    MAX_PAGE_SIZE,
    MAX_RECIPE_NAME_LENGTH,
    MAX_TAG_NAME_LENGTH,
    MAX_TAG_SLUG_LENGTH,
    MAX_USERNAME_LENGTH,
    MIN_COOKING_TIME,
    MIN_INGREDIENT_AMOUNT,
)
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

    def to_representation(self, value):
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

    def update(self, instance, validated_data):
        """Обновляет аватар пользователя."""
        instance.profile.avatar = validated_data['avatar']
        instance.profile.save()
        return instance


class IsFavoritedField(serializers.Field):
    """Кастомное поле для проверки, находится ли рецепт в избранном."""

    def to_representation(self, obj: Recipe) -> bool:
        """Проверяет, добавлен ли рецепт в избранное."""
        if hasattr(obj, 'is_favorited'):
            return obj.is_favorited
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
        if hasattr(obj, 'is_in_shopping_cart'):
            return obj.is_in_shopping_cart
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
    """Сериализатор для создания пользователя."""

    first_name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=MAX_FIRST_NAME_LENGTH
    )
    last_name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=MAX_LAST_NAME_LENGTH
    )
    email = serializers.EmailField(
        required=True,
        max_length=MAX_EMAIL_LENGTH
    )
    username = serializers.CharField(
        max_length=MAX_USERNAME_LENGTH,
        validators=[AbstractUser.username_validator]
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
            'password': {'write_only': True}
        }

    def validate(self, data):
        """Проверяет валидность данных пользователя."""
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
        """Проверяет валидность имени пользователя."""
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
        """Проверяет валидность email."""
        if len(value) > MAX_EMAIL_LENGTH:
            raise serializers.ValidationError(
                'Email не может превышать 254 символа.',
                code=status.HTTP_400_BAD_REQUEST
            )
        return value

    def validate_password(self, value):
        """Проверяет валидность пароля."""
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

    def to_representation(self, instance):
        """Переопределяет представление для отображения подписки."""
        representation = super().to_representation(instance)
        representation['is_subscribed'
                       ] = IsFollowedField().to_representation(instance)
        return representation


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
        """Мета-класс для настройки сериализатора связи рецепта и ингредиента.

        Определяет:
        - Модель, с которой работает сериализатор (RecipeIngredient)
        - Поля, которые включаются в сериализацию
        - Переопределенные поля (id, name, measurement_unit, amount)
        """

        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')

    def validate_amount(
            self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Проверяет, что количество игредиентов не меньше одного."""
        if value < 1:
            raise serializers.ValidationError(
                'Количество ингредиентов не может быть меньше одного'
            )
        return value


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для рецептов."""

    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True
    )
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

    def to_representation(self, instance):
        """Переопределяем представление для правильного отображения тегов."""
        representation = super().to_representation(instance)
        representation['tags'] = TagSerializer(
            instance.tags.all(),
            many=True
        ).data
        representation['is_favorited'] = IsFavoritedField(
        ).to_representation(instance)
        representation['is_in_shopping_cart'] = IsInShoppingCartField(
        ).to_representation(instance)
        return representation

    def _process_ingredients(self, recipe, ingredients_data):
        """Обрабатывает ингредиенты (создание/обновление)."""
        recipe.recipe_ingredients.all().delete()
        RecipeIngredient.objects.bulk_create([
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient_data['id'],
                amount=ingredient_data['amount']
            )
            for ingredient_data in ingredients_data
        ])

    def create(self, validated_data):
        """Создаёт рецепт с тегами и ингредиентами."""
        tags_data = validated_data.pop('tags', [])
        ingredients_data = validated_data.pop('recipe_ingredients', [])
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags_data)
        self._process_ingredients(recipe, ingredients_data)
        return recipe

    def update(self, instance, validated_data):
        """Обновляет рецепт, теги и ингредиенты."""
        tags_data = validated_data.pop('tags')
        ingredients_data = validated_data.pop('recipe_ingredients')
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        instance.tags.set(tags_data)
        self._process_ingredients(instance, ingredients_data)
        return instance

    def validate(self, data):
        """Проверяет данные рецепта перед сохранением."""
        if self.context['request'].method == 'PATCH':
            if 'tags' not in data and 'recipe_ingredients' not in data:
                raise serializers.ValidationError(
                    'Для обновления рецепта необходимо указать'
                    'как теги, так и ингредиенты.'
                )
            if 'tags' not in data:
                raise serializers.ValidationError(
                    {'tags': 'Это поле обязательно при обновлении рецепта.'}
                )
            if 'recipe_ingredients' not in data:
                raise serializers.ValidationError(
                    {'ingredients':
                     'Это поле обязательно при обновлении рецепта.'}
                )
        return data

    def validate_ingredients(
            self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Валидация поля ингредиентов."""
        if not value:
            raise serializers.ValidationError(
                'Добавьте хотя бы один ингредиент.'
            )
        ingredient_ids = [ingredient['id'].id for ingredient in value]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                'Ингредиенты в рецепте не должны повторяться.'
            )
        return value

    def validate_tags(self, value: List[Tag]) -> List[Tag]:
        """Проверяет поле тегов."""
        if not value:
            raise serializers.ValidationError(
                'Добавьте хотя бы один тег'
            )
        tag_ids = [tag.id for tag in value]
        if len(tag_ids) != len(set(tag_ids)):
            raise serializers.ValidationError(
                'Теги не должны повторяться'
            )
        return value

    def validate_cooking_time(self, value):
        """Валидация времени приготовления."""
        if value < MIN_COOKING_TIME:
            raise serializers.ValidationError(
                'Время приготовления должно быть не менее 1 минуты'
            )
        return value


class FavoriteSerializer(serializers.ModelSerializer):
    """Сериализатор для избранных рецептов."""

    name = serializers.ReadOnlyField(source='favorite.name')
    image = Base64ImageField(source='favorite.image')
    cooking_time = serializers.ReadOnlyField(source='favorite.cooking_time')

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

    is_subscribed = IsFollowedField(source='following')
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
        recipes = obj.following.recipes.all()
        if request:
            recipes_limit = request.query_params.get('recipes_limit')
            if recipes_limit and str(recipes_limit).isdigit():
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
        """Проверка, что пользователь не пытается подписаться на самого себя."""
        if self.context['request'].user == data['following']:
            raise serializers.ValidationError(
                'Нельзя подписаться на самого себя'
            )
        return data
