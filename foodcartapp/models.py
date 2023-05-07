from copy import deepcopy

from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import QuerySet, Sum, F
from django.utils.timezone import now
from geopy.distance import distance
from phonenumber_field.modelfields import PhoneNumberField

from foodcartapp.geo_services import _get_places


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
    quantity = models.PositiveIntegerField(
        'Количество',
        validators=[MinValueValidator(1)]
    )
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
        self.prefetch_related('products_in_cart')
        return self.annotate(
            cost=Sum(
                F('products_in_cart__price') * F('products_in_cart__quantity')
            ))

    def filter_active(self):
        return self.filter(status__in=['NEW', 'PICKING', 'DELIVERING']). \
            calculate_costs(). \
            prefetch_related('products_in_cart__product'). \
            order_by('status', '-created_at')

    def get_available_restaurants(self):
        orders_ids = (str(order.id) for order in self)
        available_restaurants = super().raw(
            """
            SELECT pic.id, rmi.id, o.id ord_id, r.id res_id
            FROM foodcartapp_order o
            JOIN foodcartapp_productincart pic ON pic.order_id=o.id
            JOIN foodcartapp_restaurantmenuitem rmi ON pic.product_id=rmi.product_id
            JOIN foodcartapp_restaurant r ON rmi.product_id=r.id
            WHERE o.id IN ({})
            """.format(','.join(orders_ids))
            # Пришлось использовать format. Джанговый плейсхолдер %s автоматически оборачивается в кавычки
        )
        restaurants = Restaurant.objects.all()
        for order in self:
            order_rests = filter(
                lambda order_rest: order_rest.ord_id == order.id,
                available_restaurants
            )
            order_restaurants_ids = [
                order_rest.res_id
                for order_rest in order_rests
            ]
            order.available_restaurants = [
                deepcopy(restaurant)
                for restaurant in restaurants
                if restaurant.id in order_restaurants_ids
            ]
        return self

    def get_distances_to_client(self):
        restaurant_addresses = set()
        for order in self:
            for restaurant in order.available_restaurants:
                restaurant_addresses.add(restaurant.address)
        orders_addresses = {order.address for order in self}
        all_places = _get_places(restaurant_addresses | orders_addresses)

        for order in self:
            order.distance_error = False
            order_coordinates = all_places[order.address]
            for restaurant in order.available_restaurants:
                restaurant_coordinates = all_places[restaurant.address]
                if not order_coordinates or not restaurant_coordinates:
                    order.distance_error = True
                    break
                distance_to_client = distance(
                    restaurant_coordinates,
                    order_coordinates
                ).km
                restaurant.distance_to_client = f'{distance_to_client:0.3f}'
        return self


class Order(models.Model):
    STATUSES = [
        ('NEW', 'Необработан'),
        ('PICKING', 'Сборка'),
        ('DELIVERING', 'Доставка'),
        ('CLOSED', 'Завершён'),
        ('CANCELED', 'Отменён')
    ]

    PAYMENT_FORMS = [
        ('CASH', 'Наличка'),
        ('CASHLESS', 'Безнал')
    ]

    address = models.CharField('Адрес', max_length=200)
    firstname = models.CharField('Имя', max_length=30)
    lastname = models.CharField('Фамилия', max_length=50)
    phonenumber = PhoneNumberField('Телефон', region='RU', db_index=True)
    created_at = models.DateTimeField('Создан', default=now, db_index=True)
    comment = models.TextField('Комментарий', blank=True)
    processed_at = models.DateTimeField(
        'Обработан менеджером',
        blank=True,
        null=True,
        db_index=True
    )
    finished_at = models.DateTimeField(
        'Завершён',
        blank=True,
        null=True,
        db_index=True
    )
    restaurant = models.ForeignKey(
        Restaurant,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name='Ресторан'
    )
    status = models.CharField(
        'Статус',
        max_length=10,
        choices=STATUSES,
        default='NEW',
        db_index=True
    )
    payment = models.CharField(
        'Способ оплаты',
        max_length=10,
        choices=PAYMENT_FORMS,
        db_index=True
    )
    objects = OrderQuerySet.as_manager()

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ от {self.created_at.strftime("%d.%m.%Y %H:%M:%S")}'


class Banner(models.Model):
    title = models.CharField('Название', max_length=32)
    src = models.ImageField('Изображение', upload_to='banners/')
    text = models.CharField('Текст', max_length=100, blank=True, null=True)
    order = models.PositiveIntegerField(default=0, blank=True, null=True, db_index=True)

    class Meta:
        verbose_name = 'Баннер'
        verbose_name_plural = 'Баннеры'
        ordering = ['order']
