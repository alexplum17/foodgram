"""backend/food/models.py."""

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from hashids import Hashids

from food.constants import (
    MAX_EMAIL_LENGTH,
    MAX_FIRST_NAME_LENGTH,
    MAX_INGREDIENT_NAME_LENGTH,
    MAX_LAST_NAME_LENGTH,
    MAX_MEASUREMENT_UNIT_LENGTH,
    MAX_RECIPE_NAME_LENGTH,
    MAX_SHORT_LINK_LENGTH,
    MAX_TAG_NAME_LENGTH,
    MAX_TAG_SLUG_LENGTH,
    MAX_USERNAME_LENGTH,
    MIN_COOKING_TIME,
    MIN_INGREDIENT_AMOUNT,
    SHORT_LINK_ALPHABET,
    SHORT_LINK_MIN_LENGTH,
)


def generate_hash(recipe_id):
    """Генерирует хеш для короткой ссылки на рецепт."""
    hashids = Hashids(
        min_length=SHORT_LINK_MIN_LENGTH,
        salt=settings.SECRET_KEY,
        alphabet=SHORT_LINK_ALPHABET
    )
    return hashids.encode(recipe_id)


class UserManager(BaseUserManager):
    """Менеджер для кастомной модели пользователя."""

    def create_user(self, username, email, password, **extra_fields):
        """Создает обычного пользователя."""
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        """Создает суперпользователя."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    """Кастомная модель пользователя."""

    username = models.CharField(
        max_length=MAX_USERNAME_LENGTH,
        blank=False,
        unique=True,
        help_text='Обязательное поле. Максимум 150 символов.',
        validators=[AbstractUser.username_validator],
        error_messages={
            'unique': 'Пользователь с таким именем уже существует.',
        },
    )
    email = models.EmailField(
        max_length=MAX_EMAIL_LENGTH,
        blank=False,
        unique=True,
        verbose_name='Электронная почта'
    )
    first_name = models.CharField(
        max_length=MAX_FIRST_NAME_LENGTH,
        blank=False,
        verbose_name='Имя'
    )
    last_name = models.CharField(
        max_length=MAX_LAST_NAME_LENGTH,
        blank=False,
        verbose_name='Фамилия'
    )
    objects = UserManager()

    class Meta:
        """Мета-класс для модели User.

        Определяет:
        - Названия в админке
        """

        app_label = 'food'
        swappable = 'AUTH_USER_MODEL'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        """Возвращает строковое представление пользователя."""
        return f"{self.username} ({self.first_name} {self.last_name})"


class Tag(models.Model):
    """Модель тега, используемого для категоризации рецептов."""

    name = models.CharField(
        max_length=MAX_TAG_NAME_LENGTH,
        unique=True,
        verbose_name='Название тега',
        help_text='Введите название тега.',
    )
    slug = models.SlugField(
        unique=True,
        verbose_name='Уникальный идентификатор',
        help_text='Введите уникальный идентификатор тега',
        max_length=MAX_TAG_SLUG_LENGTH,
        validators=[RegexValidator(
            regex='^[-a-zA-Z0-9_]+$',
            message='Разрешены только цифры и буквы'
        )]
    )

    class Meta:
        """Мета-класс для модели Tag.

        Определяет метаданные модели:
        - Название в единственном и множественном числе
        - Порядок сортировки по умолчанию
        """

        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'
        ordering = ['name']

    def __str__(self) -> str:
        """Возвращает строковое представление имени тега."""
        return self.name


class Ingredient(models.Model):
    """Модель, представляющая ингредиенты для рецептов."""

    name = models.CharField(
        max_length=MAX_INGREDIENT_NAME_LENGTH,
        verbose_name='Название ингридиента',
        help_text='Введите название ингридиента.',
    )
    measurement_unit = models.CharField(
        max_length=MAX_MEASUREMENT_UNIT_LENGTH,
        verbose_name='Единица измерения',
        help_text='Введите единицу измерения (штуки, граммы и т.д.).',
    )

    class Meta:
        """Мета-класс для модели Ingredient.

        Определяет:
        - Ограничения уникальности
        - Названия в админке
        """

        constraints = [
            models.UniqueConstraint(
                fields=['name', 'measurement_unit'],
                name='unique_ingredient'
            )
        ]
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'

    def __str__(self) -> str:
        """Возвращает строковое представление имени ингредиента."""
        return f'{self.name} ({self.measurement_unit})'


class Recipe(models.Model):
    """Модель, представляющая рецепт."""

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recipes',
        verbose_name='Автор рецепта',
    )
    name = models.CharField(
        max_length=MAX_RECIPE_NAME_LENGTH,
        verbose_name='Название рецепта',
        help_text='Введите название рецепта.',
    )
    image = models.ImageField(
        upload_to='recipes/images/',
        verbose_name='Изображение',
        help_text='Загрузите изображение рецепта.'
    )
    text = models.TextField(
        verbose_name='Описание рецепта',
        help_text='Введите описание рецепта.',
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        through='RecipeIngredient',
        verbose_name='Ингредиенты',
        help_text='Выберите ингредиенты для рецепта.'
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name='Теги',
        help_text='Выберите теги для рецепта.'
    )
    cooking_time = models.PositiveIntegerField(
        validators=[MinValueValidator(MIN_COOKING_TIME)],
        verbose_name='Время приготовления (в минутах)',
        help_text='Введите время приготовления в минутах.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    short_link = models.SlugField(
        max_length=MAX_SHORT_LINK_LENGTH,
        unique=True,
        blank=True,
        verbose_name='Короткая ссылка'
    )

    class Meta:
        """Мета-класс для модели Recipe.

        Определяет:
        - Названия в админке
        - Порядок сортировки по умолчанию
        """

        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ['-created_at']

    def clean(self) -> None:
        """Выполняет валидацию ингридиентов и тегов перед сохранением."""
        if self.pk:
            if not self.ingredients.exists():
                raise ValidationError(
                    'Рецепт должен содержать хотя бы один ингредиент'
                )
            if not self.tags.exists():
                raise ValidationError(
                    'Рецепт должен содержать хотя бы один тег'
                )

    def save(self, *args, **kwargs):
        """Сохраняет рецепт, генерируя короткую ссылку при необходимости."""
        super().save(*args, **kwargs)
        if not self.short_link:
            self.short_link = generate_hash(self.id)
            Recipe.objects.filter(id=self.id).update(
                short_link=self.short_link)

    def __str__(self) -> str:
        """Возвращает строковое представление названия рецепта."""
        return self.name


class RecipeIngredient(models.Model):
    """Модель, связывающая рецепты и ингредиенты с указанием количества."""

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='recipe_ingredients',
        verbose_name='Рецепт',
        help_text='Выберите рецепт, к которому относится этот ингредиент.'
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        verbose_name='Ингредиент',
        help_text='Выберите ингредиент.'
    )
    amount = models.PositiveIntegerField(
        verbose_name='Количество',
        validators=[MinValueValidator(MIN_INGREDIENT_AMOUNT)],
        help_text='Введите количество ингредиента (больше 0).'
    )

    class Meta:
        """Мета-класс для модели RecipeIngredient.

        Определяет:
        - Ограничения уникальности
        - Названия в админке
        """

        constraints = [
            models.UniqueConstraint(
                fields=['recipe', 'ingredient'],
                name='unique_recipe_ingredient'
            )
        ]
        verbose_name = 'Ингредиент рецепта'
        verbose_name_plural = 'Ингредиенты рецептов'

    def __str__(self) -> str:
        """Возвращает строковое представление связи рецепта и ингредиента."""
        return (f'{self.amount} {self.ingredient.measurement_unit} '
                f'{self.ingredient.name} для рецепта {self.recipe.name}')


class Profile(models.Model):
    """Модель профиля пользователя для хранения дополнительных данных."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    avatar = models.ImageField(
        upload_to='users/avatars/',
        blank=True,
        null=True
    )

    class Meta:
        """Мета-класс для модели Profile.

        Определяет:
        - Названия в админке
        - Порядок сортировки
        """

        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'
        ordering = ['user']

    def __str__(self) -> str:
        """Возвращает строковое представление профиля."""
        return f'Профиль пользователя {self.user.username}'


class Follow(models.Model):
    """Модель подписки пользователей друг на друга."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='following',
        verbose_name='Пользователь'
    )
    following = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='followers',
        verbose_name='Подписанный пользователь'
    )

    class Meta:
        """Мета-класс для модели Follow.

        Определяет:
        - Ограничения уникальности
        - Названия в админке
        """

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'following'],
                name='unique_follower'
            )
        ]
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'

    def clean(self) -> None:
        """Проверяет, что пользователь не подписывается на самого себя."""
        if self.user == self.following:
            raise ValidationError(
                'Пользователь не может подписаться на самого себя'
            )

    def __str__(self) -> str:
        """Возвращает строковое представление подписки."""
        return (f'Пользователь {self.user.username} '
                f'подписан на {self.following.username}')


class Favorite(models.Model):
    """Модель для хранения избранных рецептов пользователей."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь'
    )
    favorite = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='favorite',
        verbose_name='Избранное'
    )

    class Meta:
        """Мета-класс для модели Favorite.

        Определяет:
        - Ограничения уникальности
        - Названия в админке
        """

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'favorite'],
                name='unique_favorite'
            )
        ]
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'

    def __str__(self) -> str:
        """Возвращает строковое представление избранного рецепта."""
        return (f'Пользователь {self.user.username} '
                f'добавил в избранное {self.favorite.name}')


class ShoppingCart(models.Model):
    """Модель для хранения рецептов в списке покупок пользователя."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
        related_name='shopping_cart'
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='shopping_cart',
        verbose_name='Рецепт в списке покупок'
    )

    class Meta:
        """Мета-класс для модели ShoppingCart.

        Определяет:
        - Ограничения уникальности
        - Названия в админке
        """

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_shopping_cart'
            )
        ]
        verbose_name = 'Список покупок'
        verbose_name_plural = 'Списки покупок'

    def __str__(self) -> str:
        """Возвращает строковое представление списка покупок."""
        return (f'Пользователь {self.user.username} '
                f'добавил в список покупок {self.recipe.name}')
