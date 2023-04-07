from pprint import pprint

from django.db import transaction
from rest_framework.fields import IntegerField
from rest_framework.response import Response
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.serializers import ModelSerializer

from .models import Product, Order, ProductInCart, Banner


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


class ProductSerializer(ModelSerializer):
    class Meta:
        model = ProductInCart
        fields = ['product', 'quantity']


class OrderSerializer(ModelSerializer):
    products = ProductSerializer(many=True, allow_empty=False, write_only=True)
    id = IntegerField(required=False)

    class Meta:
        model = Order
        fields = ['id', 'products', 'firstname', 'lastname', 'phonenumber', 'address']


@api_view(['POST'])
@transaction.atomic
def register_order(request):
    serializer = OrderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    products = serializer.validated_data.pop('products')
    order = Order.objects.create(**serializer.validated_data)
    products_in_cart = [
        ProductInCart(
            product=product['product'],
            order=order,
            quantity=product['quantity'],
            price=product['product'].price
        )
        for product in products
    ]
    ProductInCart.objects.bulk_create(products_in_cart)

    serializer = OrderSerializer(order)
    return Response(serializer.data)
