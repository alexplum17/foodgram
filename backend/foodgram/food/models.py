from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

User = get_user_model()


class Tag(models.Model):
    """Модель тега, используемого для категоризации рецептов."""

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Название тега',
        help_text='Введите название тега.',
    )
    slug = models.SlugField(
        unique=True,
        verbose_name='Уникальный идентификатор',
        help_text='Введите уникальный идентификатор тега (латиница, цифры)'
    )

    class Meta:
        """Meta-класс для модели Tag."""

        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'
        ordering = ['name']

    def __str__(self):
        """Возвращает строковое представление имени тега."""
        return self.name


class Ingredient(models.Model):
    """Модель, представляющая ингредиенты для рецептов."""

    name = models.CharField(
        max_length=100,
        verbose_name='Название ингридиента',
        help_text='Введите название ингридиента.',
    )
    measurement_unit = models.CharField(
        max_length=20,
        verbose_name='Единица измерения',
        help_text='Введите единицу измерения (штуки, граммы и т.д.).',
    )

    class Meta:
        """Meta-класс для модели Ingredient."""

        constraints = [
            models.UniqueConstraint(
                fields=['name', 'measurement_unit'],
                name='unique_ingredient'
            )
        ]
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'

    def __str__(self):
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
        max_length=256,
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
        validators=[MinValueValidator(1)],
        verbose_name='Время приготовления (в минутах)',
        help_text='Введите время приготовления в минутах.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        """Meta-класс для модели Recipe."""

        ordering = ['-created_at']

    def clean(self):
        """Выполняет валидацию ингридиентов и тегов."""
        if not self.ingredients.exists():
            raise ValidationError(
                'Рецепт должен содержать хотя бы один ингредиент'
            )
        if not self.tags.exists():
            raise ValidationError(
                'Рецепт должен содержать хотя бы один тег'
            )

    def __str__(self):
        """Возвращает строковое представление названия рецепта."""
        return self.name


class RecipeIngredient(models.Model):
    """
    Модель, связывающая рецепты и ингредиенты.

    Позволяет указать количество каждого ингредиента.
    """

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
        help_text='Выберите рецепт, к которому относится этот ингредиент.'
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        verbose_name='Ингредиент',
        help_text='Выберите ингредиент.'
    )
    quantity = models.PositiveIntegerField(
        verbose_name='Количество',
        validators=[MinValueValidator(1)],
        help_text='Введите количество ингредиента (больше 0).'
    )

    class Meta:
        """Meta-класс для модели RecipeIngredient."""

        unique_together = ('recipe', 'ingredient')
        verbose_name = 'Ингредиент рецепта'
        verbose_name_plural = 'Ингредиенты рецептов'

    def __str__(self):
        """
        Возвращает строковое представление объекта RecipeIngredient.

        Объект RecipeIngredient показывает количество, единицу
        измерения и название ингредиента для указанного рецепта.
        """
        return (f'{self.quantity} {self.ingredient.measurement_unit}'
                f' {self.ingredient.name} для рецепта {self.recipe.name}')


class Profile(models.Model):
    """Модель для представления профиля пользователя."""

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


class Follow(models.Model):
    """
    Модель для представления подписки пользователя на другого пользователя.

    Пользователь не может подписаться на самого себя.
    """

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
        """Meta-класс для модели Follow."""

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'following'],
                name='unique_follower'
            )
        ]
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'

    def clean(self):
        """Выполняет валидацию подписки на самого себя."""
        if self.user == self.following:
            raise ValidationError(
                'Пользователь не может подписаться на самого себя'
            )

    def __str__(self):
        """Возвращает строковое представление подписки."""
        return (f'Пользователь {self.user.username} '
                f'подписан на пользователя {self.following.username}')


class Favorite(models.Model):
    """Модель для представления рецепта в разделе "Избранное"."""

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
        """Meta-класс для модели Favorite."""

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'favorite'],
                name='unique_favotite'
            )
        ]
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'

    def __str__(self):
        """Возвращает строковое представление избранного."""
        return (f'Пользователь {self.user.username} '
                f'добавил в избранное рецепт {self.favorite.name}')


class ShoppingCart(models.Model):
    """Модель для представления рецепта в списке покупок."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь'
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='shopping_cart',
        verbose_name='Рецепт в списке покупок'
    )

    class Meta:
        """Meta-класс для модели ShoppingCart."""

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_shopping_cart'
            )
        ]
        verbose_name = 'Список покупок'
        verbose_name_plural = 'Списки покупок'

    def __str__(self):
        """Возвращает строковое представление списка покупок."""
        return (f'Пользователь {self.user.username} '
                f'добавил в список покупок рецепт {self.recipe.name}')
