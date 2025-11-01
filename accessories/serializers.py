from rest_framework import serializers
from .models import *
from decimal import Decimal


# ==================== PRODUCT SERIALIZERS ====================
class AcsProductListSerializer(serializers.ModelSerializer):
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = AcsProduct
        fields = [
            'id', 'title', 'subtitle', 'slug', 'picture',
            'main_amount', 'discounted_amount', 'final_price', 'discount_percentage',
            'stock_quantity', 'description_title', 'description', 'is_in_stock', 'is_featured',
            'created_at'
        ]


class AcsProductDetailSerializer(serializers.ModelSerializer):
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    average_rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AcsProduct
        fields = [
            'id', 'title', 'subtitle', 'slug', 'picture',
            'main_amount', 'discounted_amount', 'final_price', 'discount_percentage',
            'description_title', 'description',
            'stock_quantity', 'is_in_stock', 'is_featured',
            'average_rating', 'reviews_count',
            'created_at', 'updated_at'
        ]
    
    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if reviews.exists():
            return round(sum(r.rating for r in reviews) / reviews.count(), 1)
        return 0.0
    
    def get_reviews_count(self, obj):
        return obj.reviews.count()


class AcsProductCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcsProduct
        fields = [
            'title', 'subtitle', 'picture',
            'main_amount', 'discounted_amount',
            'description_title', 'description',
            'stock_quantity', 'is_featured'
        ]


# ==================== DISCOUNT SERIALIZERS ====================
class AcsWebsiteDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcsWebsiteDiscount
        fields = ['id', 'percentage', 'amount', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'is_active']


# ==================== ORDER SERIALIZERS ====================
class AcsOrderCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    
    customer_name = serializers.CharField(max_length=200)
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField(max_length=20)
    
    shipping_address = serializers.CharField()
    city = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=100, default='Bangladesh')
    
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_product_id(self, value):
        try:
            product = AcsProduct.objects.get(id=value, is_active=True)
            if not product.is_in_stock:
                raise serializers.ValidationError("This product is out of stock")
        except AcsProduct.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive product")
        return value
    
    def validate(self, data):
        # Check stock availability
        try:
            product = AcsProduct.objects.get(id=data['product_id'])
            quantity = data.get('quantity', 1)
            
            if product.stock_quantity < quantity:
                raise serializers.ValidationError({
                    'quantity': f'Only {product.stock_quantity} units available in stock'
                })
        except AcsProduct.DoesNotExist:
            raise serializers.ValidationError({'product_id': 'Product not found'})
        
        return data


class AcsOrderSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source='product.title', read_only=True)
    product_subtitle = serializers.CharField(source='product.subtitle', read_only=True)
    product_image = serializers.ImageField(source='product.picture', read_only=True)
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    total_discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = AcsOrder
        fields = [
            'id', 'order_number',
            'user', 'product', 'product_title', 'product_subtitle', 'product_image',
            'quantity',
            'customer_name', 'customer_email', 'customer_phone',
            'shipping_address', 'city', 'postal_code', 'country',
            'unit_price', 'subtotal',
            'website_discount_percentage', 'website_discount_amount',
            'shipping_cost', 'total_amount', 'total_discount',
            'status', 'status_display',
            'payment_status', 'payment_status_display',
            'stripe_payment_intent_id',
            'notes', 'admin_notes',
            'created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at'
        ]
        read_only_fields = [
            'order_number', 'unit_price', 'subtotal', 'total_amount',
            'stripe_payment_intent_id', 'status', 'payment_status',
            'created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at'
        ]


class AcsOrderListSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source='product.title', read_only=True)
    product_image = serializers.ImageField(source='product.picture', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    class Meta:
        model = AcsOrder
        fields = [
            'id', 'order_number',
            'customer_name', 'customer_phone',
            'product_title', 'product_image',
            'quantity', 'total_amount',
            'status', 'status_display',
            'payment_status', 'payment_status_display',
            'created_at'
        ]


class AcsOrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcsOrder
        fields = ['status', 'admin_notes']


# ==================== REVIEW SERIALIZERS ====================
class AcsReviewSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source='product.title', read_only=True)
    
    class Meta:
        model = AcsReview
        fields = [
            'id', 'product', 'product_title',
            'customer_name', 'customer_email',
            'rating', 'review',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


# ==================== PRICE CALCULATION SERIALIZER ====================
class AcsPriceCalculationSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    
    def validate_product_id(self, value):
        if not AcsProduct.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid product")
        return value
    
# ========== NEW SERIALIZER FOR ADMIN ACCESSORY ORDER LIST ==========
class AdminAcsOrderListSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for admin accessory order list view
    Shows all order details including customer info, product details, and payment info
    """
    # Product details
    product_title = serializers.CharField(source='product.title', read_only=True)
    product_subtitle = serializers.CharField(source='product.subtitle', read_only=True)
    product_image = serializers.ImageField(source='product.picture', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    
    # User details (if order is linked to a user account)
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
    
    # Status displays
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    # Calculated fields
    total_discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = AcsOrder
        fields = [
            # Order identification
            'id', 'order_number',
            
            # User account info (if exists)
            'user', 'user_email', 'user_username',
            
            # Customer details
            'customer_name', 'customer_email', 'customer_phone',
            
            # Shipping address
            'shipping_address', 'city', 'postal_code', 'country',
            
            # Product details
            'product', 'product_title', 'product_subtitle', 'product_image', 'product_slug',
            
            # Quantity
            'quantity',
            
            # Pricing details
            'unit_price', 'subtotal',
            'website_discount_percentage', 'website_discount_amount', 'total_discount',
            'shipping_cost', 'total_amount',
            
            # Order status
            'status', 'status_display',
            'payment_status', 'payment_status_display',
            
            # Notes
            'notes', 'admin_notes',
            
            # Timestamps
            'created_at', 'updated_at',
        ]
        read_only_fields = fields
# ========== END NEW SERIALIZER ==========