"""backend/food/models.py."""

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from hashids import Hashids

from food.constants import (MAX_EMAIL_LENGTH, MAX_FIRST_NAME_LENGTH,
                            MAX_INGREDIENT_NAME_LENGTH, MAX_LAST_NAME_LENGTH,
                            MAX_MEASUREMENT_UNIT_LENGTH,
                            MAX_RECIPE_NAME_LENGTH, MAX_SHORT_LINK_LENGTH,
                            MAX_TAG_NAME_LENGTH, MAX_TAG_SLUG_LENGTH,
                            MAX_USERNAME_LENGTH, MIN_COOKING_TIME,
                            MIN_INGREDIENT_AMOUNT, SHORT_LINK_ALPHABET,
                            SHORT_LINK_MIN_LENGTH)


def generate_hash(recipe_id: int) -> str:
    """Генерирует хеш для короткой ссылки на рецепт."""
    hashids = Hashids(
        min_length=SHORT_LINK_MIN_LENGTH,
        salt=settings.SECRET_KEY,
        alphabet=SHORT_LINK_ALPHABET
    )
    return hashids.encode(recipe_id)


class UserManager(BaseUserManager):
    """Менеджер для кастомной модели пользователя."""

    def create_user(
            self,
            username: str,
            email: str,
            password: str,
            **extra_fields
    ) -> 'User':
        """Создает и сохраняет обычного пользователя."""
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self,
                         email: str,
                         username: str,
                         first_name: str,
                         last_name: str,
                         password: str = None,
                         **extra_fields
                         ) -> 'User':
        """Создает и сохраняет суперпользователя."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(
            email,
            username,
            first_name,
            last_name,
            password,
            **extra_fields
        )


class User(AbstractUser):
    """Кастомная модель пользователя."""

    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        max_length=MAX_USERNAME_LENGTH,
        blank=False,
        unique=True,
        help_text='Обязательное поле. Максимум 150 символов.',
        validators=[UnicodeUsernameValidator],
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
    avatar = models.ImageField(
        upload_to='users/avatars/',
        blank=True,
        default='',
        verbose_name='Аватар'
    )
    objects = UserManager()

    class Meta:
        """Мета-класс для модели User."""

        app_label = 'food'
        swappable = 'AUTH_USER_MODEL'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self) -> str:
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
    )

    class Meta:
        """Мета-класс для модели Tag."""

        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'
        ordering = ['name']

    def __str__(self) -> str:
        """Возвращает строковое представление тега."""
        return self.name


class Ingredient(models.Model):
    """Модель ингредиента для рецептов."""

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
        """Мета-класс для модели Ingredient."""

        constraints = [
            models.UniqueConstraint(
                fields=['name', 'measurement_unit'],
                name='unique_ingredient'
            )
        ]
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'

    def __str__(self) -> str:
        """Возвращает строковое представление ингредиента."""
        return f'{self.name} ({self.measurement_unit})'


class Recipe(models.Model):
    """Модель рецепта."""

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
        null=True,
        verbose_name='Короткая ссылка'
    )

    class Meta:
        """Мета-класс для модели Recipe."""

        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ['-created_at']

    def clean(self) -> None:
        """Проверяет наличие ингредиентов и тегов перед сохранением."""
        if self.pk:
            if not self.ingredients.exists():
                raise ValidationError(
                    'Рецепт должен содержать хотя бы один ингредиент'
                )
            if not self.tags.exists():
                raise ValidationError(
                    'Рецепт должен содержать хотя бы один тег'
                )

    def save(self, *args, **kwargs) -> None:
        """Сохраняет рецепт, генерируя короткую ссылку при необходимости."""
        is_new = not self.pk
        super().save(*args, **kwargs)
        if is_new and not self.short_link:
            self.short_link = generate_hash(self.id)
            super().save(update_fields=['short_link'])

    def __str__(self) -> str:
        """Возвращает строковое представление рецепта."""
        return self.name


class RecipeIngredient(models.Model):
    """Модель связи рецепта и ингредиента с указанием количества."""

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
        """Мета-класс для модели RecipeIngredient."""

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
        """Мета-класс для модели Follow."""

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


class UserRecipeBaseModel(models.Model):
    """
    Абстрактная базовая модель для связей пользователь-рецепт.

    Содержит общие поля и методы для Favorite и ShoppingCart.
    """

    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        verbose_name='Пользователь'
    )
    recipe = models.ForeignKey(
        'Recipe',
        on_delete=models.CASCADE,
        verbose_name='Рецепт'
    )

    class Meta:
        """Мета-класс для абстрактной модели UserRecipeBaseModel."""

        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_%(app_label)s_%(class)s'
            )
        ]

    def __str__(self):
        """Возвращает строковое представление связи пользователя и рецепта."""
        return f'{self.user.username} - {self.recipe.name}'


class Favorite(UserRecipeBaseModel):
    """Модель для хранения избранных рецептов пользователей."""

    class Meta(UserRecipeBaseModel.Meta):
        """Мета-класс для модели Favorite."""

        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранные рецепты'

    def __str__(self):
        """Возвращает строковое представление избранного рецепта."""
        return (f'Пользователь {self.user.username} '
                f'добавил в избранное {self.recipe.name}')


class ShoppingCart(UserRecipeBaseModel):
    """Модель для хранения рецептов в списке покупок пользователя."""

    class Meta(UserRecipeBaseModel.Meta):
        """Мета-класс для модели ShoppingCart."""

        verbose_name = 'Список покупок'
        verbose_name_plural = 'Списки покупок'

    def __str__(self):
        """Возвращает строковое представление списка покупок."""
        return (f'Пользователь {self.user.username} '
                f'добавил в список покупок {self.recipe.name}')