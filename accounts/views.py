"""
Accounts Views
===============
Registration and profile management endpoints.
"""
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from drf_spectacular.utils import extend_schema

from .serializers import UserRegistrationSerializer, UserDetailSerializer, ClientProfileSerializer
from .models import ClientProfile

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """
    POST /api/v1/auth/register/
    Create a new client account. No authentication required.
    """
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary='Register a new client', tags=['Authentication'])
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {'detail': 'Account created successfully. Please log in.'},
            status=status.HTTP_201_CREATED
        )


class MeView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/v1/auth/me/  — Return authenticated user + profile
    PATCH /api/v1/auth/me/ — Update first/last name
    """
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary='Get current user profile', tags=['Authentication'])
    def get_object(self):
        # select_related('profile') avoids a second query for the nested profile
        return User.objects.select_related('profile').get(pk=self.request.user.pk)


class ProfileUpdateView(generics.UpdateAPIView):
    """
    PATCH /api/v1/auth/profile/ — Update the client's extended profile (address, phone etc.)
    """
    serializer_class = ClientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary='Update client profile', tags=['Authentication'])
    def get_object(self):
        # get_or_create is safer than get() in case profile was not auto-created
        profile, _ = ClientProfile.objects.get_or_create(user=self.request.user)
        return profile
