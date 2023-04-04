from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import QuerySet, Count, Sum, F
from django.utils.timezone import now
from phonenumber_field.modelfields import PhoneNumberField


class Restaurant(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )
    address = models.CharField(
        'адрес',
        max_length=100,
        blank=True,
    )
    contact_phone = models.CharField(
        'контактный телефон',
        max_length=50,
        blank=True,
    )

    class Meta:
        verbose_name = 'ресторан'
        verbose_name_plural = 'рестораны'

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def available(self):
        products = (
            RestaurantMenuItem.objects
            .filter(availability=True)
            .values_list('product')
        )
        return self.filter(pk__in=products)


class ProductCategory(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )
    category = models.ForeignKey(
        ProductCategory,
        verbose_name='категория',
        related_name='products',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    price = models.DecimalField(
        'цена',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    image = models.ImageField(
        'картинка'
    )
    special_status = models.BooleanField(
        'спец.предложение',
        default=False,
        db_index=True,
    )
    description = models.TextField(
        'описание',
        max_length=200,
        blank=True,
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'

    def __str__(self):
        return self.name


class RestaurantMenuItem(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        related_name='menu_items',
        verbose_name="ресторан",
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='menu_items',
        verbose_name='продукт',
    )
    availability = models.BooleanField(
        'в продаже',
        default=True,
        db_index=True
    )

    class Meta:
        verbose_name = 'пункт меню ресторана'
        verbose_name_plural = 'пункты меню ресторана'
        unique_together = [
            ['restaurant', 'product']
        ]

    def __str__(self):
        return f"{self.restaurant.name} - {self.product.name}"


class ProductInCart(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='in_carts',
        verbose_name='Товар',
        db_index=True
    )
    quantity = models.PositiveIntegerField('Количество')
    order = models.ForeignKey(
        'Order',
        on_delete=models.CASCADE,
        related_name='products_in_cart',
        verbose_name='Заказ',
        db_index=True
    )
    price = models.DecimalField(
        'Цена',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        verbose_name = 'Продукт в корзине'
        verbose_name_plural = 'Продукты в корзинах'

    def __str__(self):
        return f'Заказ {self.order}: {self.product} - {self.quantity}'


class OrderQuerySet(QuerySet):
    def calculate_costs(self):
        return self.annotate(
            cost=Sum(
                F('products_in_cart__price') * F('products_in_cart__quantity')
            ))


class Order(models.Model):
    STATUSES = [
        ('NEW', 'Необработан'),
        ('PICKING', 'Сборка'),
        ('DELIVERING', 'Доставка'),
        ('CLOSED', 'Завершён'),
        ('CANCELED', 'Отменён')
    ]

    address = models.CharField('Адрес', max_length=200)
    firstname = models.CharField('Имя', max_length=30)
    lastname = models.CharField('Фамилия', max_length=50)
    phonenumber = PhoneNumberField('Телефон', region='RU', db_index=True)
    created_at = models.DateTimeField('Создан', default=now)
    comment = models.TextField('Комментарий', null=True, blank=True)
    status = models.CharField(
        'Статус',
        max_length=10,
        choices=STATUSES,
        default='NEW',
        db_index=True
    )
    objects = OrderQuerySet.as_manager()

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ от {self.created_at.strftime("%d.%m.%Y %H:%M:%S")}'
