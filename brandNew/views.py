from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from django.db import transaction
from django.db.models import Q, Sum
from decimal import Decimal
from .models import *
from .serializers import *
from accounts.permissions import IsAdmin, IsUser, IsOwnerOrReadOnly
import stripe
from django.conf import settings
from django.utils import timezone

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


# ==================== BRAND VIEWSET ====================
class NewPhoneBrandViewSet(viewsets.ModelViewSet):
    serializer_class = PhoneBrandSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return NewPhoneBrand.objects.filter(is_active=True).prefetch_related('phone_models')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'message': 'Phone brands retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'message': 'Phone brand retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'Phone brand created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'Phone brand updated successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            'success': False,
            'message': 'Update failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({
            'success': True,
            'message': 'Phone brand deleted successfully',
            'data': None
        }, status=status.HTTP_200_OK)


# ==================== COLOR VIEWSET ====================
class PhoneColorViewSet(viewsets.ModelViewSet):
    queryset = NewPhoneColor.objects.all()
    serializer_class = PhoneColorSerializer
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'message': 'Colors retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


# ==================== STOCK MANAGEMENT VIEWSET ====================
class StockManagementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing stock by color for phone models
    """
    serializer_class = StockManagementSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = StockManagement.objects.select_related('phone_model', 'color').all()
        
        # Filter by phone model if provided
        phone_model_id = self.request.query_params.get('phone_model')
        if phone_model_id:
            queryset = queryset.filter(phone_model_id=phone_model_id)
        
        # Filter by color if provided
        color_id = self.request.query_params.get('color')
        if color_id:
            queryset = queryset.filter(color_id=color_id)
        
        # Filter by in_stock
        in_stock = self.request.query_params.get('in_stock')
        if in_stock and in_stock.lower() == 'true':
            queryset = queryset.filter(stock__gt=0)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return StockManagementWriteSerializer
        return StockManagementSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'message': 'Stock management retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'message': 'Stock details retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            phone_model_id = request.data.get('phone_model')
            color_id = request.data.get('color')
            
            if StockManagement.objects.filter(phone_model_id=phone_model_id, color_id=color_id).exists():
                return Response({
                    'success': False,
                    'message': 'Stock entry already exists for this phone model and color',
                    'errors': {'detail': 'Duplicate entry'}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer.save()
            return Response({
                'success': True,
                'message': 'Stock created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            read_serializer = StockManagementSerializer(instance)
            return Response({
                'success': True,
                'message': 'Stock updated successfully',
                'data': read_serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            'success': False,
            'message': 'Update failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({
            'success': True,
            'message': 'Stock deleted successfully',
            'data': None
        }, status=status.HTTP_200_OK)


# ==================== PHONE MODEL VIEWSET ====================
class NewPhoneModelViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    lookup_field = 'pk'

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PhoneModelDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return PhoneModelCreateUpdateSerializer
        return PhoneModelListSerializer
    
    def create(self, request, *args, **kwargs):
        """Create phone model with stock management in single request"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            phone_model = serializer.save()
            # Return full detail serializer with stock_management
            output_serializer = PhoneModelDetailSerializer(phone_model)
            return Response({
                'success': True,
                'message': 'Phone model created successfully with stock management',
                'data': output_serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        """Update phone model and optionally update stock management"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            phone_model = serializer.save()
            # Return full detail serializer with stock_management
            output_serializer = PhoneModelDetailSerializer(phone_model)
            return Response({
                'success': True,
                'message': 'Phone model updated successfully',
                'data': output_serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            'success': False,
            'message': 'Update failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def get_queryset(self):
        queryset = NewPhoneModel.objects.filter(is_active=True).select_related('brand').prefetch_related(
            'colors', 'reviews', 'stock_management', 'stock_management__color'
        )
        
        brand_slug = self.request.query_params.get('brand')
        if brand_slug:
            queryset = queryset.filter(brand__slug=brand_slug)
        
        in_stock = self.request.query_params.get('in_stock')
        if in_stock and in_stock.lower() == 'true':
            queryset = queryset.filter(stock_management__stock__gt=0).distinct()
        
        featured = self.request.query_params.get('featured')
        if featured and featured.lower() == 'true':
            queryset = queryset.filter(is_featured=True)
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(brand__name__icontains=search)
            )
        
        return queryset.order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'message': 'Phone models Listed successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'message': 'Phone details retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get', 'post'], url_path='stock')
    def manage_stock(self, request, pk=None):
        """
        GET: List all stock entries for this phone model
        POST: Create new stock entry for this phone model
        """
        phone_model = self.get_object()
        
        if request.method == 'GET':
            stocks = phone_model.stock_management.all()
            serializer = StockManagementSerializer(stocks, many=True)
            return Response({
                'success': True,
                'message': 'Stock entries retrieved successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        elif request.method == 'POST':
            data = request.data.copy()
            data['phone_model'] = phone_model.id
            
            serializer = StockManagementWriteSerializer(data=data)
            if serializer.is_valid():
                if StockManagement.objects.filter(
                    phone_model=phone_model, 
                    color_id=data.get('color')
                ).exists():
                    return Response({
                        'success': False,
                        'message': 'Stock for this color already exists',
                        'errors': {'detail': 'Duplicate entry'}
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                stock = serializer.save(phone_model=phone_model)
                read_serializer = StockManagementSerializer(stock)
                return Response({
                    'success': True,
                    'message': 'Stock created successfully',
                    'data': read_serializer.data
                }, status=status.HTTP_201_CREATED)
            
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)


# ==================== DISCOUNT VIEWSET ====================
class WebsiteDiscountViewSet(viewsets.ModelViewSet):
    serializer_class = WebsiteDiscountSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'get_active']:
            return [AllowAny()]
        return [AllowAny()]

    def get_queryset(self):
        return WebsiteDiscount.objects.all().order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'message': 'Discounts retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def get_active(self, request):
        """Get currently active discount"""
        discount = WebsiteDiscount.objects.filter(is_active=True).first()
        
        if discount:
            serializer = self.get_serializer(discount)
            return Response({
                'success': True,
                'message': 'Active discount retrieved',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': True,
            'message': 'No active discount available',
            'data': None
        }, status=status.HTTP_200_OK)


# ==================== ORDER VIEWSET ====================
class NewPhoneOrderViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.action == 'create':
            return NewPhoneOrderCreateSerializer
        elif self.action == 'list':
            return NewPhoneOrderListSerializer
        elif self.action in ['update', 'partial_update']:
            return NewPhoneOrderUpdateSerializer
        return NewPhoneOrderSerializer

    def get_queryset(self):
        queryset = NewPhoneOrder.objects.select_related(
            'user', 'phone_model__brand', 'selected_color', 'stock_management', 'stock_management__color'
        ).prefetch_related('phone_model__colors')

        if self.request.user.is_authenticated:
            if hasattr(self.request.user, 'role') and self.request.user.role == 'admin':
                pass
            else:
                queryset = queryset.filter(
                    Q(user=self.request.user) | 
                    Q(customer_email=self.request.user.email)
                )
        
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        payment_status_param = self.request.query_params.get('payment_status')
        if payment_status_param:
            queryset = queryset.filter(payment_status=payment_status_param)

        return queryset.order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'message': 'Orders retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'message': 'Order details retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        """Delete an order (Admin only)"""
        order = self.get_object()
        
        # Serialize order data before deletion
        serializer = self.get_serializer(order)
        order_data = serializer.data
        
        # Safety check: Don't delete paid orders without refund
        if order.payment_status == 'paid':
            return Response({
                'success': False,
                'message': 'Cannot delete paid order. Please cancel the order first to process refund.',
                'data': order_data
            }, status=status.HTTP_400_BAD_REQUEST)
        
        order_number = order.order_number
        order_id = order.id
        
        # Delete the order
        with transaction.atomic():
            order.delete()
        
        return Response({
            'success': True,
            'message': f'Order {order_number} deleted successfully',
            'data': {
                'deleted_order_id': order_id,
                'deleted_order_number': order_number,
                'order_details': order_data
            }
        }, status=status.HTTP_200_OK)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create order and initiate Stripe payment - using StockManagement"""
        serializer = NewPhoneOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Get validated objects from serializer
        phone_model = data['phone_model']
        stock_mgmt = data['stock_management']
        quantity = data.get('quantity', 1)
        
        # Get active discount
        active_discount = WebsiteDiscount.objects.filter(is_active=True).first()
        website_discount_percentage = Decimal('0.00')
        website_discount_amount = Decimal('0.00')
        
        if active_discount:
            website_discount_percentage = active_discount.percentage
            website_discount_amount = active_discount.amount
        
        # Calculate VAT
        vat = Decimal('00.20')
        
        # Calculate prices
        unit_price = phone_model.final_price
        subtotal = unit_price * quantity
        
        # Calculate discount
        discount = Decimal('0.00')
        if website_discount_percentage > 0:
            discount = subtotal * (website_discount_percentage / Decimal('100'))
        discount += website_discount_amount
        
        # Calculate total
        total_amount = subtotal - discount
        total_amount += total_amount * vat
        total_amount = max(total_amount, Decimal('0.00'))
        
        # Generate guest UUID for non-authenticated users
        guest_uuid = None
        if not request.user.is_authenticated:
            import uuid
            guest_uuid = str(uuid.uuid4())
        
        # Create order with stock_management reference
        order = NewPhoneOrder.objects.create(
            user=request.user if request.user.is_authenticated else None,
            phone_model=phone_model,
            stock_management=stock_mgmt,
            selected_color=stock_mgmt.color,  # Store color for easy access
            quantity=quantity,
            customer_name=data['customer_name'],
            customer_email=data['customer_email'],
            customer_phone=data['customer_phone'],
            shipping_address=data['shipping_address'],
            city=data['city'],
            postal_code=data['postal_code'],
            country=data.get('country', 'Bangladesh'),
            unit_price=unit_price,
            subtotal=subtotal,
            website_discount_percentage=website_discount_percentage,
            website_discount_amount=website_discount_amount,
            vat=vat,
            total_amount=total_amount,
            notes=data.get('notes', ''),
            status='pending',
            payment_status='pending'
        )
        
        # Create Stripe Payment Intent
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(order.total_amount * 100),
                currency='usd',
                payment_method_types=['card', 'klarna'],
                metadata={
                    'order_id': order.id,
                    'order_number': order.order_number,
                    'customer_email': order.customer_email,
                    'phone_model': phone_model.name,
                    'color': stock_mgmt.color.name if stock_mgmt.color else 'N/A',
                    'guest_uuid': guest_uuid if guest_uuid else 'authenticated_user'
                },
                description=f"Order {order.order_number} - {phone_model.name} ({stock_mgmt.color.name if stock_mgmt.color else 'No Color'})"
            )

            
            order.stripe_payment_intent_id = payment_intent.id
            order.save()
            
            output_serializer = NewPhoneOrderSerializer(order)
            
            response_data = {
                'order': output_serializer.data,
                'payment': {
                    'client_secret': payment_intent.client_secret,
                    'payment_intent_id': payment_intent.id,
                    'amount': str(order.total_amount),
                    'currency': 'USD'
                }
            }
            
            if guest_uuid:
                response_data['guest_uuid'] = guest_uuid
            
            return Response({
                'success': True,
                'message': 'Order created successfully',
                'data': response_data
            }, status=status.HTTP_201_CREATED)
            
        except stripe.error.StripeError as e:
            order.delete()
            return Response({
                'success': False,
                'message': f'Payment initialization failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def confirm_payment(self, request, pk=None):
        """Confirm payment after successful Stripe payment - reduces stock from StockManagement"""
        order = self.get_object()
        
        payment_intent_id = request.data.get('payment_intent_id')
        
        if not payment_intent_id or order.stripe_payment_intent_id != payment_intent_id:
            return Response({
                'success': False,
                'message': 'Invalid payment intent'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            payment_intent = stripe.PaymentIntent.retrieve(
                payment_intent_id,
                expand=['latest_charge']
            )
            
            if payment_intent.status == 'succeeded':
                with transaction.atomic():
                    order.payment_status = 'paid'
                    order.status = 'confirmed'
                    order.confirmed_at = timezone.now()
                    
                    # Get charge ID
                    if hasattr(payment_intent, 'latest_charge') and payment_intent.latest_charge:
                        if isinstance(payment_intent.latest_charge, str):
                            order.stripe_charge_id = payment_intent.latest_charge
                        else:
                            order.stripe_charge_id = payment_intent.latest_charge.id
                    
                    order.save()
                    
                    # CHANGED: Reduce stock from StockManagement instead of phone_model.stock_quantity
                    stock_mgmt = order.stock_management
                    stock_mgmt.stock -= order.quantity
                    stock_mgmt.save()
                
                serializer = NewPhoneOrderSerializer(order)
                return Response({
                    'success': True,
                    'message': 'Payment confirmed successfully',
                    'data': serializer.data
                }, status=status.HTTP_200_OK)
            else:
                order.payment_status = 'failed'
                order.save()
                return Response({
                    'success': False,
                    'message': f'Payment not completed. Status: {payment_intent.status}'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except stripe.error.StripeError as e:
            return Response({
                'success': False,
                'message': f'Payment verification failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        """Cancel an order - restores stock to StockManagement"""
        order = self.get_object()
        
        if order.status not in ['pending', 'confirmed']:
            return Response({
                'success': False,
                'message': f'Cannot cancel order with status: {order.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Refund if payment was made
            if order.payment_status == 'paid' and order.stripe_payment_intent_id:
                try:
                    refund = stripe.Refund.create(
                        payment_intent=order.stripe_payment_intent_id
                    )
                    order.payment_status = 'refunded'
                except stripe.error.StripeError as e:
                    return Response({
                        'success': False,
                        'message': f'Refund failed: {str(e)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # CHANGED: Restore stock to StockManagement instead of phone_model.stock_quantity
            if order.status == 'confirmed':
                stock_mgmt = order.stock_management
                stock_mgmt.stock += order.quantity
                stock_mgmt.save()
            
            order.status = 'cancelled'
            order.save()
        
        serializer = self.get_serializer(order)
        return Response({
            'success': True,
            'message': 'Order cancelled successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def calculate_price(self, request):
        """Calculate order price before creating order"""
        serializer = PriceCalculationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        try:
            phone_model = NewPhoneModel.objects.get(id=data['phone_model_id'])
        except NewPhoneModel.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Phone model not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate stock management
        try:
            stock_mgmt = StockManagement.objects.select_related('color').get(
                id=data['stock_management_id']
            )
        except StockManagement.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Stock management entry not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if stock_mgmt.phone_model_id != data['phone_model_id']:
            return Response({
                'success': False,
                'message': 'This color is not available for the selected phone model'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        quantity = data.get('quantity', 1)
        
        # Check stock availability
        if stock_mgmt.stock < quantity:
            return Response({
                'success': False,
                'message': f'Only {stock_mgmt.stock} units available'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate subtotal
        unit_price = phone_model.final_price
        subtotal = unit_price * quantity
        
        # Get active discount
        active_discount = WebsiteDiscount.objects.filter(is_active=True).first()
        website_discount_percentage = Decimal('0.00')
        website_discount_amount = Decimal('0.00')
        
        if active_discount:
            website_discount_percentage = active_discount.percentage
            website_discount_amount = active_discount.amount
        
        # Calculate discount
        discount = Decimal('0.00')
        if website_discount_percentage > 0:
            discount = subtotal * (website_discount_percentage / Decimal('100'))
        discount += website_discount_amount
        
        # VAT
        vat = Decimal('00.20')
        
        # Total
        total_amount = subtotal - discount
        total_amount += total_amount * vat
        total_amount = max(total_amount, Decimal('0.00'))
        
        return Response({
            'success': True,
            'message': 'Price calculated successfully',
            'data': {
                'phone_model': phone_model.name,
                'brand': phone_model.brand.name,
                'color': stock_mgmt.color.name if stock_mgmt.color else 'N/A',
                'color_hex': stock_mgmt.color.hex_code if stock_mgmt.color else None,
                'available_stock': stock_mgmt.stock,
                'unit_price': str(unit_price),
                'quantity': quantity,
                'subtotal': str(subtotal),
                'discount_percentage': str(website_discount_percentage),
                'discount_amount': str(website_discount_amount),
                'total_discount': str(discount),
                'vat': str(vat),
                'total_amount': str(total_amount)
            }
        }, status=status.HTTP_200_OK)


# ==================== REVIEW VIEWSET ====================
class PhoneReviewViewSet(viewsets.ModelViewSet):
    serializer_class = PhoneReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        queryset = NewPhoneReview.objects.select_related('phone_model__brand', 'order')
        
        phone_id = self.request.query_params.get('phone_model')
        if phone_id:
            queryset = queryset.filter(phone_model_id=phone_id)
        
        if self.request.user.is_authenticated and self.request.query_params.get('my_reviews'):
            queryset = queryset.filter(
                Q(order__user=self.request.user) | 
                Q(customer_email=self.request.user.email)
            )
        
        return queryset.order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'message': 'Reviews retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        """Create review - must be from a paid order"""
        create_serializer = PhoneReviewCreateSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)
        
        order = NewPhoneOrder.objects.get(id=create_serializer.validated_data['order_id'])
        
        review = NewPhoneReview.objects.create(
            order=order,
            phone_model=order.phone_model,
            customer_name=order.customer_name,
            customer_email=order.customer_email,
            rating=create_serializer.validated_data['rating'],
            review=create_serializer.validated_data.get('review', '')
        )
        
        serializer = self.get_serializer(review)
        return Response({
            'success': True,
            'message': 'Review created successfully',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        if request.user.is_authenticated:
            if request.user.role == 'admin' or instance.order.user == request.user or instance.customer_email == request.user.email:
                instance.delete()
                return Response({
                    'success': True,
                    'message': 'Review deleted successfully'
                }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'message': 'Permission denied'
        }, status=status.HTTP_403_FORBIDDEN)


# ========== ADMIN ORDER LIST VIEW ==========
from rest_framework.views import APIView
from django.db.models import Count, Sum, Q

class AdminOrderListView(APIView):
    """
    API endpoint for admins to view all orders with comprehensive details
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'admin':
            return Response({
                'success': False,
                'message': 'Permission denied. Only admins can access all orders.'
            }, status=status.HTTP_403_FORBIDDEN)

        queryset = NewPhoneOrder.objects.select_related(
            'user', 'phone_model__brand', 'selected_color', 'stock_management', 'stock_management__color'
        ).prefetch_related('phone_model__colors')

        # Filtering
        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        payment_status_param = request.query_params.get('payment_status')
        if payment_status_param:
            queryset = queryset.filter(payment_status=payment_status_param)

        customer_email = request.query_params.get('customer_email')
        if customer_email:
            queryset = queryset.filter(customer_email__icontains=customer_email)

        order_number = request.query_params.get('order_number')
        if order_number:
            queryset = queryset.filter(order_number__icontains=order_number)

        date_from = request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)

        brand = request.query_params.get('brand')
        if brand:
            queryset = queryset.filter(phone_model__brand__slug=brand)

        queryset = queryset.order_by('-created_at')

        # Statistics
        total_orders = queryset.count()
        
        status_counts = queryset.values('status').annotate(count=Count('id'))
        status_summary = {item['status']: item['count'] for item in status_counts}
        
        payment_counts = queryset.values('payment_status').annotate(count=Count('id'))
        payment_summary = {item['payment_status']: item['count'] for item in payment_counts}
        
        total_revenue = queryset.filter(
            payment_status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        pending_revenue = queryset.filter(
            payment_status='pending'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

        serializer = AdminOrderListSerializer(queryset, many=True)

        return Response({
            'success': True,
            'message': 'Admin order list retrieved successfully',
            'statistics': {
                'total_orders': total_orders,
                'status_summary': status_summary,
                'payment_summary': payment_summary,
                'total_revenue': str(total_revenue),
                'pending_revenue': str(pending_revenue)
            },
            'data': serializer.data
        }, status=status.HTTP_200_OK)