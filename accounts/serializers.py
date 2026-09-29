"""
Accounts Serializers
=====================
Handle registration, profile reads/updates, and JWT token responses.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import ClientProfile

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Validates and creates a new client user + their profile.
    Password is write-only and validated against Django's AUTH_PASSWORD_VALIDATORS.
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'password', 'password_confirm']

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        # create_user handles password hashing via set_password()
        user = User.objects.create_user(**validated_data)
        # Auto-create blank profile for the new client
        ClientProfile.objects.create(user=user)
        return user


class ClientProfileSerializer(serializers.ModelSerializer):
    """Read/Update the extended client profile."""

    class Meta:
        model = ClientProfile
        fields = [
            'company_name', 'phone', 'address_line1', 'address_line2',
            'city', 'state', 'country', 'postal_code', 'credit_balance', 'currency',
        ]
        read_only_fields = ['credit_balance', 'currency']  # Changed via billing only


class UserDetailSerializer(serializers.ModelSerializer):
    """Full user + nested profile for the authenticated user's dashboard."""
    profile = ClientProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'date_joined', 'profile']
        read_only_fields = ['id', 'email', 'role', 'date_joined']
