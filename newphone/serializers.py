from .models import *
from rest_framework import serializers
from decimal import Decimal

class PhoneBrandSerializer(serializers.ModelSerializer):
    """Serializer for phone brands"""
    class Meta:
        model = PhoneBrand
        fields = ['id', 'name', 'slug', 'icon', 'description', 'is_active', 'created_at']
        read_only_fields = ['is_active', 'slug', 'created_at']

class PhoneColorSerializer(serializers.ModelSerializer):
    """Serializer for phone colors"""
    class Meta:
        model = PhoneColor
        fields = ['id', 'name', 'hex_code']

class PhoneModelSerializer(serializers.ModelSerializer):
    """Serializer for phone modelo"""
    brand = serializers.SlugRelatedField(
        queryset=PhoneBrand.objects.all(),
        slug_field='slug'
    )
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    color_serializer = PhoneColorSerializer(source='color', many=True, read_only=True)
    class Meta:
        model = PhoneModel
        fields = ['id', 'name', 'slug', 'icon', 'brand', 'color_serializer', 'ram', 'memory', 'main_amount', 'discounted_amount', 
                  'description_title', 'description', 'is_active', 'created_at']
        read_only_fields = ['is_active', 'slug', 'created_at']
                  
