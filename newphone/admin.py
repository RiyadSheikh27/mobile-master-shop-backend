from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(PhoneBrand)
admin.site.register(PhoneModel)
admin.site.register(PhoneColor)
admin.site.register(ShopReview)
admin.site.register(Order)