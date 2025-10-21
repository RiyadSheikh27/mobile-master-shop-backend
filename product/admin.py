from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import *

admin.site.register(PhoneBrand)
admin.site.register(PhoneModel)
admin.site.register(PhoneProblem)
admin.site.register(RepairPrice)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(WebsiteDiscount)

