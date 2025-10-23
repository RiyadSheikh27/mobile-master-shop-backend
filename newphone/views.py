from django.shortcuts import render
from .models import *
from .serializers import *
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework import status

# Create your views here.
class PhoneBrandViewSet(viewsets.ModelViewSet):
        pass
    # serializer_class = PhoneBrandSerializer

    # def get_queryset(self):
    #     # Make sure is_active is a boolean field
    #     return PhoneBrand.objects.filter(is_active=True).prefetch_related("phone_models")

    # def list(self, request, *args, **kwargs):
    #     queryset = self.get_queryset()
    #     serializer = self.get_serializer(queryset, many=True)

    #     return Response(
    #         {
    #             "status": "success",
    #             "message": "Phone brands retrieved successfully",
    #             "data": serializer.data,
    #         },
    #         status=status.HTTP_200_OK,
        # )

class PhoneColorViewSet(viewsets.ModelViewSet):
    queryset = PhoneColor.objects.all()
    serializer_class = PhoneColorSerializer
    permission_classes = [permissions.AllowAny]

class NewPhoneModelViewSet(viewsets.ModelViewSet):
    queryset = PhoneModel.objects.all()
    serializer_class = PhoneModelSerializer
    permission_classes = [permissions.AllowAny]