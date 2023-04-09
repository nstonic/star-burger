from django.db import transaction
from rest_framework.response import Response
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.serializers import ModelSerializer

from .models import Product, Banner
from .order_serializers import OrderSerializer


class BannerSerializer(ModelSerializer):
    class Meta:
        model = Banner
        fields = ['title', 'src', 'text', 'order']


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


@api_view(['POST'])
@transaction.atomic
def register_order(request):
    serializer = OrderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    order = serializer.create()
    serializer = OrderSerializer(order)
    return Response(serializer.data)
