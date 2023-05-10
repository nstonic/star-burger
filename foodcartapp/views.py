from django.db import transaction
from django.http import JsonResponse
from rest_framework import mixins, viewsets

from .models import Product, Banner, Order
from .serializers import OrderSerializer, BannerSerializer


def banners_list_api(request):
    banners = Banner.objects.all().order_by('order')
    serialized_banners = [BannerSerializer(banner) for banner in banners]
    return JsonResponse([
        serializer.data
        for serializer in serialized_banners
    ], safe=False, json_dumps_params={
        'ensure_ascii': False,
        'indent': 4,
    })


def product_list_api(request):
    products = Product.objects.select_related('category').available()

    dumped_products = []
    for product in products:
        dumped_product = {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'special_status': product.special_status,
            'description': product.description,
            'category': {
                'id': product.category.id,
                'name': product.category.name,
            } if product.category else None,
            'image': product.image.url,
            'restaurant': {
                'id': product.id,
                'name': product.name,
            }
        }
        dumped_products.append(dumped_product)
    return JsonResponse(dumped_products, safe=False, json_dumps_params={
        'ensure_ascii': False,
        'indent': 4,
    })


class OrderViewSet(mixins.CreateModelMixin,
                   mixins.DestroyModelMixin,
                   mixins.UpdateModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = OrderSerializer
    queryset = Order.objects.all()

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        phonenumber = request.data.get('phonenumber')
        if phonenumber and phonenumber.startswith('8'):
            phonenumber.replace('8', '+7', 1)
        return super().create(request, *args, **kwargs)
