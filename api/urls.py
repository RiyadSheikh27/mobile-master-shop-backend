from django.urls import path, include
from rest_framework.routers import DefaultRouter
from product.views import *
from brandNew.views import *
from accessories.views import *

router = DefaultRouter()
router.register(r'repair/brands', PhoneBrandViewSet, basename='phonebrand')
router.register(r'repair/models', PhoneModelViewSet, basename='phonemodel')
router.register(r'repair/problems', PhoneProblemViewSet, basename='phoneproblem')
router.register(r'repair/repair-prices', RepairPriceViewSet, basename='repairprice')
router.register(r'repair/orders', OrderViewSet, basename='order')
router.register(r'repair/discounts', DiscountViewSet, basename='websitediscount')

router.register(r'brandnew/brands', PhoneBrandViewSet, basename='newphonebrand')
router.register(r'brandnew/models', NewPhoneModelViewSet, basename='newphonemodel')
router.register(r'brandnew/discount', WebsiteDiscountViewSet, basename = 'newphonediscount')
router.register(r'brandnew/review', PhoneReviewViewSet, basename = 'newphonereview')
router.register(r'brandnew/color', PhoneColorViewSet, basename = 'newphonecolor')
router.register(r'brandnew/orders', NewPhoneOrderViewSet, basename = 'newphoneorder')

router.register(r'accessories/products', AcsProductViewSet, basename='acsproduct')
router.register(r'accessories/discount', AcsWebsiteDiscountViewSet, basename='acsdiscount')
router.register(r'accessories/orders', AcsOrderViewSet, basename='acsorder')
router.register(r'accessories/reviews', AcsReviewViewSet, basename='acsreview')

urlpatterns = [
    path('', include(router.urls)),
]