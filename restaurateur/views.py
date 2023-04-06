from typing import Iterator

import requests
from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet
from django.shortcuts import redirect, render
from django.utils.timezone import now
from django.views import View
from django.urls import reverse_lazy
from django.contrib.auth.decorators import user_passes_test

from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views
from geopy.distance import distance
from requests import HTTPError

from foodcartapp.models import Product, Restaurant, Order, RestaurantMenuItem
from places.models import Place

_latitude = float
_longitude = float


class Login(forms.Form):
    username = forms.CharField(
        label='Логин', max_length=75, required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Укажите имя пользователя'
        })
    )
    password = forms.CharField(
        label='Пароль', max_length=75, required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль'
        })
    )


class LoginView(View):
    def get(self, request, *args, **kwargs):
        form = Login()
        return render(request, "login.html", context={
            'form': form
        })

    def post(self, request):
        form = Login(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                if user.is_staff:  # FIXME replace with specific permission
                    return redirect("restaurateur:RestaurantView")
                return redirect("start_page")

        return render(request, "login.html", context={
            'form': form,
            'ivalid': True,
        })


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy('restaurateur:login')


def is_manager(user):
    return user.is_staff  # FIXME replace with specific permission


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_products(request):
    restaurants = list(Restaurant.objects.order_by('name'))
    products = list(Product.objects.prefetch_related('menu_items'))

    products_with_restaurant_availability = []
    for product in products:
        availability = {item.restaurant_id: item.availability for item in product.menu_items.all()}
        ordered_availability = [availability.get(restaurant.id, False) for restaurant in restaurants]

        products_with_restaurant_availability.append(
            (product, ordered_availability)
        )

    return render(request, template_name="products_list.html", context={
        'products_with_restaurant_availability': products_with_restaurant_availability,
        'restaurants': restaurants,
    })


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_restaurants(request):
    return render(request, template_name="restaurants_list.html", context={
        'restaurants': Restaurant.objects.all(),
    })


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_orders(request):
    orders = get_orders_with_available_restaurants()

    context = {
        'orders': [
            {
                'id': order.id,
                'status': order.get_status_display(),
                'payment': order.get_payment_display(),
                'cost': order.cost or 0,
                'client': f'{order.firstname} {order.lastname}',
                'phonenumber': order.phonenumber,
                'address': order.address,
                'restaurant': order.restaurant,
                'restaurants_with_distances': order.restaurants_with_distances,
                'geocoder_error': order.geocoder_error
            } for order in orders
        ],
        'current_url': request.path
    }
    return render(request, template_name='order_items.html', context=context)


def get_orders_with_available_restaurants():
    orders = Order.objects.all(). \
        calculate_costs(). \
        prefetch_related('products_in_cart__product'). \
        order_by('status', '-created_at')
    restaurant_menu_items = RestaurantMenuItem.objects.all().select_related('restaurant', 'product')
    all_restaurants = {menu_item.restaurant for menu_item in restaurant_menu_items}
    for order in orders:
        available_restaurants = set.intersection(
            all_restaurants,
            *group_restaurants_by_product(order, restaurant_menu_items)
        )
        try:
            restaurants_with_distances = dict(
                get_restaurant_with_distance_to_client(order, available_restaurants)
            )
        except HTTPError:
            order.restaurants_with_distances = []
            order.geocoder_error = True
        else:
            order.restaurants_with_distances = sorted(restaurants_with_distances.items(), key=lambda r: r[1])
            order.geocoder_error = False
    return orders


def get_restaurant_with_distance_to_client(order: Order, restaurants: set) -> Iterator[tuple[str, str]]:
    if order.restaurant:
        yield str(), str()
    for restaurant in restaurants:
        distance_to_client = distance(
            get_coordinates(order.address)[::-1],
            get_coordinates(restaurant.address)[::-1]
        ).km
        yield restaurant.name, f'{distance_to_client:0.3f}'


def group_restaurants_by_product(order: Order, restaurant_menu_items: QuerySet) -> list[set]:
    restaurants_grouped_by_products = []
    for product in order.products_in_cart.all():
        menu_item_filter = filter(
            lambda menu_item: menu_item.product == product.product,
            restaurant_menu_items
        )
        restaurants_grouped_by_products.append({
            menu_item.restaurant
            for menu_item in menu_item_filter
        })
    return restaurants_grouped_by_products


def get_coordinates(address: str) -> tuple[_latitude, _longitude]:
    try:
        place = Place.objects.get(address=address)
        timedelta_after_last_update = place.updated_at - now()
        if timedelta_after_last_update.days > 0:
            raise ObjectDoesNotExist
    except ObjectDoesNotExist:
        geocoder_api_key = settings.GEOCODER_API_KEY
        latitude, longitude = fetch_coordinates(geocoder_api_key, address)
        place = Place.objects.create(
            address=address,
            latitude=latitude,
            longitude=longitude
        )
    return place.latitude, place.longitude


def fetch_coordinates(apikey: str, address: str) -> tuple[_latitude, _longitude]:
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']

    if not found_places:
        return []

    most_relevant, *_ = found_places
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lon, lat
