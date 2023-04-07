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


def get_orders_with_distances_to_client(orders: QuerySet, all_restaurants) -> QuerySet:
    restaurants_addresses = {restaurant.address for restaurant in all_restaurants}
    orders_addresses = {order.address for order in orders}
    all_places = _get_places_by_addresses(restaurants_addresses | orders_addresses)

    for order in orders:
        order.distances_errors = False
        order_coordinates = all_places[order.address]
        for restaurant in order.available_restaurants:
            restaurant_coordinates = all_places[restaurant.address]
            if not order_coordinates or not restaurant_coordinates:
                order.distances_errors = True
                break
            distance_to_client = distance(
                restaurant_coordinates,
                order_coordinates
            ).km
            restaurant.distance_to_client = f'{distance_to_client:0.3f}'
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


def _get_places_by_addresses(addresses: Iterable[str]) -> dict[str:tuple[_latitude, _longitude]]:
    places = dict()
    new_places = set()
    for address in addresses:
        try:
            place = Place.objects.get(address=address)
            timedelta_after_last_update = place.updated_at - now()
            if timedelta_after_last_update.days > 0:
                raise ObjectDoesNotExist
            places[address] = place.latitude, place.longitude
        except ObjectDoesNotExist:
            geocoder_api_key = settings.GEOCODER_API_KEY
            try:
                longitude, latitude = _fetch_coordinates(geocoder_api_key, address)
            except HTTPError:
                places[address] = False
            else:
                places[address] = latitude, longitude
                new_places.add(Place(
                    address=address,
                    latitude=latitude,
                    longitude=longitude
                ))
    Place.objects.bulk_create(new_places)
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
        return []

    most_relevant, *_ = found_places
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lon, lat
