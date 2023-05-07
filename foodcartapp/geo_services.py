import requests
from django.conf import settings
from django.utils.timezone import now
from requests.exceptions import HTTPError, JSONDecodeError

from places.models import Place

_lat = float
_lon = float


def _get_places(addresses):
    geocoder_api_key = settings.GEOCODER_API_KEY

    places = dict()
    for address in addresses:
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
