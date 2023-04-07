import copy
from typing import Iterable

import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet
from django.utils.timezone import now
from geopy.distance import distance
from requests import HTTPError

from foodcartapp.models import Order
from places.models import Place

_latitude = float
_longitude = float


def get_orders_with_available_restaurants(orders: QuerySet, restaurant_menu_items: QuerySet) -> QuerySet:
    all_restaurants = {menu_item.restaurant for menu_item in restaurant_menu_items}
    for order in orders:
        available_restaurants = set.intersection(
            all_restaurants,
            *_group_restaurants_by_product(order, restaurant_menu_items)
        )
        order.available_restaurants = copy.deepcopy(available_restaurants)
    return orders


def get_orders_with_distances_to_client(orders: QuerySet) -> QuerySet:
    for order in orders:
        order.distances_errors = False
        order_coordinates = order.place.latitude, order.place.longitude
        for restaurant in order.available_restaurants:
            if restaurant.place.with_an_error or order.place.with_an_error:
                restaurant.distance_to_client = None
                continue
            restaurant_coordinates = restaurant.place.latitude, restaurant.place.longitude
            distance_to_client = distance(
                restaurant_coordinates,
                order_coordinates
            ).km
            restaurant.distance_to_client = f'{distance_to_client:0.3f}'
        if not any(restaurant.distance_to_client for restaurant in order.available_restaurants):
            order.distances_errors = True
    return orders


def add_places_to_menu_items(restaurant_menu_items: QuerySet) -> QuerySet:
    restaurants_addresses = {menu_item.restaurant.address for menu_item in restaurant_menu_items}
    places = _get_places_for_addresses(restaurants_addresses)
    for menu_item in restaurant_menu_items:
        place = filter(lambda p: p.address == menu_item.restaurant.address, places)
        menu_item.restaurant.place = next(place)
    return restaurant_menu_items


def add_places_to_orders(orders: QuerySet) -> QuerySet:
    orders_addresses = {order.address for order in orders}
    places = _get_places_for_addresses(orders_addresses)
    for order in orders:
        place = filter(lambda p: p.address == order.address, places)
        order.place = next(place)
    return orders


def _group_restaurants_by_product(order: Order, restaurant_menu_items: QuerySet) -> list[set]:
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


def _get_places_for_addresses(addresses: Iterable[str]) -> list[Place]:
    places = []
    new_places = []
    for address in addresses:
        try:
            place = Place.objects.get(address=address)
            timedelta_after_last_update = place.updated_at - now()
            if timedelta_after_last_update.days > 0:
                raise ObjectDoesNotExist
            places.append(place)
        except ObjectDoesNotExist:
            geocoder_api_key = settings.GEOCODER_API_KEY
            with_an_error = False
            try:
                longitude, latitude = _fetch_coordinates(geocoder_api_key, address)
            except HTTPError:
                longitude, latitude = 0, 0
                with_an_error = True
            if address not in [place.address for place in new_places]:
                place = Place(
                    address=address,
                    latitude=latitude,
                    longitude=longitude,
                    with_an_error=with_an_error
                )
                new_places.append(place)
    places.extend(Place.objects.bulk_create(new_places))
    return places


def _fetch_coordinates(apikey: str, address: str) -> tuple[_longitude, _latitude]:
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']

    if not found_places:
        return _longitude(), _latitude()

    most_relevant, *_ = found_places
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lon, lat
