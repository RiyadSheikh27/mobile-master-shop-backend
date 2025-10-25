from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import *
from .serializers import *
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from accounts.permissions import IsUser, IsOwnerOrReadOnly, IsAdmin
from django.db.models import Q

class PhoneBrandViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing phone brands.
    """
    serializer_class = PhoneBrandSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return (
            NewPhoneBrand.objects.filter(is_active=True)
            .prefetch_related("phone_models")
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "status": "success",
                "message": "Phone brands retrieved successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

class PhoneColorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing phone colors.
    """
    queryset = NewPhoneColor.objects.all()
    serializer_class = PhoneColorSerializer
    permission_classes = [permissions.AllowAny]


class NewPhoneModelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing phone models.
    """
    queryset = (
        NewPhoneModel.objects.all()
        .select_related("brand")  
        .prefetch_related("color")
    )
    serializer_class = PhoneModelSerializer
    permission_classes = [permissions.AllowAny]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "status": "success",
                "message": "Phone models retrieved successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class PhoneListViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing phone brands along with their nested models.
    (Used for public display)
    """
    queryset = (
        NewPhoneBrand.objects.filter(is_active=True)
        .prefetch_related("phone_models__color")
    )
    serializer_class = PhoneBrandNestedSerializer
    permission_classes = [permissions.AllowAny]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "status": "success",
                "message": "Phone list with models retrieved successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

""" Order Section """
class NewPhoneOrderViewSet(viewsets.ModelViewSet):
    def get_queryset_class(self):
        if self.action == 'create':
            return NewPhoneOrderCreateSerializer
        elif self.action == 'list':
            return NewPhoneOrderSerializer
        elif self.action in ['update', 'partial_update']:
            return NewPhoneOrderUpdateSerializer
        else:
            return NewPhoneOrderSerializer
            
    def get_queryset(self):
        queryset = NewPhoneOrder.objects.all().select_related('user', 'phone_model__brand').prefetch_related('phone_model__color')

        if self.request.user.is_authenticated and not self.request.user.IsAdmin:
            queryset = queryset.filter(Q(user=self.request.user) | Q(customer_email = self.user.email))

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        payment_status_param = self.request.query_params.get('payment_status')
        if payment_status_param:
            queryset = queryset.filter(payment_status=payment_status_param)
        
        return queryset

    
        
    



