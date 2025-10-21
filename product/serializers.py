from rest_framework import serializers
from .models import *
from decimal import Decimal


class PhoneBrandSerializer(serializers.ModelSerializer):
    """Serializer for phone brands"""
    class Meta:
        model = PhoneBrand
        fields = ['id', 'name', 'logo', 'is_active', 'created_at']
        read_only_fields = ['is_active']

class PhoneModelListSerializer(serializers.ModelSerializer):
    """Serializer for phone model list"""
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    
    
    class Meta:
        model = PhoneModel
        fields = ['id', 'name', 'brand', 'brand_name', 'image', 'is_active']
        read_only_fields = ['is_active']



class PhoneModelDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for phone model with available repairs"""
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    brand_logo = serializers.ImageField(source='brand.logo', read_only=True)
    available_repairs_count = serializers.SerializerMethodField()
    
    class Meta:
        model = PhoneModel
        fields = ['id', 'name', 'brand', 'brand_name', 'brand_logo', 'image', 
                  'is_active', 'available_repairs_count']
    
    def get_available_repairs_count(self, obj):
        return obj.repair_prices.filter(is_active=True).values('problem').distinct().count()


class PhoneProblemSerializer(serializers.ModelSerializer):
    """Serializer for phone problems"""
    
    class Meta:
        model = PhoneProblem
        fields = ['id', 'name', 'description', 'icon', 'estimated_time']


class RepairPriceSerializer(serializers.ModelSerializer):
    """Serializer for repair prices with calculated fields"""
    problem_name = serializers.CharField(source='problem.name', read_only=True)
    problem_icon = serializers.CharField(source='problem.icon', read_only=True)
    problem_description = serializers.CharField(source='problem.description', read_only=True)
    estimated_time = serializers.IntegerField(source='problem.estimated_time', read_only=True)
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = RepairPrice
        fields = [
            'id', 'phone_model', 'problem', 'problem_name', 'problem_icon', 'problem_description',
            'part_type', 'base_price', 'discount_percentage', 'discount_amount',
            'final_price', 'total_discount', 'in_stock', 'warranty_days',
            'estimated_time', 'is_active'
        ]
        read_only_fields = ['is_active', 'in_stock']


class RepairPriceGroupedSerializer(serializers.Serializer):
    """Grouped repair prices by problem with both original and duplicate options"""
    problem_id = serializers.IntegerField()
    problem_name = serializers.CharField()
    problem_icon = serializers.CharField()
    problem_description = serializers.CharField()
    estimated_time = serializers.IntegerField()
    original = RepairPriceSerializer(allow_null=True)
    duplicate = RepairPriceSerializer(allow_null=True)


class OrderItemCreateSerializer(serializers.Serializer):
    """Serializer for creating order items"""
    problem_id = serializers.IntegerField()
    part_type = serializers.ChoiceField(choices=RepairPrice.PART_TYPE_CHOICES, default='original')


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order items"""
    problem_name = serializers.CharField(source='problem.name', read_only=True)
    problem_icon = serializers.CharField(source='problem.icon', read_only=True)
    item_discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'problem', 'problem_name', 'problem_icon', 'part_type',
            'base_price', 'discount_percentage', 'discount_amount', 'final_price',
            'item_discount', 'warranty_days', 'warranty_expires_at', 'notes'
        ]
        read_only_fields = ['warranty_expires_at']


class OrderCreateSerializer(serializers.Serializer):
    """Serializer for creating orders"""
    phone_model_id = serializers.IntegerField()
    customer_name = serializers.CharField(max_length=200)
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField(max_length=20)
    items = OrderItemCreateSerializer(many=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    website_discount_percentage = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        min_value=Decimal('0.00'),
        max_value=Decimal('100.00')
    )
    website_discount_amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        min_value=Decimal('0.00')
    )

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one repair item is required")
        return value

    def validate(self, data):
        # Validate phone model exists
        phone_model_id = data.get('phone_model_id')
        try:
            phone_model = PhoneModel.objects.get(id=phone_model_id, is_active=True)
        except PhoneModel.DoesNotExist:
            raise serializers.ValidationError({"phone_model_id": "Invalid or inactive phone model"})

        # Validate repair prices exist for all items
        for item in data.get('items', []):
            try:
                repair_price = RepairPrice.objects.get(
                    phone_model=phone_model,
                    problem_id=item['problem_id'],
                    part_type=item['part_type'],
                    is_active=True
                )
                if not repair_price.in_stock:
                    raise serializers.ValidationError({
                        "items": f"Part not in stock for {repair_price.problem.name} ({item['part_type']})"
                    })
            except RepairPrice.DoesNotExist:
                raise serializers.ValidationError({
                    "items": f"Invalid repair option for problem ID {item['problem_id']} with part type {item['part_type']}"
                })

        return data


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for orders"""
    order_items = OrderItemSerializer(many=True, read_only=True)
    phone_model_name = serializers.CharField(source='phone_model.__str__', read_only=True)
    brand_name = serializers.CharField(source='phone_model.brand.name', read_only=True)
    total_discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user', 'customer_name', 'customer_email', 
            'customer_phone', 'phone_model', 'phone_model_name', 'brand_name',
            'subtotal', 'item_discount', 'website_discount_percentage', 
            'website_discount_amount', 'total_amount', 'total_discount',
            'status', 'status_display', 'payment_status', 'payment_status_display',
            'notes', 'admin_notes', 'order_items', 'created_at', 'updated_at',
            'confirmed_at', 'completed_at'
        ]
        read_only_fields = [
            'order_number', 'subtotal', 'item_discount', 'total_amount',
            'created_at', 'updated_at', 'confirmed_at', 'completed_at'
        ]


class OrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for order list"""
    phone_model_name = serializers.CharField(source='phone_model.__str__', read_only=True)
    brand_name = serializers.CharField(source='phone_model.brand.name', read_only=True)
    items_count = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'customer_name', 'customer_phone',
            'phone_model_name', 'brand_name', 'total_amount', 'status',
            'status_display', 'payment_status', 'payment_status_display',
            'items_count', 'created_at'
        ]
    
    def get_items_count(self, obj):
        return obj.order_items.count()


class PriceCalculationSerializer(serializers.Serializer):
    """Serializer for price calculation preview"""
    items = OrderItemCreateSerializer(many=True)
    website_discount_percentage = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        required=False
    )
    website_discount_amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        required=False
    )

class WebsiteDiscountSerializer(serializers.ModelSerializer):
    """Serializer for website discounts"""
    class Meta:
        model = WebsiteDiscount
        fields = ['id', 'percentage', 'amount', 'is_active', 'created_at']
        read_only_fields = ['is_active', 'created_at']