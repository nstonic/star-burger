import requests
from django.conf import settings
from django.db.models import QuerySet
from django.utils.timezone import now
from geopy.distance import distance
from requests.exceptions import HTTPError, JSONDecodeError

from foodcartapp.models import Order, RestaurantMenuItem, Restaurant
from places.models import Place

_lat = float
_lon = float


def get_orders_with_distances_to_client(
    orders: QuerySet[Order],
    restaurant_menu_items: QuerySet[RestaurantMenuItem]
) -> QuerySet:
    all_restaurants = {menu_item.restaurant for menu_item in restaurant_menu_items}
    all_places = _get_places(orders, all_restaurants)

    for order in orders:
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
    return orders


def _get_places(
    orders: QuerySet[Order],
    restaurants: set[Restaurant]
) -> dict[str:tuple[_lat, _lon]]:

    restaurants_addresses = {restaurant.address for restaurant in restaurants}
    orders_addresses = {order.address for order in orders}
    all_addresses = restaurants_addresses | orders_addresses
    geocoder_api_key = settings.GEOCODER_API_KEY

    places = dict()
    for address in all_addresses:
        place, place_created = Place.objects.get_or_create(address=address)
        timedelta_after_last_update = now() - place.updated_at

        if place_created or timedelta_after_last_update.days > 0:
            try:
                longitude, latitude = _fetch_coordinates(geocoder_api_key, address)
            except (HTTPError, JSONDecodeError, KeyError, TypeError):
                places[address] = False
                continue
            else:
                place.latitude = latitude
                place.longitude = longitude
                place.save()

        places[address] = place.latitude, place.longitude
    return places


def _fetch_coordinates(apikey: str, address: str) -> tuple[_lon, _lat] | list:
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
    return float(lon), float(lat)
