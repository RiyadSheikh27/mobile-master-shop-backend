from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from accounts.permissions import IsAdmin, IsUser, IsOwnerOrReadOnly
from django.db import transaction
from django.db.models import Q
from decimal import Decimal
from .models import *
from .serializers import *
from accounts.permissions import IsAdmin
import stripe
from django.conf import settings
from django.utils import timezone
from accounts.mypaginations import MyLimitOffsetPagination

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


# ==================== PRODUCT VIEWSET ====================
class AcsProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrReadOnly]
    lookup_field = 'pk'

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AcsProductDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return AcsProductCreateUpdateSerializer
        return AcsProductListSerializer

    def get_queryset(self):
        queryset = AcsProduct.objects.filter(is_active=True).prefetch_related('reviews')
        
        in_stock = self.request.query_params.get('in_stock')
        if in_stock and in_stock.lower() == 'true':
            queryset = queryset.filter(stock_quantity__gt=0)
        
        featured = self.request.query_params.get('featured')
        if featured and featured.lower() == 'true':
            queryset = queryset.filter(is_featured=True)
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | 
                Q(subtitle__icontains=search)
            )
        
        return queryset.order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'message': 'Accessories retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'message': 'Accessory details retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'Accessory created successfully',
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
                'message': 'Accessory updated successfully',
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
            'message': 'Accessory deleted successfully',
            'data': None
        }, status=status.HTTP_200_OK)


# ==================== DISCOUNT VIEWSET ====================
class AcsWebsiteDiscountViewSet(viewsets.ModelViewSet):
    serializer_class = AcsWebsiteDiscountSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'get_active']:
            return [AllowAny()]
        return [AllowAny()]

    def get_queryset(self):
        return AcsWebsiteDiscount.objects.all().order_by('-created_at')

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
        discount = AcsWebsiteDiscount.objects.filter(is_active=True).first()
        
        if discount:
            serializer = self.get_serializer(discount)
            return Response({
                'success': True,
                'message': 'Discounts retrieved successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': True,
            'message': 'No active discount available',
            'data': None
        }, status=status.HTTP_200_OK)


# ==================== ORDER VIEWSET ====================
class AcsOrderViewSet(viewsets.ModelViewSet):
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsOwnerOrReadOnly()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return AcsOrderCreateSerializer
        elif self.action == 'list':
            return AcsOrderListSerializer
        elif self.action in ['update', 'partial_update']:
            return AcsOrderUpdateSerializer
        return AcsOrderSerializer

    def get_queryset(self):
        queryset = AcsOrder.objects.select_related('user', 'product')

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
        serializer = AcsOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Get product
        product = AcsProduct.objects.get(id=data['product_id'])
        quantity = data.get('quantity', 1)
        
        # Check stock
        if product.stock_quantity < quantity:
            return Response({
                'success': False,
                'message': f'Only {product.stock_quantity} units available'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get active discount
        active_discount = AcsWebsiteDiscount.objects.filter(is_active=True).first()
        website_discount_percentage = Decimal('0.00')
        website_discount_amount = Decimal('0.00')
        
        if active_discount:
            website_discount_percentage = active_discount.percentage
            website_discount_amount = active_discount.amount
        
        # Calculate shipping
        shipping_cost = Decimal('0.00')
        
        # Calculate prices
        unit_price = product.final_price
        subtotal = unit_price * quantity
        
        # Calculate discount
        discount = Decimal('0.00')
        if website_discount_percentage > 0:
            discount = subtotal * (website_discount_percentage / Decimal('100'))
        discount += website_discount_amount
        
        # Calculate total
        total_amount = subtotal - discount + shipping_cost
        total_amount = max(total_amount, Decimal('0.00'))
        
        # Create order
        order = AcsOrder.objects.create(
            user=request.user if request.user.is_authenticated else None,
            product=product,
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
            total_amount=total_amount,
            notes=data.get('notes', ''),
            status='pending',
            payment_status='pending'
        )
        
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(order.total_amount * 100),
                currency='usd',
                metadata={
                    'order_id': order.id,
                    'order_number': order.order_number,
                    'customer_email': order.customer_email
                },
                description=f"Order {order.order_number} - {product.title}"
            )
            
            order.stripe_payment_intent_id = payment_intent.id
            order.save()
            
            output_serializer = AcsOrderSerializer(order)
            
            return Response({
                'success': True,
                'message': 'Order created successfully',
                'data': {
                    'order': output_serializer.data,
                    'payment': {
                        'client_secret': payment_intent.client_secret,
                        'payment_intent_id': payment_intent.id,
                        'amount': str(order.total_amount),
                        'currency': 'USD'
                    }
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
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
            payment_intent = stripe.PaymentIntent.retrieve(
                payment_intent_id,
                expand=['latest_charge']
            )
            
            if payment_intent.status == 'succeeded':
                with transaction.atomic():
                    # Update order
                    order.payment_status = 'paid'
                    order.status = 'confirmed'
                    order.confirmed_at = timezone.now()
                    order.stripe_charge_id = payment_intent.latest_charge if hasattr(payment_intent, 'latest_charge') else None
                    order.save()
                    
                    # Reduce stock
                    product = order.product
                    product.stock_quantity -= order.quantity
                    product.save()
                
                serializer = AcsOrderSerializer(order)
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
                
        except Exception as e:
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
                except Exception as e:
                    return Response({
                        'success': False,
                        'message': f'Refund failed: {str(e)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Restore stock if order was confirmed
            if order.status == 'confirmed':
                product = order.product
                product.stock_quantity += order.quantity
                product.save()
            
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
        serializer = AcsPriceCalculationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        product = AcsProduct.objects.get(id=data['product_id'])
        quantity = data.get('quantity', 1)
        
        # Calculate subtotal
        unit_price = product.final_price
        subtotal = unit_price * quantity
        
        # Get active discount
        active_discount = AcsWebsiteDiscount.objects.filter(is_active=True).first()
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
        shipping_cost = Decimal('0.00')
        
        # Total
        total_amount = subtotal - discount + shipping_cost
        total_amount = max(total_amount, Decimal('0.00'))
        
        return Response({
            'success': True,
            'message': 'Price calculated successfully',
            'data': {
                'product': product.title,
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
class AcsReviewViewSet(viewsets.ModelViewSet):
    serializer_class = AcsReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    http_method_names = ['get', 'post', 'delete']  # Only allow GET, POST, DELETE

    def get_queryset(self):
        queryset = AcsReview.objects.select_related('product', 'order')
        
        # Filter by product (for admin to see all reviews of a product)
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        # Filter by user's own reviews
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
        create_serializer = AcsReviewCreateSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)
        
        # Get order
        order = AcsOrder.objects.get(id=create_serializer.validated_data['order_id'])
        
        # Create review
        review = AcsReview.objects.create(
            order=order,
            product=order.product,
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
        
        # Only allow deletion by order owner or admin
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
    

# ========== NEW VIEW FOR ADMIN ACCESSORY ORDER LIST ==========
from rest_framework.views import APIView
from django.db.models import Count, Sum, Avg, Q

class AdminAcsOrderListView(APIView):
    """
    API endpoint for admins to view all accessory orders with comprehensive details
    Requires authentication and admin role
    GET: Returns list of all accessory orders with filtering and statistics
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Check if user is admin
        if request.user.role != 'admin':
            return Response({
                'success': False,
                'message': 'Permission denied. Only admins can access all accessory orders.'
            }, status=status.HTTP_403_FORBIDDEN)

        # Get all orders with related data
        queryset = AcsOrder.objects.select_related('user', 'product')

        # ========== FILTERING OPTIONS ==========
        # Filter by status
        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by payment status
        payment_status_param = request.query_params.get('payment_status')
        if payment_status_param:
            queryset = queryset.filter(payment_status=payment_status_param)

        # Filter by customer email
        customer_email = request.query_params.get('customer_email')
        if customer_email:
            queryset = queryset.filter(customer_email__icontains=customer_email)

        # Filter by customer phone
        customer_phone = request.query_params.get('customer_phone')
        if customer_phone:
            queryset = queryset.filter(customer_phone__icontains=customer_phone)

        # Filter by order number
        order_number = request.query_params.get('order_number')
        if order_number:
            queryset = queryset.filter(order_number__icontains=order_number)

        # Filter by date range
        date_from = request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)

        # Filter by product
        product_id = request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        # Filter by city
        city = request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)

        # Filter by country
        country = request.query_params.get('country')
        if country:
            queryset = queryset.filter(country__icontains=country)
        # ========== END FILTERING OPTIONS ==========

        # Order by newest first
        queryset = queryset.order_by('-created_at')

        # ========== CALCULATE STATISTICS ==========
        total_orders = queryset.count()
        
        # Count by status
        status_counts = queryset.values('status').annotate(count=Count('id'))
        status_summary = {item['status']: item['count'] for item in status_counts}
        
        # Count by payment status
        payment_counts = queryset.values('payment_status').annotate(count=Count('id'))
        payment_summary = {item['payment_status']: item['count'] for item in payment_counts}
        
        # Calculate total revenue (only paid orders)
        total_revenue = queryset.filter(
            payment_status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        # Calculate pending revenue
        pending_revenue = queryset.filter(
            payment_status='pending'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        # Calculate average order value
        average_order_value = queryset.filter(
            payment_status='paid'
        ).aggregate(avg=Avg('total_amount'))['avg'] or Decimal('0.00')
        
        # Calculate total items sold (sum of quantities)
        total_items_sold = queryset.filter(
            payment_status='paid'
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # Most popular products
        top_products = queryset.filter(
            payment_status='paid'
        ).values(
            'product__title', 'product__id'
        ).annotate(
            total_quantity=Sum('quantity'),
            order_count=Count('id')
        ).order_by('-total_quantity')[:5]
        
        # Orders by city (top 5)
        top_cities = queryset.values('city').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        # ========== END STATISTICS ==========

        # Serialize order data
        # paginator = MyLimitOffsetPagination()
        # page = paginator.paginate_queryset(queryset, request)  # paginated queryset
        serializer = AdminAcsOrderListSerializer(queryset, many=True)

        return Response({
            'success': True,
            'message': 'Admin accessory order list retrieved successfully',
            'statistics': {
                'total_orders': total_orders,
                'status_summary': status_summary,
                'payment_summary': payment_summary,
                'total_revenue': str(total_revenue),
                'pending_revenue': str(pending_revenue),
                'average_order_value': str(round(average_order_value, 2)) if average_order_value and average_order_value > 0 else '0.00',
                'total_items_sold': total_items_sold,
                'top_products': list(top_products),
                'top_cities': list(top_cities)
            },
            'data': serializer.data
        }, status=status.HTTP_200_OK)
# ========== END NEW VIEW ==========