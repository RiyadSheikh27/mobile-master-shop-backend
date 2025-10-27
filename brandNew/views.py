from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db import transaction
from django.db.models import Q
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
class PhoneBrandViewSet(viewsets.ModelViewSet):
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

    def get_queryset(self):
        queryset = NewPhoneModel.objects.filter(is_active=True).select_related('brand').prefetch_related('colors', 'reviews')
        
        brand_slug = self.request.query_params.get('brand')
        if brand_slug:
            queryset = queryset.filter(brand__slug=brand_slug)
        
        in_stock = self.request.query_params.get('in_stock')
        if in_stock and in_stock.lower() == 'true':
            queryset = queryset.filter(stock_quantity__gt=0)
        
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
        return [IsAuthenticated()]

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
            'user', 'phone_model__brand', 'selected_color'
        ).prefetch_related('phone_model__colors')

        # Non-admin users see only their orders
        if self.request.user.is_authenticated and not hasattr(self.request.user, 'is_admin'):
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

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create order and initiate Stripe payment"""
        serializer = NewPhoneOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Get phone model
        phone_model = NewPhoneModel.objects.select_related('brand').get(
            id=data['phone_model_id']
        )
        
        # Get color if provided
        selected_color = None
        if data.get('color_id'):
            selected_color = NewPhoneColor.objects.get(id=data['color_id'])
        
        quantity = data.get('quantity', 1)
        
        # Check stock
        if phone_model.stock_quantity < quantity:
            return Response({
                'success': False,
                'message': f'Only {phone_model.stock_quantity} units available'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get active discount (from WebsiteDiscount model)
        active_discount = WebsiteDiscount.objects.filter(is_active=True).first()
        website_discount_percentage = Decimal('0.00')
        website_discount_amount = Decimal('0.00')
        
        if active_discount:
            website_discount_percentage = active_discount.percentage
            website_discount_amount = active_discount.amount
        
        # Calculate shipping (you can modify this logic)
        shipping_cost = Decimal('100.00')  # Flat rate
        
        # Calculate prices before creating order
        unit_price = phone_model.final_price
        subtotal = unit_price * quantity
        
        # Calculate discount
        discount = Decimal('0.00')
        if website_discount_percentage > 0:
            discount = subtotal * (website_discount_percentage / Decimal('100'))
        discount += website_discount_amount
        
        # Calculate total
        total_amount = subtotal - discount + shipping_cost
        total_amount = max(total_amount, Decimal('0.00'))
        
        # Create order with calculated total_amount
        order = NewPhoneOrder.objects.create(
            user=request.user if request.user.is_authenticated else None,
            phone_model=phone_model,
            selected_color=selected_color,
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
            shipping_cost=shipping_cost,
            total_amount=total_amount,  # Set total_amount here
            notes=data.get('notes', ''),
            status='pending',
            payment_status='pending'
        )
        
        # Create Stripe Payment Intent
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(order.total_amount * 100),  # Convert to cents
                currency='bdt',  # Bangladesh Taka
                metadata={
                    'order_id': order.id,
                    'order_number': order.order_number,
                    'customer_email': order.customer_email
                },
                description=f"Order {order.order_number} - {phone_model.name}"
            )
            
            order.stripe_payment_intent_id = payment_intent.id
            order.save()
            
            output_serializer = NewPhoneOrderSerializer(order)
            
            return Response({
                'success': True,
                'message': 'Order created successfully',
                'data': {
                    'order': output_serializer.data,
                    'payment': {
                        'client_secret': payment_intent.client_secret,
                        'payment_intent_id': payment_intent.id,
                        'amount': str(order.total_amount),
                        'currency': 'BDT'
                    }
                }
            }, status=status.HTTP_201_CREATED)
            
        except stripe.error.StripeError as e:
            # If Stripe fails, delete the order
            order.delete()
            return Response({
                'success': False,
                'message': f'Payment initialization failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def confirm_payment(self, request, pk=None):
        """Confirm payment after successful Stripe payment"""
        order = self.get_object()
        
        payment_intent_id = request.data.get('payment_intent_id')
        
        if not payment_intent_id or order.stripe_payment_intent_id != payment_intent_id:
            return Response({
                'success': False,
                'message': 'Invalid payment intent'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Verify payment with Stripe
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if payment_intent.status == 'succeeded':
                with transaction.atomic():
                    # Update order
                    order.payment_status = 'paid'
                    order.status = 'confirmed'
                    order.confirmed_at = timezone.now()
                    order.stripe_charge_id = payment_intent.charges.data[0].id if payment_intent.charges.data else None
                    order.save()
                    
                    # Reduce stock
                    phone_model = order.phone_model
                    phone_model.stock_quantity -= order.quantity
                    phone_model.save()
                
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
        """Cancel an order"""
        order = self.get_object()
        
        # Only allow cancellation of pending/confirmed orders
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
            
            # Restore stock if order was confirmed
            if order.status == 'confirmed':
                phone_model = order.phone_model
                phone_model.stock_quantity += order.quantity
                phone_model.save()
            
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
        phone_model = NewPhoneModel.objects.get(id=data['phone_model_id'])
        quantity = data.get('quantity', 1)
        
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
        
        # Shipping
        shipping_cost = Decimal('100.00')
        
        # Total
        total_amount = subtotal - discount + shipping_cost
        total_amount = max(total_amount, Decimal('0.00'))
        
        return Response({
            'success': True,
            'message': 'Price calculated successfully',
            'data': {
                'phone_model': phone_model.name,
                'brand': phone_model.brand.name,
                'unit_price': str(unit_price),
                'quantity': quantity,
                'subtotal': str(subtotal),
                'discount_percentage': str(website_discount_percentage),
                'discount_amount': str(website_discount_amount),
                'total_discount': str(discount),
                'shipping_cost': str(shipping_cost),
                'total_amount': str(total_amount)
            }
        }, status=status.HTTP_200_OK)


# ==================== REVIEW VIEWSET ====================
class PhoneReviewViewSet(viewsets.ModelViewSet):
    serializer_class = PhoneReviewSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = NewPhoneReview.objects.select_related('phone_model__brand')
        
        # Filter by phone model
        phone_id = self.request.query_params.get('phone_model')
        if phone_id:
            queryset = queryset.filter(phone_model_id=phone_id)
        
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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'success': True,
            'message': 'Review created successfully',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'success': True,
            'message': 'Review updated successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({
            'success': True,
            'message': 'Review deleted successfully'
        }, status=status.HTTP_200_OK)