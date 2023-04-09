from rest_framework.fields import IntegerField
from rest_framework.serializers import ModelSerializer

from foodcartapp.models import ProductInCart, Order


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

    def create(self):
        products = self.validated_data.pop('products')
        order = super().create(self.validated_data)
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

        return order
