from django.urls import path, include
from rest_framework.routers import DefaultRouter
from product.views import *
from brandNew.views import *
from accessories.views import *
from accounts.views import *

router = DefaultRouter()
router.register(r'repair/brands', PhoneBrandViewSet, basename='phonebrand')
router.register(r'repair/models', PhoneModelViewSet, basename='phonemodel')
router.register(r'repair/problems', PhoneProblemViewSet, basename='phoneproblem')
router.register(r'repair/repair-prices', RepairPriceViewSet, basename='repairprice')
router.register(r'repair/orders', OrderViewSet, basename='order')
router.register(r'repair/discount', DiscountViewSet, basename='websitediscount')
router.register(r'repair/review', RepairReviewViewSet, basename='repair-review')

router.register(r'brandnew/brands', NewPhoneBrandViewSet, basename='newphonebrand')
router.register(r'brandnew/models', NewPhoneModelViewSet, basename='newphonemodel')
router.register(r'brandnew/discount', WebsiteDiscountViewSet, basename = 'newphonediscount')
router.register(r'brandnew/review', PhoneReviewViewSet, basename = 'newphonereview')
router.register(r'brandnew/color', PhoneColorViewSet, basename = 'newphonecolor')
router.register(r'brandnew/orders', NewPhoneOrderViewSet, basename = 'newphoneorder')
router.register(r'brandnew/stock-management', StockManagementViewSet, basename='stock-management')

router.register(r'accessories/products', AcsProductViewSet, basename='acsproduct')
router.register(r'accessories/discount', AcsWebsiteDiscountViewSet, basename='acsdiscount')
router.register(r'accessories/orders', AcsOrderViewSet, basename='acsorder')
router.register(r'accessories/review', AcsReviewViewSet, basename='acsreview')

urlpatterns = [
    path('', include(router.urls)),
    path('brandnew/admin/orders/', AdminOrderListView.as_view(), name='admin-order-list'),
    path('repair/admin/orders/', AdminRepairOrderListView.as_view(), name='admin-repair-order-list'),
    path('accessories/admin/orders/', AdminAcsOrderListView.as_view(), name='admin-acs-order-list'),
    path('admin/orders/', UnifiedAdminOrderListView.as_view(), name='unified-admin-orders'),
]