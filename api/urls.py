from django.urls import path, include
from rest_framework.routers import DefaultRouter
from product.views import *
from newphone.views import *

router = DefaultRouter()
router.register(r'repair/brands', PhoneBrandViewSet, basename='phonebrand')
router.register(r'repair/models', PhoneModelViewSet, basename='phonemodel')
router.register(r'repair/problems', PhoneProblemViewSet, basename='phoneproblem')
router.register(r'repair/repair-prices', RepairPriceViewSet, basename='repairprice')
router.register(r'repair/orders', OrderViewSet, basename='order')
router.register(r'repair/discounts', DiscountViewSet, basename='websitediscount')

router.register(r'phone/brands', NewPhoneBrandViewSet, basename='new-phone-brand')
router.register(r'phone/colors', PhoneColorViewSet, basename='phone-color')
router.register(r'phone/models', NewPhoneModelViewSet, basename='new-phone-model')

urlpatterns = [
    path('', include(router.urls)),
]
