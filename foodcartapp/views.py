import phonenumbers
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
    if error_message := validate_order(order_obj):
        return entity_error(error_message)

    products = order_obj.pop('products')
    order = Order.objects.create(**order_obj)
    products_in_cart = []
    for product in products:
        quantity = product['quantity']
        try:
            product = Product.objects.get(pk=product['product'])
        except ObjectDoesNotExist:
            return entity_error(f'unknown product with id {product["product"]}')
        else:
            products_in_cart.append(
                ProductInCart(
                    product=product,
                    order=order,
                    quantity=quantity
                )
            )
    ProductInCart.objects.bulk_create(products_in_cart)
    return Response({})


def entity_error(msg: str):
    return Response(
        {'error': msg},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


def validate_order(order_obj: dict) -> str | None:
    order_fields = {'products': list, 'firstname': str, 'lastname': str, 'phonenumber': str, 'address': str}
    product_fields = {'product': int, 'quantity': int}
    missing_fields = []
    null_fields = []

    def validate_fields(obj, required_fields):
        nonlocal null_fields
        nonlocal missing_fields

        for field in required_fields:
            if field not in obj:
                missing_fields.append(field)

        for field, value in obj.items():
            if field in required_fields:
                if not value:
                    null_fields.append(field)
                    continue
                required_type = required_fields[field]
                if not isinstance(value, required_type):
                    return f'{field} must be {required_type.__name__}, not {type(value).__name__}'

    if error_message := validate_fields(order_obj, order_fields):
        return error_message

    if 'products' in order_obj:
        products = order_obj['products']
        if not products:
            return f'products cannot be empty list or null'

        for product in products:
            if error_message := validate_fields(product, product_fields):
                return error_message

    if missing_fields:
        return f'{", ".join(missing_fields)} is required fields'

    if null_fields:
        return f'{", ".join(null_fields)} cannot be null or empty'

    phone_number = phonenumbers.parse(order_obj['phonenumber'], 'RU')
    if not phonenumbers.is_valid_number(phone_number):
        return 'invalid phonenumber'
