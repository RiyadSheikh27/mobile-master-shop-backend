from django.db import models
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone


User = get_user_model()

class NewPhoneBrand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    icon = models.ImageField(upload_to='new-phone-brand', null=True, blank=True)
    description = CKEditor5Field('Text', config_name='default')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name_plural = "Brands"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while NewPhoneBrand.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

class NewPhoneColor(models.Model):
    name = models.CharField(max_length=50, unique=True)
    hex_code = models.CharField(max_length=7, unique=True)

    def __str__(self):
        return self.name

class NewPhoneModel(models.Model):
    brand = models.ForeignKey(NewPhoneBrand, on_delete=models.CASCADE, related_name='phone_models')
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    icon = models.ImageField(upload_to='new-phone-model', null=True, blank=True)
    ram = models.CharField(max_length=20, null=True, blank=True)
    memory = models.CharField(max_length=25, null=True, blank=True)
    main_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discounted_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    description_title = CKEditor5Field('Text', config_name='default', null=True, blank=True)
    description = CKEditor5Field('Text', config_name='default', null=True, blank=True)
    color = models.ManyToManyField(NewPhoneColor, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    

    def __str__(self):
        return f"{self.brand.name} - {self.name}"
    
    @property
    def amount(self):
        if self.discounted_amount and self.discounted_amount < self.main_amount:
            return self.main_amount - self.discounted_amount
        return self.main_amount or Decimal("0.00")
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class NewPhoneOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    phone_model = models.ForeignKey(NewPhoneModel, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    notes = models.TextField(blank=True, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    website_discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    website_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    stripe_payment_intent = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Order {self.id} - {self.customer_name}"


class NewPhoneReview(models.Model):
    Customer_name = models.CharField(max_length=100)
    Customer_email = models.EmailField()
    review = models.TextField()
    rating = models.PositiveIntegerField()
    Phone_name_brand = models.CharField(max_length=100)
    phone_status = models.CharField(max_length=50)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Review by {self.Customer_name} for {self.Phone_name_brand}"
    

