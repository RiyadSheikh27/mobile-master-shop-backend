from rest_framework import serializers
from .models import *
from decimal import Decimal


# ==================== COLOR SERIALIZERS ====================
class PhoneColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewPhoneColor
        fields = ['id', 'name', 'hex_code']


# ==================== BRAND SERIALIZERS ====================
class PhoneBrandSerializer(serializers.ModelSerializer):
    models_count = serializers.SerializerMethodField()
    
    class Meta:
        model = NewPhoneBrand
        fields = ['id', 'name', 'slug', 'icon', 'description', 'is_active', 'models_count', 'created_at']
        read_only_fields = ['slug', 'created_at', 'is_active']
    
    def get_models_count(self, obj):
        return obj.phone_models.filter(is_active=True).count()


# ==================== PHONE MODEL SERIALIZERS ====================
class PhoneModelListSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    brand_slug = serializers.CharField(source='brand.slug', read_only=True)
    color = PhoneColorSerializer(many=True, read_only=True)
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = NewPhoneModel
        fields = [
            'id', 'name', 'slug', 'icon',
            'brand', 'brand_name', 'brand_slug',
            'ram', 'memory',
            'main_amount', 'discounted_amount', 'final_price', 'discount_percentage',
            'color', 'stock_quantity', 'is_in_stock', 'is_featured',
            'created_at', 'colors',
        ]
        ref_name = 'BrandNewPhoneModelList'


class PhoneModelDetailSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    brand_slug = serializers.CharField(source='brand.slug', read_only=True)
    brand_icon = serializers.ImageField(source='brand.icon', read_only=True)
    colors = PhoneColorSerializer(many=True, read_only=True)
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    average_rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    
    class Meta:
        model = NewPhoneModel
        fields = [
            'id', 'name', 'slug', 'icon',
            'brand', 'brand_name', 'brand_slug', 'brand_icon',
            'ram', 'memory',
            'main_amount', 'discounted_amount', 'final_price', 'discount_percentage',
            'description_title', 'description',
            'colors', 'stock_quantity', 'is_in_stock', 'is_featured',
            'average_rating', 'reviews_count',
            'created_at', 'updated_at'
        ]
        ref_name = 'BrandNewPhoneModelDetail'
    
    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if reviews.exists():
            return round(sum(r.rating for r in reviews) / reviews.count(), 1)
        return 0.0
    
    def get_reviews_count(self, obj):
        return obj.reviews.count()


class PhoneModelCreateUpdateSerializer(serializers.ModelSerializer):
    brand = serializers.SlugRelatedField(
        queryset=NewPhoneBrand.objects.filter(is_active=True),
        slug_field='slug'
    )
    color_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=NewPhoneColor.objects.all(),
        write_only=True,
        required=False
    )
    class Meta:
        model = NewPhoneModel
        fields = [
            'name', 'brand', 'icon',
            'ram', 'memory',
            'main_amount', 'discounted_amount',
            'description_title', 'description',
            'color_ids', 'stock_quantity', 'is_featured'
        ]
    
    def create(self, validated_data):
        color_ids = validated_data.pop('color_ids', [])
        phone_model = NewPhoneModel.objects.create(**validated_data)
        if color_ids:
            phone_model.colors.set(color_ids)
        return phone_model
    
    def update(self, instance, validated_data):
        color_ids = validated_data.pop('color_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if color_ids is not None:
            instance.colors.set(color_ids)
        
        return instance


# ==================== DISCOUNT SERIALIZERS ====================
class WebsiteDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteDiscount
        fields = ['id', 'percentage', 'amount', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'is_active']
        ref_name = 'BrandNewWebsiteDiscountSerializer'


# ==================== ORDER SERIALIZERS ====================
class NewPhoneOrderCreateSerializer(serializers.Serializer):
    phone_model_id = serializers.IntegerField()
    color_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, default=1)
    
    customer_name = serializers.CharField(max_length=200)
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField(max_length=20)
    
    shipping_address = serializers.CharField()
    city = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=100, default='Bangladesh')
    
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_phone_model_id(self, value):
        try:
            phone = NewPhoneModel.objects.get(id=value, is_active=True)
            if not phone.is_in_stock:
                raise serializers.ValidationError("This phone is out of stock")
        except NewPhoneModel.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive phone model")
        return value
    
    def validate(self, data):
        # Check stock availability
        try:
            phone = NewPhoneModel.objects.get(id=data['phone_model_id'])
            quantity = data.get('quantity', 1)
            
            if phone.stock_quantity < quantity:
                raise serializers.ValidationError({
                    'quantity': f'Only {phone.stock_quantity} units available in stock'
                })
            
            # Validate color if provided
            color_id = data.get('color_id')
            if color_id:
                if not phone.colors.filter(id=color_id).exists():
                    raise serializers.ValidationError({
                        'color_id': 'Selected color is not available for this phone'
                    })
        except NewPhoneModel.DoesNotExist:
            raise serializers.ValidationError({'phone_model_id': 'Phone not found'})
        
        return data


class NewPhoneOrderSerializer(serializers.ModelSerializer):
    phone_model_name = serializers.CharField(source='phone_model.name', read_only=True)
    phone_model_brand = serializers.CharField(source='phone_model.brand.name', read_only=True)
    phone_model_image = serializers.ImageField(source='phone_model.icon', read_only=True)
    phone_ram = serializers.CharField(source='phone_model.ram', read_only=True)
    phone_memory = serializers.CharField(source='phone_model.memory', read_only=True)
    
    color_name = serializers.CharField(source='selected_color.name', read_only=True)
    color_hex = serializers.CharField(source='selected_color.hex_code', read_only=True)
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    total_discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = NewPhoneOrder
        fields = [
            'id', 'order_number',
            'user', 'phone_model', 'phone_model_name', 'phone_model_brand', 'phone_model_image',
            'phone_ram', 'phone_memory',
            'selected_color', 'color_name', 'color_hex', 'quantity',
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


class NewPhoneOrderListSerializer(serializers.ModelSerializer):
    phone_model_name = serializers.CharField(source='phone_model.name', read_only=True)
    phone_model_brand = serializers.CharField(source='phone_model.brand.name', read_only=True)
    phone_image = serializers.ImageField(source='phone_model.icon', read_only=True)
    color_name = serializers.CharField(source='selected_color.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    class Meta:
        model = NewPhoneOrder
        fields = [
            'id', 'order_number',
            'customer_name', 'customer_phone',
            'phone_model_name', 'phone_model_brand', 'phone_image',
            'color_name', 'quantity',
            'total_amount',
            'status', 'status_display',
            'payment_status', 'payment_status_display',
            'created_at'
        ]


class NewPhoneOrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewPhoneOrder
        fields = ['status', 'admin_notes']


# ==================== REVIEW SERIALIZERS ====================
class PhoneReviewSerializer(serializers.ModelSerializer):
    phone_name = serializers.CharField(source='phone_model.name', read_only=True)
    phone_brand = serializers.CharField(source='phone_model.brand.name', read_only=True)
    
    class Meta:
        model = NewPhoneReview
        fields = [
            'id', 'phone_model', 'phone_name', 'phone_brand',
            'customer_name', 'customer_email',
            'rating', 'review',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


# ==================== PRICE CALCULATION SERIALIZER ====================
class PriceCalculationSerializer(serializers.Serializer):
    phone_model_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    
    def validate_phone_model_id(self, value):
        if not NewPhoneModel.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid phone model")
        return value