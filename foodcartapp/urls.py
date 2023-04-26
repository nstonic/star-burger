from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import product_list_api, banners_list_api, OrderViewSet

app_name = "foodcartapp"

router = DefaultRouter()
router.register('order', OrderViewSet, basename='order')

urlpatterns = [
    path('products/', product_list_api),
    path('banners/', banners_list_api),
] + router.urls
