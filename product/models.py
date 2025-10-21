from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid

User = get_user_model()


class PhoneBrand(models.Model):
    """Phone brand model (e.g., Apple, Samsung)"""
    name = models.CharField(max_length=100, unique=True)
    logo = models.ImageField(upload_to='brand_logos/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Phone Brand'
        verbose_name_plural = 'Phone Brands'

    def __str__(self):
        return self.name


class PhoneModel(models.Model):
    """Phone model (e.g., iPhone 15 Pro Max)"""
    brand = models.ForeignKey(PhoneBrand, on_delete=models.CASCADE, related_name='phone_models')
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='phone_images/', null=True, blank=True)
    release_year = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['brand', 'name']
        verbose_name = 'Phone Model'
        verbose_name_plural = 'Phone Models'

    def __str__(self):
        return f"{self.brand.name} {self.name}"


class PhoneProblem(models.Model):
    """Phone repair problems (e.g., Display Change, Battery Replacement)"""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class or name")
    estimated_time = models.PositiveIntegerField(
        help_text="Estimated repair time in minutes", 
        default=30
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Phone Problem'
        verbose_name_plural = 'Phone Problems'

    def __str__(self):
        return self.name


class RepairPrice(models.Model):
    """Pricing for specific phone model and problem combination"""
    PART_TYPE_CHOICES = [
        ('original', 'Original'),
        ('duplicate', 'Duplicate'),
    ]

    phone_model = models.ForeignKey(
        PhoneModel, 
        on_delete=models.CASCADE, 
        related_name='repair_prices'
    )
    problem = models.ForeignKey(
        PhoneProblem, 
        on_delete=models.CASCADE, 
        related_name='repair_prices'
    )
    part_type = models.CharField(max_length=20, choices=PART_TYPE_CHOICES)
    
    # Pricing
    base_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Discount in percentage (0-100)"
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Fixed discount amount"
    )
    
    # Stock management
    in_stock = models.BooleanField(default=True)
    warranty_days = models.PositiveIntegerField(
        default=90, 
        help_text="Warranty in days"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['phone_model', 'problem', 'part_type']
        unique_together = ['phone_model', 'problem', 'part_type']
        verbose_name = 'Repair Price'
        verbose_name_plural = 'Repair Prices'
        indexes = [
            models.Index(fields=['phone_model', 'problem']),
            models.Index(fields=['part_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.phone_model} - {self.problem.name} ({self.get_part_type_display()})"

    @property
    def final_price(self):
        """Calculate final price after discounts"""
        price = self.base_price
        if self.discount_percentage > 0:
            price -= (price * self.discount_percentage / Decimal('100'))
        price -= self.discount_amount
        return max(price, Decimal('0.00'))

    @property
    def total_discount(self):
        """Calculate total discount amount"""
        return self.base_price - self.final_price


class Order(models.Model):
    """Customer order for phone repair"""
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

    # Order identification
    order_number = models.CharField(max_length=50, unique=True, editable=False)
    
    # Customer information
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    
    # Phone information
    phone_model = models.ForeignKey(PhoneModel, on_delete=models.PROTECT, related_name='orders')
    
    # Pricing
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Sum of all repair item prices"
    )
    item_discount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total discount from individual items"
    )
    website_discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Website discount percentage on subtotal after item discounts"
    )
    website_discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Website fixed discount amount"
    )
    total_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Payment information (for Stripe integration)
    payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True)
    
    # Additional information
    notes = models.TextField(blank=True, help_text="Customer notes or special instructions")
    admin_notes = models.TextField(blank=True, help_text="Internal notes for staff")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
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
            order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
            if not Order.objects.filter(order_number=order_number).exists():
                return order_number

    def calculate_totals(self):
        """Calculate all totals for the order"""
        # Calculate subtotal and item discounts from order items
        items = self.order_items.all()
        self.subtotal = sum(item.base_price for item in items)
        self.item_discount = sum(item.item_discount for item in items)
        
        # Calculate price after item discounts
        price_after_items = self.subtotal - self.item_discount
        
        # Apply website percentage discount
        website_discount = Decimal('0.00')
        if self.website_discount_percentage > 0:
            website_discount = price_after_items * (self.website_discount_percentage / Decimal('100'))
        
        # Apply website fixed discount
        website_discount += self.website_discount_amount
        
        # Calculate final total
        self.total_amount = max(price_after_items - website_discount, Decimal('0.00'))
        
        return self.total_amount

    @property
    def total_discount(self):
        """Calculate total discount amount"""
        return self.subtotal - self.total_amount


class OrderItem(models.Model):
    """Individual repair item in an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    problem = models.ForeignKey(PhoneProblem, on_delete=models.PROTECT, related_name='order_items')
    part_type = models.CharField(
        max_length=20, 
        choices=RepairPrice.PART_TYPE_CHOICES,
        default='original'
    )
    base_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Original base price"
    )
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    final_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Price after discounts"
    )
    warranty_days = models.PositiveIntegerField(default=90)
    warranty_expires_at = models.DateField(null=True, blank=True)

    # Status
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Additional info
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        return f"{self.order.order_number} - {self.problem.name} ({self.get_part_type_display()})"

    @property
    def item_discount(self):
        """Calculate discount for this item"""
        return self.base_price - self.final_price

    def set_warranty_expiry(self):
        """Set warranty expiry date"""
        if self.order.confirmed_at:
            from datetime import timedelta
            self.warranty_expires_at = (self.order.confirmed_at + timedelta(days=self.warranty_days)).date()


class WebsiteDiscount(models.Model):
    """Fixed website discount applied automatically to all orders"""
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Fixed discount amount"
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Percentage discount applied to subtotal after item discounts"
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Website Discount"
        verbose_name_plural = "Website Discounts"

    def __str__(self):
        return f"Website Discount: {self.percentage}% + {self.amount} fixed"