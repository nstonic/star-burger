from adminsortable2.admin import SortableAdminMixin
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import reverse
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now

from .models import Product, ProductInCart, Order, Banner
from .models import ProductCategory
from .models import Restaurant
from .models import RestaurantMenuItem


class RestaurantMenuItemInline(admin.TabularInline):
    model = RestaurantMenuItem
    extra = 0


class PreviewAdminMixin:

    @staticmethod
    def get_img_attr(obj, possible_attrs):
        for attr in possible_attrs:
            if hasattr(obj, attr):
                return getattr(obj, attr)

    def get_image_preview(self, obj):
        img = PreviewAdminMixin.get_img_attr(obj, ['image', 'src'])
        if not img:
            return 'выберите картинку'
        return format_html('<img src="{url}" style="max-height: 200px;"/>', url=img.url)

    get_image_preview.short_description = 'превью'

    def get_image_list_preview(self, obj):
        img = PreviewAdminMixin.get_img_attr(obj, ['image', 'src'])
        if not img or not obj.id:
            return 'нет картинки'
        edit_url = reverse('admin:foodcartapp_product_change', args=(obj.id,))
        return format_html('<a href="{edit_url}"><img src="{src}" style="max-height: 50px;"/></a>', edit_url=edit_url,
                           src=img.url)

    get_image_list_preview.short_description = 'превью'


@admin.register(Banner)
class BannerAdmin(PreviewAdminMixin, SortableAdminMixin, admin.ModelAdmin):
    search_fields = [
        'title',
        'text'
    ]
    list_display = [
        'title',
        'get_image_list_preview',
        'text'
    ]
    readonly_fields = [
        'get_image_preview',
    ]
    ordering = ['order']


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    search_fields = [
        'name',
        'address',
        'contact_phone',
    ]
    list_display = [
        'name',
        'address',
        'contact_phone',
    ]
    inlines = [
        RestaurantMenuItemInline
    ]


@admin.register(Product)
class ProductAdmin(PreviewAdminMixin, admin.ModelAdmin):
    list_display = [
        'get_image_list_preview',
        'name',
        'category',
        'price',
    ]
    list_display_links = [
        'name',
    ]
    list_filter = [
        'category',
    ]
    search_fields = [
        'name',
        'category__name',
    ]

    inlines = [
        RestaurantMenuItemInline
    ]
    fieldsets = (
        ('Общее', {
            'fields': [
                'name',
                'category',
                'image',
                'get_image_preview',
                'price',
            ]
        }),
        ('Подробно', {
            'fields': [
                'special_status',
                'description',
            ],
            'classes': [
                'wide'
            ],
        }),
    )

    readonly_fields = [
        'get_image_preview',
    ]

    class Media:
        css = {
            "all": (
                static("admin/foodcartapp.css")
            )
        }


@admin.register(ProductCategory)
class ProductAdmin(admin.ModelAdmin):
    pass


class ProductInCartInline(admin.TabularInline):
    model = ProductInCart
    extra = 0
    readonly_fields = [
        'price'
    ]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    search_fields = [
        'phonenumber',
        'address',
        'firstname',
        'lastname'
    ]
    list_display = [
        'id',
        'status',
        'created_at',
        'phonenumber',
        'address'
    ]
    list_display_links = [
        'id'
    ]
    readonly_fields = [
        'created_at',
        'processed_at',
        'finished_at'
    ]
    list_filter = [
        'status'
    ]
    inlines = [
        ProductInCartInline
    ]

    def save_form(self, request, form, change):
        instance = form.save(commit=False)
        if not instance.processed_at and instance.payment and instance.restaurant:
            instance.processed_at = now()
            instance.status = 'PICKING'
        if not instance.finished_at and instance.status in ['CLOSED', 'CANCELED']:
            instance.finished_at = now()
        return form.save(commit=False)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if not change or not instance.price:
                instance.price = instance.product.price
            instance.save()
        formset.save()

    def response_change(self, request, obj):
        response = super().response_change(request, obj)
        next_url = request.GET.get('next')
        next_url_is_allowed = url_has_allowed_host_and_scheme(next_url, settings.ALLOWED_HOSTS)
        if next_url and next_url_is_allowed:
            return HttpResponseRedirect(next_url)
        else:
            return response

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'restaurant':
            order_id = request.resolver_match.kwargs['object_id']
            order = Order.objects.filter(pk=order_id).get_available_restaurants().first()
            available_restaurants_ids = {restaurant.id for restaurant in order.available_restaurants}
            kwargs['queryset'] = Restaurant.objects.filter(pk__in=available_restaurants_ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
