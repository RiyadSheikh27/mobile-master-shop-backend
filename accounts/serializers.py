from rest_framework import serializers
from .models import User
import re
from django.contrib.auth.password_validation import validate_password

class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

class SetCredentialsSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        """
        Username rules:
        - Minimum 6 characters
        - Only lowercase letters, numbers, _, @
        - No spaces
        """
        if len(value) < 6:
            raise serializers.ValidationError("Username must be at least 6 characters long.")

        if not re.match(r'^[a-z0-9_@.]+$', value):
            raise serializers.ValidationError(
                "Username can contain only lowercase letters, numbers, '_', '.' and '@'. No spaces allowed."
            )

        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken.")

        return value

    def validate_password(self, value):
        """
        Password rules:
        - Minimum 8 characters
        - Can include a-z, A-Z, 0-9, special characters
        """
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        validate_password(value)  # Django's built-in password validators
        return value

class LoginSerializer(serializers.Serializer):
    email_or_username = serializers.CharField()
    password = serializers.CharField(write_only=True)

class OAuthRegisterSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    provider = serializers.ChoiceField(choices=['google', 'apple'])

class OAuthLoginSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    provider = serializers.ChoiceField(choices=['google', 'apple'])
