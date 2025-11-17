from django.db import models
from django.db.models import Max, Sum
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from django.db.models import F, Max

User = get_user_model()

class NewPhoneBrand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    icon = models.ImageField(upload_to='new-phone-brand/', null=True, blank=True)
    description = CKEditor5Field('Text', config_name='default', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "New Phone Brands"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while NewPhoneBrand.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class NewPhoneColor(models.Model):
    name = models.CharField(max_length=50, unique=True)
    hex_code = models.CharField(max_length=7, help_text="Color hex code (e.g., #FF5733)")

    class Meta:
        verbose_name_plural = "Phone Colors"
        ordering = ['name']

    def __str__(self):
        return self.name


class NewPhoneModel(models.Model):
    brand = models.ForeignKey(
        NewPhoneBrand, 
        on_delete=models.CASCADE, 
        related_name='phone_models'
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    icon = models.ImageField(upload_to='new-phone-model/', null=True, blank=True)
    
    ram = models.CharField(max_length=20, null=True, blank=True, help_text="e.g., 8GB")
    memory = models.CharField(max_length=25, null=True, blank=True, help_text="e.g., 128GB")
    
    main_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Original price"
    )
    discounted_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Discounted price (optional)"
    )
    
    # Description
    description_title = CKEditor5Field('Description Title', config_name='default', null=True, blank=True)
    description = CKEditor5Field('Description', config_name='default', null=True, blank=True)
    
    # DEPRECATED: This field will be removed in future - use StockManagement instead
    colors = models.ManyToManyField(NewPhoneColor, blank=True, related_name='phone_models')
    
    # DEPRECATED: Use StockManagement total stock instead
    stock_quantity = models.PositiveIntegerField(default=0, help_text="Available stock (deprecated - use StockManagement)")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Show on homepage")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    rank = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "New Phone Models"
        ordering = ['-rank', '-id']
        # unique_together = ['brand', 'name']

    def __str__(self):
        return f"{self.brand.name} {self.name}"
    
    @property
    def final_price(self):
        """Return the selling price (discounted if available, else main price)"""
        if self.discounted_amount and self.discounted_amount < self.main_amount:
            return self.discounted_amount
        return self.main_amount
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.discounted_amount and self.discounted_amount < self.main_amount:
            discount = ((self.main_amount - self.discounted_amount) / self.main_amount) * 100
            return round(discount, 2)
        return Decimal('0.00')
    
    @property
    def is_in_stock(self):
        """Check if phone is available - checks StockManagement"""
        total_stock = self.stock_management.aggregate(
            total=Sum('stock')
        )['total'] or 0
        return total_stock > 0
    
    @property
    def total_stock(self):
        """Get total stock across all colors from StockManagement"""
        return self.stock_management.aggregate(
            total=Sum('stock')
        )['total'] or 0
    
    def get_color_stock(self, color_id):
        """Get stock for a specific color"""
        try:
            stock_entry = self.stock_management.get(color_id=color_id)
            return stock_entry.stock
        except StockManagement.DoesNotExist:
            return 0
    
    def save(self, *args, **kwargs):
        if self.rank == 0:
            max_rank = NewPhoneModel.objects.filter(brand=self.brand).aggregate(Max('rank'))['rank__max'] or 0
            self.rank = max_rank + 1

        if self.pk:
            old_rank = NewPhoneModel.objects.get(pk=self.pk).rank

            if self.rank == old_rank:
                return super().save(*args, **kwargs)

            if self.rank < old_rank:
                NewPhoneModel.objects.filter(
                    brand=self.brand,
                    rank__gte=self.rank,
                    rank__lt=old_rank
                ).update(rank=F('rank') + 1)
            else:
                NewPhoneModel.objects.filter(
                    brand=self.brand,
                    rank__gt=old_rank,
                    rank__lte=self.rank
                ).update(rank=F('rank') - 1)

        if not self.slug:
            base_slug = slugify(f"{self.brand.name} {self.name}")
            slug = base_slug
            counter = 1
            while NewPhoneModel.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
    
        super().save(*args, **kwargs)


class StockManagement(models.Model):
    phone_model = models.ForeignKey(NewPhoneModel, on_delete=models.CASCADE, related_name='stock_management')
    color = models.ForeignKey(NewPhoneColor, on_delete=models.CASCADE, null=True, blank=True, related_name='stock_management')
    stock = models.PositiveIntegerField(default=0, help_text="Available stock", null=True, blank=True)
    icon_color_based = models.ImageField(upload_to='icon_color_based/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        unique_together = ['phone_model', 'color']
        verbose_name_plural = "Stock Management"
        ordering = ['phone_model', 'color']

    @property
    def is_in_stock(self):
        return (self.stock or 0) > 0
    
    def __str__(self):
        color_name = self.color.name if self.color else "No Color"
        return f"{self.phone_model.name} - {color_name} - Stock: {self.stock}"


class WebsiteDiscount(models.Model):
    """Fixed website discount applied automatically to all orders"""
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Percentage discount (0-100)"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Fixed discount amount"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Website Discount"
        verbose_name_plural = "Website Discounts"

    def __str__(self):
        return f"Discount: {self.percentage}% + ৳{self.amount}"


class NewPhoneOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    # Order identification
    order_number = models.CharField(max_length=50, unique=True, editable=False)
    
    # User & Phone
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='new_phone_orders'
    )
    phone_model = models.ForeignKey(
        NewPhoneModel, 
        on_delete=models.PROTECT,
        related_name='orders'
    )
    
    # CHANGED: Now references StockManagement instead of just color
    stock_management = models.ForeignKey(
        'StockManagement',
        on_delete=models.PROTECT,
        related_name='orders',
        help_text="Stock management entry (phone + color combination)"
    )
    
    # Keep for backward compatibility and display
    selected_color = models.ForeignKey(
        NewPhoneColor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Color chosen by customer"
    )
    
    quantity = models.PositiveIntegerField(default=1)
    
    # Customer Information
    customer_name = models.CharField(max_length=200, null=True, blank=True)
    customer_email = models.EmailField(null=True, blank=True)
    customer_phone = models.CharField(max_length=20, null=True, blank=True)
    
    # Shipping Address
    shipping_address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=100, default='Bangladesh', null=True, blank=True)
    
    # Pricing
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Price per unit at time of order"
    )
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Unit price × Quantity"
    )
    website_discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    website_discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    vat = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Final amount after discounts + shipping"
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Stripe Payment
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_charge_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Notes
    notes = models.TextField(blank=True, help_text="Customer notes")
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes")
    is_read = models.BooleanField(default=False, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "New Phone Orders"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['status', 'payment_status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"Order {self.order_number} - {self.customer_name}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_order_number():
        """Generate unique order number"""
        while True:
            order_number = f"NP-{uuid.uuid4().hex[:8].upper()}"
            if not NewPhoneOrder.objects.filter(order_number=order_number).exists():
                return order_number
    
    def calculate_total(self):
        """Calculate total amount with discounts and shipping"""
        # Subtotal
        self.subtotal = self.unit_price * self.quantity
        
        # Apply percentage discount
        discount = Decimal('0.00')
        if self.website_discount_percentage > 0:
            discount = self.subtotal * (self.website_discount_percentage / Decimal('100'))
        
        # Apply fixed discount
        discount += self.website_discount_amount
        
        # Calculate total
        self.total_amount = self.subtotal - discount + self.vat
        self.total_amount = max(self.total_amount, Decimal('0.00'))
        
        return self.total_amount
    
    @property
    def total_discount(self):
        """Calculate total discount applied"""
        discount = Decimal('0.00')
        if self.website_discount_percentage > 0:
            discount = self.subtotal * (self.website_discount_percentage / Decimal('100'))
        discount += self.website_discount_amount
        return discount


class NewPhoneReview(models.Model):
    """Review model - tied to order"""
    order = models.OneToOneField('NewPhoneOrder', on_delete=models.CASCADE, related_name='review', blank=True, null=True)
    phone_model = models.ForeignKey(NewPhoneModel, on_delete=models.CASCADE, related_name='reviews')
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer_name} - {self.phone_model.name} - {self.rating}★"