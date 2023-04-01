from django.core.exceptions import ObjectDoesNotExist, ValidationError
from rest_framework import status
from rest_framework.response import Response
from django.http import JsonResponse
from django.templatetags.static import static
from rest_framework.decorators import api_view

from .models import Product, Order, ProductInCart


def banners_list_api(request):
    # FIXME move data to db?
    return JsonResponse([
        {
            'title': 'Burger',
            'src': static('burger.jpg'),
            'text': 'Tasty Burger at your door step',
        },
        {
            'title': 'Spices',
            'src': static('food.jpg'),
            'text': 'All Cuisines',
        },
        {
            'title': 'New York',
            'src': static('tasty.jpg'),
            'text': 'Food is incomplete without a tasty dessert',
        }
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
def register_order(request):
    order_obj = request.data
    try:
        products = order_obj.pop('products')
    except KeyError:
        return Response(
            {'error': 'products key is not presented'},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    if not isinstance(products, list):
        return Response(
            {'error': 'products key must be list of product objects'},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    if not products:
        return Response(
            {'error': 'products list is empty'},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    order = Order.objects.create(**order_obj)

    products_in_cart = []
    for product in products:
        try:
            quantity = product['quantity']
            product = Product.objects.get(pk=product['product'])
            products_in_cart.append(
                ProductInCart(
                    product=product,
                    order=order,
                    quantity=quantity
                )
            )
        except ObjectDoesNotExist:
            return Response(
                {'error': 'product does not exists'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        except (TypeError, KeyError):
            return Response(
                {'error': 'product must be object with product and quantity keys'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

    ProductInCart.objects.bulk_create(products_in_cart)

    return Response({})
