from rest_framework import serializers
from .models import *
from decimal import Decimal


# ==================== BRAND SERIALIZERS ====================
class PhoneBrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewPhoneBrand
        fields = ['id', 'name', 'slug', 'icon', 'description', 'is_active', 'created_at']
        read_only_fields = ['is_active']


# ==================== COLOR SERIALIZERS ====================
class PhoneColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewPhoneColor
        fields = ['id', 'name', 'hex_code']


# ==================== STOCK MANAGEMENT SERIALIZERS ====================
class StockManagementSerializer(serializers.ModelSerializer):
    color_name = serializers.CharField(source='color.name', read_only=True)
    color_hex = serializers.CharField(source='color.hex_code', read_only=True)
    
    class Meta:
        model = StockManagement
        fields = [
            'id', 'phone_model', 'color', 'color_name', 'color_hex', 
            'stock', 'icon_color_based', 'is_in_stock', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['is_in_stock', 'created_at', 'updated_at']


class StockManagementWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockManagement
        fields = ['phone_model', 'color', 'stock', 'icon_color_based']


# ==================== PHONE MODEL SERIALIZERS ====================
class PhoneModelListSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    brand_slug = serializers.CharField(source='brand.slug', read_only=True)
    stock_management = StockManagementSerializer(many=True, read_only=True)
    total_stock = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = NewPhoneModel
        fields = [
            'id', 'name', 'slug', 'icon', 'stock_management',
            'brand', 'brand_name', 'brand_slug',
            'ram', 'memory', 'description_title', 'description',
            'main_amount', 'discounted_amount', 'final_price', 'discount_percentage',
            'stock_quantity', 'total_stock', 'rank', 'is_active',
            'is_in_stock', 'is_featured', 'created_at'
        ]


class PhoneModelDetailSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    brand_slug = serializers.CharField(source='brand.slug', read_only=True)
    stock_management = StockManagementSerializer(many=True, read_only=True)
    total_stock = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = NewPhoneModel
        fields = [
            'id', 'name', 'slug', 'icon', 'stock_management',
            'brand', 'brand_name', 'brand_slug',
            'ram', 'memory', 'description_title', 'description',
            'main_amount', 'discounted_amount', 'final_price', 'discount_percentage',
            'stock_quantity', 'total_stock', 'rank', 'is_active',
            'is_in_stock', 'is_featured', 'created_at', 'updated_at'
        ]


class PhoneModelCreateUpdateSerializer(serializers.ModelSerializer):
    stock_management = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of stock management entries with color, stock, and optional icon_color_based"
    )
    
    class Meta:
        model = NewPhoneModel
        fields = [
            'brand', 'name', 'icon', 'ram', 'memory',
            'main_amount', 'discounted_amount',
            'description_title', 'description',
            'stock_quantity', 'is_active', 'is_featured', 'rank',
            'stock_management'
        ]
        read_only_fields = ['is_active']
    
    def validate_stock_management(self, value):
        """Validate stock management data"""
        if not value:
            return value
        
        # Check for duplicate colors
        color_ids = [item.get('color') for item in value]
        if len(color_ids) != len(set(color_ids)):
            raise serializers.ValidationError("Duplicate colors found in stock management")
        
        # Validate each entry
        for item in value:
            if 'color' not in item:
                raise serializers.ValidationError("Each stock entry must have a 'color' field")
            if 'stock' not in item:
                raise serializers.ValidationError("Each stock entry must have a 'stock' field")
            
            # Validate color exists
            if not NewPhoneColor.objects.filter(id=item['color']).exists():
                raise serializers.ValidationError(f"Color with id {item['color']} does not exist")
            
            # Validate stock is non-negative
            try:
                stock_value = int(item['stock'])
                if stock_value < 0:
                    raise serializers.ValidationError("Stock cannot be negative")
            except (ValueError, TypeError):
                raise serializers.ValidationError("Stock must be a valid integer")
        
        return value
    
    def create(self, validated_data):
        """Create phone model with stock management entries"""
        stock_management_data = validated_data.pop('stock_management', [])
        
        # Create phone model
        phone_model = NewPhoneModel.objects.create(**validated_data)
        
        # Create stock management entries
        for stock_data in stock_management_data:
            color_id = stock_data.get('color')
            stock = stock_data.get('stock')
            icon_color_based = stock_data.get('icon_color_based', None)
            
            StockManagement.objects.create(
                phone_model=phone_model,
                color_id=color_id,
                stock=stock,
                icon_color_based=icon_color_based
            )
        
        return phone_model
    
    def update(self, instance, validated_data):
        """Update phone model and optionally update stock management"""
        stock_management_data = validated_data.pop('stock_management', None)
        
        # Update phone model fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update stock management if provided
        if stock_management_data is not None:
            # Delete existing stock management entries
            instance.stock_management.all().delete()
            
            # Create new stock management entries
            for stock_data in stock_management_data:
                color_id = stock_data.get('color')
                stock = stock_data.get('stock')
                icon_color_based = stock_data.get('icon_color_based', None)
                
                StockManagement.objects.create(
                    phone_model=instance,
                    color_id=color_id,
                    stock=stock,
                    icon_color_based=icon_color_based
                )
        
        return instance


# ==================== DISCOUNT SERIALIZERS ====================
class WebsiteDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteDiscount
        fields = ['id', 'percentage', 'amount', 'is_active', 'created_at']


# ==================== ORDER SERIALIZERS ====================
class NewPhoneOrderCreateSerializer(serializers.Serializer):
    """Serializer for creating orders"""
    phone_model_id = serializers.IntegerField()
    stock_management_id = serializers.IntegerField(help_text="ID of the stock management entry (phone + color)")
    quantity = serializers.IntegerField(default=1, min_value=1)
    
    # Customer info
    customer_name = serializers.CharField(max_length=200)
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField(max_length=20)
    
    # Shipping address
    shipping_address = serializers.CharField()
    city = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=100, default='Bangladesh')
    
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate order data"""
        # Validate phone model exists
        try:
            phone_model = NewPhoneModel.objects.get(id=data['phone_model_id'])
        except NewPhoneModel.DoesNotExist:
            raise serializers.ValidationError({'phone_model_id': 'Phone model not found'})
        
        # Validate stock management entry exists and belongs to the phone model
        try:
            stock_mgmt = StockManagement.objects.select_related('color', 'phone_model').get(
                id=data['stock_management_id']
            )
        except StockManagement.DoesNotExist:
            raise serializers.ValidationError({'stock_management_id': 'Stock management entry not found'})
        
        # Ensure stock management belongs to the specified phone model
        if stock_mgmt.phone_model_id != data['phone_model_id']:
            raise serializers.ValidationError({
                'stock_management_id': 'This color is not available for the selected phone model'
            })
        
        # Check if enough stock is available
        if stock_mgmt.stock < data['quantity']:
            raise serializers.ValidationError({
                'quantity': f'Only {stock_mgmt.stock} units available for {stock_mgmt.color.name if stock_mgmt.color else "this variant"}'
            })
        
        # Add validated objects to data
        data['phone_model'] = phone_model
        data['stock_management'] = stock_mgmt
        
        return data


class NewPhoneOrderSerializer(serializers.ModelSerializer):
    """Complete order serializer for reading"""
    phone_model_name = serializers.CharField(source='phone_model.name', read_only=True)
    phone_model_brand = serializers.CharField(source='phone_model.brand.name', read_only=True)
    phone_model_icon = serializers.ImageField(source='phone_model.icon', read_only=True)
    
    # Stock management details
    stock_management_id = serializers.IntegerField(source='stock_management.id', read_only=True)
    color_name = serializers.CharField(source='selected_color.name', read_only=True, allow_null=True)
    color_hex = serializers.CharField(source='selected_color.hex_code', read_only=True, allow_null=True)
    color_icon = serializers.ImageField(source='stock_management.icon_color_based', read_only=True, allow_null=True)
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    class Meta:
        model = NewPhoneOrder
        fields = [
            'id', 'order_number', 'user',
            'phone_model', 'phone_model_name', 'phone_model_brand', 'phone_model_icon',
            'stock_management_id', 'selected_color', 'color_name', 'color_hex', 'color_icon',
            'quantity', 'unit_price', 'subtotal',
            'website_discount_percentage', 'website_discount_amount', 'total_discount',
            'vat', 'total_amount',
            'customer_name', 'customer_email', 'customer_phone',
            'shipping_address', 'city', 'postal_code', 'country',
            'status', 'status_display', 'payment_status', 'payment_status_display',
            'stripe_payment_intent_id', 'stripe_charge_id',
            'notes', 'admin_notes', 'is_read',
            'created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at'
        ]


class NewPhoneOrderListSerializer(serializers.ModelSerializer):
    """Compact serializer for order lists"""
    phone_model_name = serializers.CharField(source='phone_model.name', read_only=True)
    phone_model_brand = serializers.CharField(source='phone_model.brand.name', read_only=True)
    color_name = serializers.CharField(source='selected_color.name', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    class Meta:
        model = NewPhoneOrder
        fields = [
            'id', 'order_number',
            'phone_model_name', 'phone_model_brand', 'color_name',
            'quantity', 'total_amount',
            'customer_name', 'customer_email',
            'status', 'status_display', 'payment_status', 'payment_status_display',
            'created_at'
        ]


class NewPhoneOrderUpdateSerializer(serializers.ModelSerializer):
    """Serializer for admin to update order status"""
    class Meta:
        model = NewPhoneOrder
        fields = [
            'status', 'payment_status', 'admin_notes', 'is_read',
            'confirmed_at', 'shipped_at', 'delivered_at'
        ]


class AdminOrderListSerializer(serializers.ModelSerializer):
    """Detailed serializer for admin order listing"""
    phone_model_name = serializers.CharField(source='phone_model.name', read_only=True)
    phone_model_brand = serializers.CharField(source='phone_model.brand.name', read_only=True)
    phone_model_icon = serializers.ImageField(source='phone_model.icon', read_only=True)
    color_name = serializers.CharField(source='selected_color.name', read_only=True, allow_null=True)
    color_hex = serializers.CharField(source='selected_color.hex_code', read_only=True, allow_null=True)
    color_icon = serializers.ImageField(source='stock_management.icon_color_based', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)
    
    class Meta:
        model = NewPhoneOrder
        fields = [
            'id', 'order_number', 'user', 'user_email',
            'phone_model', 'phone_model_name', 'phone_model_brand', 'phone_model_icon',
            'selected_color', 'color_name', 'color_hex', 'color_icon',
            'quantity', 'unit_price', 'subtotal',
            'website_discount_percentage', 'website_discount_amount', 'total_discount',
            'vat', 'total_amount',
            'customer_name', 'customer_email', 'customer_phone',
            'shipping_address', 'city', 'postal_code', 'country',
            'status', 'status_display', 'payment_status', 'payment_status_display',
            'stripe_payment_intent_id',
            'notes', 'admin_notes', 'is_read',
            'created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at'
        ]


class PriceCalculationSerializer(serializers.Serializer):
    """Serializer for price calculation endpoint"""
    phone_model_id = serializers.IntegerField()
    stock_management_id = serializers.IntegerField()
    quantity = serializers.IntegerField(default=1, min_value=1)


# ==================== REVIEW SERIALIZERS ====================
class PhoneReviewSerializer(serializers.ModelSerializer):
    phone_model_name = serializers.CharField(source='phone_model.name', read_only=True)
    phone_model_brand = serializers.CharField(source='phone_model.brand.name', read_only=True)
    
    class Meta:
        model = NewPhoneReview
        fields = [
            'id', 'order', 'phone_model', 'phone_model_name', 'phone_model_brand',
            'customer_name', 'customer_email', 'rating', 'review', 'created_at'
        ]
        read_only_fields = ['order', 'phone_model', 'customer_name', 'customer_email']


class PhoneReviewCreateSerializer(serializers.Serializer):
    """Serializer for creating reviews"""
    order_id = serializers.IntegerField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    review = serializers.CharField(required=False, allow_blank=True)
    
    def validate_order_id(self, value):
        """Validate order exists and is eligible for review"""
        try:
            order = NewPhoneOrder.objects.get(id=value)
        except NewPhoneOrder.DoesNotExist:
            raise serializers.ValidationError('Order not found')
        
        # Check if order is paid
        if order.payment_status != 'paid':
            raise serializers.ValidationError('Can only review paid orders')
        
        # Check if already reviewed
        if hasattr(order, 'review'):
            raise serializers.ValidationError('Order already reviewed')
        
        return value