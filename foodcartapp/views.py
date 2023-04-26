from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import JsonResponse

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


class OrderViewSet(viewsets.ViewSet):

    # @action(detail=True, methods=['post'])
    @transaction.atomic
    def create(self, request):
        phonenumber = request.data.get('phonenumber')
        if phonenumber and phonenumber.startswith('8'):
            request.data['phonenumber'] = f'+7{phonenumber[1:]}'

        serializer = OrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.create()
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    def update(self, request, pk):
        pass

    def partial_update(self, request, pk):
        pass

    # @action(detail=False, methods=['delete'])
    def destroy(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        order.delete()
        return Response()
