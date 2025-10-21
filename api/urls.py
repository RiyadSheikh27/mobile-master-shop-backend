from django.urls import path, include
from rest_framework.routers import DefaultRouter
from product.views import *
router = DefaultRouter()
router.register(r'brands', PhoneBrandViewSet, basename='phonebrand')
router.register(r'models', PhoneModelViewSet, basename='phonemodel')
router.register(r'problems', PhoneProblemViewSet, basename='phoneproblem')
router.register(r'repair-prices', RepairPriceViewSet, basename='repairprice')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'discounts', DiscountViewSet, basename='websitediscount')

urlpatterns = [
    path('', include(router.urls)),
]
