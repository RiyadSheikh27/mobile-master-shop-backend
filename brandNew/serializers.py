from rest_framework import serializers
from .models import *
from decimal import Decimal

# ---------- Color Serializer ----------
class PhoneColorSerializer(serializers.ModelSerializer):
    """Serializer for phone colors"""
    class Meta:
        model = NewPhoneColor
        fields = ['id', 'name', 'hex_code']


# ---------- Model Serializer ----------
class PhoneModelSerializer(serializers.ModelSerializer):
    """Serializer for phone models"""
    # Use brand slug for easy writing, but brand details are nested under 'brand_detail'
    brand = serializers.SlugRelatedField(
        queryset=NewPhoneBrand.objects.all(),
        slug_field='slug'
    )

    # brand name (read-only)
    brand_name = serializers.CharField(source='brand.name', read_only=True)

    # nested color serializer
    colors = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=NewPhoneColor.objects.all(),
        write_only=True,
    )
    color_details = PhoneColorSerializer(source='color', many=True, read_only=True)
    
    class Meta:
        model = NewPhoneModel
        fields = [
            'id', 'name', 'slug', 'icon',
            'brand', 'brand_name', 'colors',
            'ram', 'memory', 'main_amount', 'discounted_amount',
            'description_title', 'description',
            'is_active', 'created_at', 'color_details'
        ]
        read_only_fields = ['id', 'slug', 'is_active', 'created_at']

    def create(self, validated_data):
        colors_data = validated_data.pop('colors', [])
        phone_model = NewPhoneModel.objects.create(**validated_data)
        phone_model.color.set(colors_data)
        return phone_model
    
    def update(self, instance, validated_data):
        colors_data = validated_data.pop('colors', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if colors_data is not None:
            instance.color.set(colors_data)



# ---------- Brand Serializer ----------
class PhoneBrandSerializer(serializers.ModelSerializer):
    """Basic serializer for phone brands"""
    class Meta:
        model = NewPhoneBrand
        fields = ['id', 'name', 'slug', 'icon', 'description', 'is_active', 'created_at']
        read_only_fields = ['id', 'slug', 'is_active', 'created_at']


# ---------- Nested Brand Serializer (with Models) ----------
class PhoneBrandNestedSerializer(serializers.ModelSerializer):
    """Nested serializer showing all models under each brand"""
    models = PhoneModelSerializer(many=True, read_only=True, source='phone_models')

    class Meta:
        model = NewPhoneBrand
        fields = ['id', 'name', 'slug', 'icon', 'description', 'models']
        read_only_fields = ['id', 'slug']

#---------- New Phone Order Section ----------
class NewPhoneOrderCreateSerializer(serializers.Serializer):
    """Serializer for creating new phone orders"""
    phone_model_id = serializers.IntegerField()
    customer_name = serializers.CharField(max_length=200)
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField(max_length=20)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_phone_model_id(self, value):
        """Validate that phone model exists and is active"""
        try:
            phone_model = NewPhoneModel.objects.get(id=value, is_active=True)
            if not phone_model.amount or phone_model.amount <= 0:
                raise serializers.ValidationError("This phone model is not available for purchase")
        except NewPhoneModel.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive phone model")
        return value
    
class NewPhoneOrderSerializer(serializers.ModelSerializer):
    """Detailed serializer for phone orders"""
    phone_model_name = serializers.CharField(source='phone_model.name', read_only=True)
    phone_model_brand = serializers.CharField(source='phone_model.brand.name', read_only=True)
    phone_model_image = serializers.ImageField(source='phone_model.icon', read_only=True)
    phone_ram = serializers.CharField(source='phone_model.ram', read_only=True)
    phone_memory = serializers.CharField(source='phone_model.memory', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    final_amount = serializers.SerializerMethodField()
    discount_applied = serializers.SerializerMethodField()

    class Meta:
        model = NewPhoneOrder
        fields = [
            'id', 'user', 'phone_model', 'phone_model_name', 'phone_model_brand',
            'phone_model_image', 'phone_ram', 'phone_memory',
            'customer_name', 'customer_email', 'customer_phone',
            'total_amount', 'website_discount_percentage', 'website_discount_amount',
            'final_amount', 'discount_applied',
            'status', 'status_display', 'payment_status', 'payment_status_display',
            'stripe_payment_intent', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'total_amount', 'final_amount', 'discount_applied',
            'status', 'payment_status', 'stripe_payment_intent',
            'created_at', 'updated_at'
        ]

    def get_final_amount(self, obj):
        """Calculate final amount after discounts"""
        amount = obj.total_amount
        
        if obj.website_discount_percentage > 0:
            amount -= (amount * obj.website_discount_percentage / Decimal('100'))
        
        amount -= obj.website_discount_amount
        
        return max(amount, Decimal('0.00'))
    
    def get_discount_applied(self, obj):
        """Calculate total discount applied"""
        return obj.total_amount - self.get_final_amount(obj)
    
class NewPhoneOrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for order list"""
    phone_model_name = serializers.CharField(source='phone_model.name', read_only=True)
    phone_model_brand = serializers.CharField(source='phone_model.brand.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    final_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = NewPhoneOrder
        fields = [
            'id', 'customer_name', 'customer_phone',
            'phone_model_name', 'phone_model_brand',
            'total_amount', 'final_amount',
            'status', 'status_display',
            'payment_status', 'payment_status_display',
            'created_at'
        ]
    
    def get_final_amount(self, obj):
        """Calculate final amount after discounts"""
        amount = obj.total_amount
        
        if obj.website_discount_percentage > 0:
            amount -= (amount * obj.website_discount_percentage / Decimal('100'))
        
        amount -= obj.website_discount_amount
        
        return max(amount, Decimal('0.00'))


class NewPhoneOrderUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating order status (admin only)"""
    
    class Meta:
        model = NewPhoneOrder
        fields = ['status', 'payment_status', 'notes']