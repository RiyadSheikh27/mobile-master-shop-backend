from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from django.db import transaction
from django.db.models import Prefetch, Q
from decimal import Decimal
from .models import *
from .serializers import *


class PhoneBrandViewSet(viewsets.ModelViewSet):
    queryset = PhoneBrand.objects.all()
    serializer_class = PhoneBrandSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return PhoneBrand.objects.filter(is_active=True).prefetch_related('phone_models')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            "status": "success",
            "message": "Phone brands retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class PhoneModelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for phone models
    - List models (optionally filtered by brand)
    - Retrieve single model details
    """
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PhoneModelDetailSerializer
        return PhoneModelListSerializer

    def get_queryset(self):
        queryset = PhoneModel.objects.filter(is_active=True).select_related('brand')
        
        brand_id = self.request.query_params.get('brand', None)
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)
        return queryset
    
class DiscountViewSet(viewsets.ModelViewSet):
    """
    ViewSet for website discounts
    - List all active discounts
    """
    serializer_class = WebsiteDiscountSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return WebsiteDiscount.objects.filter(is_active=True)


class PhoneProblemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for phone problems/repair types
    - List all active problems
    """
    serializer_class = PhoneProblemSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return PhoneProblem.objects.filter(is_active=True)


class RepairPriceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for repair prices
    - List available repairs grouped by problem (GET)
    - Calculate total price for selected items (POST)
    """
    serializer_class = RepairPriceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return RepairPrice.objects.filter(is_active=True).select_related('phone_model', 'problem')

    def list(self, request, *args, **kwargs):
        """
        List repair prices grouped by problem
        Query params:
        - phone_model: id of the phone model (optional if brand provided)
        - brand: id of the brand (optional if phone_model provided)
        """
        phone_model_id = request.query_params.get('phone_model')
        brand_id = request.query_params.get('brand')

        queryset = self.get_queryset()

        if phone_model_id:
            queryset = queryset.filter(phone_model_id=phone_model_id)
        elif brand_id:
            queryset = queryset.filter(phone_model__brand_id=brand_id)

        if not queryset.exists():
            return Response(
                {"error": "No repair prices found for the given phone model or brand"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Group by problem
        problems_dict = {}
        for repair_price in queryset:
            problem_id = repair_price.problem.id
            if problem_id not in problems_dict:
                problems_dict[problem_id] = {
                    'problem_id': problem_id,
                    'problem_name': repair_price.problem.name,
                    'problem_icon': repair_price.problem.icon,
                    'problem_description': repair_price.problem.description,
                    'estimated_time': repair_price.problem.estimated_time,
                    'original': None,
                    'duplicate': None
                }
            problems_dict[problem_id][repair_price.part_type] = RepairPriceSerializer(repair_price).data

        return Response(list(problems_dict.values()), status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def calculate_price(self, request):
        """
        Calculate total price for selected repairs
        Body:
        {
            "phone_model_id": 1,
            "items": [
                {"problem_id": 1, "part_type": "original"},
                {"problem_id": 2, "part_type": "duplicate"}
            ],
            "website_discount_percentage": 5.00,
            "website_discount_amount": 0.00
        }
        """
        phone_model_id = request.data.get('phone_model_id')
        items_data = request.data.get('items', [])
        # website_discount_percentage = Decimal(str(request.data.get('website_discount_percentage', '0.00')))
        # website_discount_amount = Decimal(str(request.data.get('website_discount_amount', '0.00')))

        if not phone_model_id:
            return Response({"error": "phone_model_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not items_data:
            return Response({"error": "items list is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            phone_model = PhoneModel.objects.get(id=phone_model_id, is_active=True)
        except PhoneModel.DoesNotExist:
            return Response({"error": "Invalid or inactive phone model"}, status=status.HTTP_400_BAD_REQUEST)

        website_discount_obj = WebsiteDiscount.objects.filter(is_active=True).first()
        website_discount_percentage = website_discount_obj.percentage if website_discount_obj else Decimal('0.00')
        website_discount_amount = website_discount_obj.amount if website_discount_obj else Decimal('0.00')


        # Calculate pricing
        subtotal = Decimal('0.00')
        item_discount = Decimal('0.00')
        items_breakdown = []

        for item_data in items_data:
            problem_id = item_data.get('problem_id')
            part_type = item_data.get('part_type', 'original')

            try:
                repair_price = RepairPrice.objects.select_related('problem').get(
                    phone_model=phone_model,
                    problem_id=problem_id,
                    part_type=part_type,
                    is_active=True
                )
                base_price = repair_price.base_price
                final_price = repair_price.final_price
                discount = base_price - final_price

                subtotal += base_price
                item_discount += discount

                items_breakdown.append({
                    'problem_id': problem_id,
                    'problem_name': repair_price.problem.name,
                    'part_type': part_type,
                    'base_price': str(base_price),
                    'discount': str(discount),
                    'final_price': str(final_price),
                    'warranty_days': repair_price.warranty_days
                })

            except RepairPrice.DoesNotExist:
                return Response(
                    {"error": f"Invalid repair option for problem ID {problem_id} with part type {part_type}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Price after item discounts
        price_after_items = subtotal - item_discount

        # Apply website discount
        website_discount = (price_after_items * (website_discount_percentage / Decimal('100'))) + website_discount_amount

        # Final total
        total_amount = max(price_after_items - website_discount, Decimal('0.00'))
        total_discount = subtotal - total_amount

        return Response({
            'phone_model': phone_model.name,
            'brand': phone_model.brand.name,
            'subtotal': str(subtotal),
            'item_discount': str(item_discount),
            'price_after_item_discount': str(price_after_items),
            'website_discount_percentage': str(website_discount_percentage),
            'website_discount_amount': str(website_discount_amount),
            'website_discount': str(website_discount),
            'total_amount': str(total_amount),
            'total_discount': str(total_discount),
            'items': items_breakdown
        }, status=status.HTTP_200_OK)

class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for orders
    - Create new order
    - List orders (user's own orders if authenticated)
    - Retrieve order details
    - Update order status (admin only)
    """
    permission_classes = [AllowAny]  # Change to IsAuthenticatedOrReadOnly in production

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        elif self.action == 'list':
            return OrderListSerializer
        return OrderSerializer

    def get_queryset(self):
        queryset = Order.objects.select_related(
            'phone_model', 'phone_model__brand', 'user'
        ).prefetch_related(
            Prefetch('order_items', queryset=OrderItem.objects.select_related('problem'))
        )

        # Filter by user if authenticated
        if self.request.user.is_authenticated and not self.request.user.is_staff:
            queryset = queryset.filter(Q(user=self.request.user) | Q(customer_email=self.request.user.email))

        # Filter by status
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by payment status
        payment_status_param = self.request.query_params.get('payment_status', None)
        if payment_status_param:
            queryset = queryset.filter(payment_status=payment_status_param)

        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new order
        Body: {
            "phone_model_id": 1,
            "customer_name": "John Doe",
            "customer_email": "john@example.com",
            "customer_phone": "+1234567890",
            "items": [
                {"problem_id": 1, "part_type": "original"},
                {"problem_id": 2, "part_type": "duplicate"}
            ],
            "notes": "Please handle with care",
            "website_discount_percentage": 5.00,
            "website_discount_amount": 0.00
        }
        """
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        phone_model = PhoneModel.objects.get(id=data['phone_model_id'])

        # Create order
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            customer_name=data['customer_name'],
            customer_email=data['customer_email'],
            customer_phone=data['customer_phone'],
            phone_model=phone_model,
            subtotal=Decimal('0.00'),
            item_discount=Decimal('0.00'),
            website_discount_percentage=data.get('website_discount_percentage', Decimal('0.00')),
            website_discount_amount=data.get('website_discount_amount', Decimal('0.00')),
            total_amount=Decimal('0.00'),
            notes=data.get('notes', ''),
            status='pending',
            payment_status='pending'
        )

        # Create order items
        for item_data in data['items']:
            repair_price = RepairPrice.objects.select_related('problem').get(
                phone_model=phone_model,
                problem_id=item_data['problem_id'],
                part_type=item_data['part_type'],
                is_active=True
            )

            OrderItem.objects.create(
                order=order,
                problem=repair_price.problem,
                part_type=item_data['part_type'],
                base_price=repair_price.base_price,
                discount_percentage=repair_price.discount_percentage,
                discount_amount=repair_price.discount_amount,
                final_price=repair_price.final_price,
                warranty_days=repair_price.warranty_days
            )

        # Calculate totals
        order.calculate_totals()
        order.save()

        # Return order details
        output_serializer = OrderSerializer(order)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm an order (admin only in production)"""
        order = self.get_object()
        
        if order.status != 'pending':
            return Response(
                {"error": "Only pending orders can be confirmed"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.utils import timezone
        order.status = 'confirmed'
        order.confirmed_at = timezone.now()
        order.save()

        # Set warranty expiry for all items
        for item in order.order_items.all():
            item.set_warranty_expiry()
            item.save()

        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an order"""
        order = self.get_object()
        
        if order.status in ['completed', 'cancelled', 'refunded']:
            return Response(
                {"error": f"Cannot cancel order with status: {order.status}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = 'cancelled'
        order.save()

        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def track(self, request, pk=None):
        """Track order status"""
        order = self.get_object()
        serializer = self.get_serializer(order)
        return Response({"error": "phone_model parameter is required"},
                    status=status.HTTP_400_BAD_REQUEST
            )

        
        # Get all repair prices for the phone model
        repair_prices = self.get_queryset().filter(phone_model_id=phone_model_id)
        
        # Group by problem
        problems_dict = {}
        for repair_price in repair_prices:
            problem_id = repair_price.problem.id
            if problem_id not in problems_dict:
                problems_dict[problem_id] = {
                    'problem_id': problem_id,
                    'problem_name': repair_price.problem.name,
                    'problem_icon': repair_price.problem.icon,
                    'problem_description': repair_price.problem.description,
                    'estimated_time': repair_price.problem.estimated_time,
                    'original': None,
                    'duplicate': None
                }
            
            # Add price to appropriate part type
            serializer = RepairPriceSerializer(repair_price)
            problems_dict[problem_id][repair_price.part_type] = serializer.data
        
        # Convert to list
        grouped_data = list(problems_dict.values())
        
        return Response(grouped_data)

    @action(detail=False, methods=['post'])
    def calculate_price(self, request):
        """
        Calculate total price for selected repairs
        Body: {
            "phone_model_id": 1,
            "items": [
                {"problem_id": 1, "part_type": "original"},
                {"problem_id": 2, "part_type": "duplicate"}
            ],
            "website_discount_percentage": 5.00,
            "website_discount_amount": 0.00
        }
        """
        phone_model_id = request.data.get('phone_model_id')
        items_data = request.data.get('items', [])
        website_discount_percentage = Decimal(str(request.data.get('website_discount_percentage', '0.00')))
        website_discount_amount = Decimal(str(request.data.get('website_discount_amount', '0.00')))

        if not phone_model_id:
            return Response(
                {"error": "phone_model_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )