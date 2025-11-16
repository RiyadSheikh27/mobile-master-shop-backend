from django.db import models
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()

class AcsProduct(models.Model):
    """Accessories Product Model"""
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    picture = models.ImageField(upload_to='accessories/', null=True, blank=True)
    
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
    
    description_title = CKEditor5Field('Description Title', config_name='default', null=True, blank=True)
    description = CKEditor5Field('Description', config_name='default', null=True, blank=True)
    
    stock_quantity = models.PositiveIntegerField(default=0, help_text="Available stock")
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Show on homepage")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Accessories Products"
        ordering = ['-created_at']

    def __str__(self):
        return self.title
    
    @property
    def final_price(self):
        """Return the selling price (discounted if available, else main price)"""
        if self.discounted_amount and self.discounted_amount < self.main_amount:
            return self.main_amount - self.discounted_amount
        return self.main_amount
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.discounted_amount and self.discounted_amount < self.main_amount:
            discount = (100 - ((self.main_amount - self.discounted_amount) / self.main_amount) * 100)
            return round(discount, 2)
        return Decimal('0.00')
    
    @property
    def is_in_stock(self):
        """Check if product is available"""
        return self.stock_quantity > 0
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while AcsProduct.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class AcsWebsiteDiscount(models.Model):
    """Fixed website discount for accessories"""
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
        verbose_name = "Accessories Website Discount"
        verbose_name_plural = "Accessories Website Discounts"

    def __str__(self):
        return f"Accessories Discount: {self.percentage}% + ৳{self.amount}"


class AcsOrder(models.Model):
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
    
    # User & Product
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='acs_orders'
    )
    product = models.ForeignKey(
        AcsProduct, 
        on_delete=models.PROTECT,
        related_name='orders'
    )
    quantity = models.PositiveIntegerField(default=1)
    
    # Customer Information
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    
    # Shipping Address
    shipping_address = models.TextField()
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='Bangladesh')
    
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
        verbose_name_plural = "Accessories Orders"
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
            order_number = f"ACS-{uuid.uuid4().hex[:8].upper()}"
            if not AcsOrder.objects.filter(order_number=order_number).exists():
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

class AcsReview(models.Model):
    """Review model - tied to order"""
    order = models.OneToOneField('AcsOrder', on_delete=models.CASCADE, related_name='review', null=True, blank=True)
    product = models.ForeignKey(AcsProduct, on_delete=models.CASCADE, related_name='reviews')
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer_name} - {self.product.title} - {self.rating}★"