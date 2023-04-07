from django.db import models
from django.utils.timezone import now


class Place(models.Model):
    latitude = models.FloatField('Долгота')
    longitude = models.FloatField('Широта')
    address = models.CharField(
        'Адрес',
        max_length=100,
        db_index=True,
        unique=True
    )
    updated_at = models.DateTimeField(
        'Последнее обновление',
        default=now,
        db_index=True
    )
    with_an_error = models.BooleanField('Ошибка определения координат', default=False)

    class Meta:
        verbose_name = 'Место'
        verbose_name_plural = 'Места'
