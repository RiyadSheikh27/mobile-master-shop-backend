from django.shortcuts import render
from .models import *
from .serializers import *
from rest_framework import viewsets, permissions
from rest_framework.response import Response

# Create your views here.
class NewPhoneBrandViewSet(viewsets.ModelViewSet):
    queryset = PhoneBrand.objects.all()
    serializer_class = PhoneBrandSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return PhoneBrand.objects.filter(is_active=True).prefetch_related('phone_models')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "status":"success",
                "message":"Phone brands retrieved successfully",
                "data":{
                    serializer.data
                }
            }
        )

class PhoneColorViewSet(viewsets.ModelViewSet):
    queryset = PhoneColor.objects.all()
    serializer_class = PhoneColorSerializer
    permission_classes = [permissions.AllowAny]

class NewPhoneModelViewSet(viewsets.ModelViewSet):
    queryset = PhoneModel.objects.all()
    serializer_class = PhoneModelSerializer
    permission_classes = [permissions.AllowAny]