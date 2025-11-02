from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from accounts.permissions import IsAdmin, IsUser, IsOwnerOrReadOnly
from django.db import transaction
from django.db.models import Prefetch, Q
from decimal import Decimal
from .models import *
from .serializers import *
import stripe
from django.conf import settings
from django.utils import timezone

stripe.api_key = settings.STRIPE_SECRET_KEY


class PhoneBrandViewSet(viewsets.ModelViewSet): 
    queryset = PhoneBrand.objects.all()
    serializer_class = PhoneBrandSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return PhoneBrand.objects.filter(is_active=True).prefetch_related(
            "phone_models"
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        return Response(
            {
                "status": "success",
                "message": "Phone brands Listed successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class PhoneModelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for phone models
    - List models (optionally filtered by brand)
    - Retrieve single model details
    """
    
    permission_classes = [IsOwnerOrReadOnly]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PhoneModelDetailSerializer
        return PhoneModelListSerializer

    def get_queryset(self):
        queryset = PhoneModel.objects.filter(is_active=True).select_related("brand")

        brand_slug = self.request.query_params.get("brand", None)
        if brand_slug:
            queryset = queryset.filter(brand__slug=brand_slug)

        return queryset


class DiscountViewSet(viewsets.ModelViewSet):
    """
    ViewSet for website discounts
    - List all active discounts
    """

    serializer_class = WebsiteDiscountSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        return WebsiteDiscount.objects.filter(is_active=True)
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'message': 'Discounts retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class PhoneProblemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for phone problems/repair types
    - CRUD operations for active problems
    """

    serializer_class = PhoneProblemSerializer
    permission_classes = [IsOwnerOrReadOnly]
    queryset = PhoneProblem.objects.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        response.data = {
            "success": True,
            "message": "Phone problem created successfully.",
            "data": response.data,
        }
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        response.data = {
            "success": True,
            "message": "Phone problem updated successfully.",
            "data": response.data,
        }
        return response

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return Response(
            {"success": True, "message": "Phone problem deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = {
            "success": True,
            "message": "Active phone problems fetched successfully.",
            "data": response.data,
        }
        return response


class RepairPriceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for repair prices
    - List available repairs grouped by problem (GET)
    - Calculate total price for selected items (POST)
    """

    serializer_class = RepairPriceSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return RepairPrice.objects.filter(is_active=True).select_related(
            "phone_model", "problem"
        )

    def list(self, request, *args, **kwargs):
        """
        List repair prices grouped by problem
        Query params:
        - phone_model: id of the phone model (optional if brand provided)
        - brand: id of the brand (optional if phone_model provided)
        """
        phone_model_id = request.query_params.get("phone_model")
        brand_id = request.query_params.get("brand")

        queryset = self.get_queryset()

        if phone_model_id:
            queryset = queryset.filter(phone_model_id=phone_model_id)
        elif brand_id:
            queryset = queryset.filter(phone_model__brand_id=brand_id)

        if not queryset.exists():
            return Response(
                {
                    "success": True,
                    "status": "empty data",
                    "message": "No repair prices found for the given phone model or brand",
                    "data": [],
                },
                status=status.HTTP_200_OK,
            )

        # Group by problem
        problems_dict = {}
        for repair_price in queryset:
            problem_id = repair_price.problem.id
            if problem_id not in problems_dict:
                problems_dict[problem_id] = {
                    "problem_id": problem_id,
                    "problem_name": repair_price.problem.name,
                    "problem_icon": repair_price.problem.icon,
                    "problem_description": repair_price.problem.description,
                    "estimated_time": repair_price.problem.estimated_time,
                    "original": None,
                    "duplicate": None,
                }
            problems_dict[problem_id][repair_price.part_type] = RepairPriceSerializer(
                repair_price
            ).data

        return Response(
            {
                "success": True,
                "message": "Data fetched successfully.",
                "data": list(problems_dict.values()),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
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
        phone_model_id = request.data.get("phone_model_id")
        items_data = request.data.get("items", [])
        # website_discount_percentage = Decimal(str(request.data.get('website_discount_percentage', '0.00')))
        # website_discount_amount = Decimal(str(request.data.get('website_discount_amount', '0.00')))

        if not phone_model_id:
            return Response(
                {"error": "phone_model_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not items_data:
            return Response(
                {"error": "items list is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            phone_model = PhoneModel.objects.get(id=phone_model_id, is_active=True)
        except PhoneModel.DoesNotExist:
            return Response(
                {"error": "Invalid or inactive phone model"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        website_discount_obj = WebsiteDiscount.objects.filter(is_active=True).first()
        website_discount_percentage = (
            website_discount_obj.percentage if website_discount_obj else Decimal("0.00")
        )
        website_discount_amount = (
            website_discount_obj.amount if website_discount_obj else Decimal("0.00")
        )

        # Calculate pricing
        subtotal = Decimal("0.00")
        item_discount = Decimal("0.00")
        items_breakdown = []

        for item_data in items_data:
            problem_id = item_data.get("problem_id")
            part_type = item_data.get("part_type", "original")

            try:
                repair_price = RepairPrice.objects.select_related("problem").get(
                    phone_model=phone_model,
                    problem_id=problem_id,
                    part_type=part_type,
                    is_active=True,
                )
                base_price = repair_price.base_price
                final_price = repair_price.final_price
                discount = base_price - final_price

                subtotal += base_price
                item_discount += discount

                items_breakdown.append(
                    {
                        "problem_id": problem_id,
                        "problem_name": repair_price.problem.name,
                        "part_type": part_type,
                        "base_price": str(base_price),
                        "discount": str(discount),
                        "final_price": str(final_price),
                        "warranty_days": repair_price.warranty_days,
                    }
                )

            except RepairPrice.DoesNotExist:
                return Response(
                    {
                        "success": False,
                        "message": f"Invalid repair option for problem ID {problem_id} with part type {part_type}",
                        "data": [],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Price after item discounts
        price_after_items = subtotal - item_discount

        # Apply website discount
        website_discount = (
            price_after_items * (website_discount_percentage / Decimal("100"))
        ) + website_discount_amount

        # Final total
        total_amount = max(price_after_items - website_discount, Decimal("0.00"))
        total_discount = subtotal - total_amount

        return Response(
            {
                "success": True,
                "message": "Repair price calculated successfully.",
                "data": {
                    "phone_model": phone_model.name,
                    "brand": phone_model.brand.name,
                    "subtotal": str(subtotal),
                    "item_discount": str(item_discount),
                    "price_after_item_discount": str(price_after_items),
                    "website_discount_percentage": str(website_discount_percentage),
                    "website_discount_amount": str(website_discount_amount),
                    "website_discount": str(website_discount),
                    "total_amount": str(total_amount),
                    "total_discount": str(total_discount),
                    "items": items_breakdown,
                },
            },
            status=status.HTTP_200_OK,
        )  

    @action(detail=False, methods=['patch'])
    def update_field(self, request):
        """
        Update a single field of a RepairPrice
        Body: {
            "phone_model_id": 1,
            "problem_id": 1,
            "part_type": "original",
            "field": "base_price",
            "value": "5000.00"
        }
        """
        phone_model_id = request.data.get("phone_model_id")
        problem_id = request.data.get("problem_id")
        part_type = request.data.get("part_type")
        field = request.data.get("field")
        value = request.data.get("value")
    
        if not all([phone_model_id, problem_id, part_type, field]):
            return Response(
                {"success": False, "message": "phone_model_id, problem_id, part_type & field are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
        try:
            obj = RepairPrice.objects.get(
                phone_model_id=phone_model_id,
                problem_id=problem_id,
                part_type=part_type
            )
        except RepairPrice.DoesNotExist:
            return Response(
                {"success": False, "message": "Repair price not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
        # Allowed fields to update
        allowed_fields = [
            "base_price", "discount_percentage", "discount_amount", 
            "in_stock", "is_active", "warranty_days"
        ]
        
        if field not in allowed_fields:
            return Response(
                {"success": False, "message": f"Field '{field}' is not allowed to be updated"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
        # Convert numeric fields
        numeric_fields = ["base_price", "discount_percentage", "discount_amount"]
        if field in numeric_fields:
            try:
                value = Decimal(str(value))
            except (ValueError, TypeError):
                return Response(
                    {"success": False, "message": f"Invalid value for {field}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
    
        # Boolean fields
        boolean_fields = ["in_stock", "is_active"]
        if field in boolean_fields:
            value = str(value).lower() in ['true', '1', 'yes']
    
        # Integer fields
        integer_fields = ["warranty_days"]
        if field in integer_fields:
            try:
                value = int(value)
            except (ValueError, TypeError):
                return Response(
                    {"success": False, "message": f"Invalid value for {field}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
    
        # Update field
        setattr(obj, field, value)
        obj.save()
    
        return Response({
            "success": True,
            "message": f"{field} updated successfully",
            "data": RepairPriceSerializer(obj).data
        }, status=status.HTTP_200_OK)
    
class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for orders
    - Create new order with Stripe payment
    - List orders (user's own orders if authenticated)
    - Retrieve order details
    - Confirm payment
    - Cancel order with refund
    - Calculate price
    - Check payment status
    """

    permission_classes = [IsAuthenticated]
    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        elif self.action == "list":
            return OrderListSerializer
        return OrderSerializer

    def get_queryset(self):
        queryset = Order.objects.select_related(
            "phone_model", "phone_model__brand", "user"
        ).prefetch_related(
            Prefetch(
                "order_items", queryset=OrderItem.objects.select_related("problem")
            )
        )

        # Filter by user if authenticated
        if self.request.user.is_authenticated and not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(user=self.request.user) | Q(customer_email=self.request.user.email)
            )

        # Filter by status
        status_param = self.request.query_params.get("status", None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by payment status
        payment_status_param = self.request.query_params.get("payment_status", None)
        if payment_status_param:
            queryset = queryset.filter(payment_status=payment_status_param)

        return queryset

    def list(self, request, *args, **kwargs):
        """List all orders with filters"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "success": True,
                "message": "Orders retrieved successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def retrieve(self, request, *args, **kwargs):
        """Retrieve single order details"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(
            {
                "success": True,
                "message": "Order details retrieved successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new order with Stripe payment integration
        Body: {
            "phone_model_id": 1,
            "customer_name": "John Doe",
            "customer_email": "john@example.com",
            "customer_phone": "+1234567890",
            "items": [
                {"problem_id": 1, "part_type": "original"},
                {"problem_id": 2, "part_type": "duplicate"}
            ],
            "notes": "Please handle with care"
        }
        """
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        phone_model = PhoneModel.objects.get(id=data["phone_model_id"])

        # Get website discount
        website_discount_obj = WebsiteDiscount.objects.filter(is_active=True).first()
        website_discount_percentage = website_discount_obj.percentage if website_discount_obj else Decimal("0.00")
        website_discount_amount = website_discount_obj.amount if website_discount_obj else Decimal("0.00")

        # Create order
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            customer_name=data["customer_name"],
            customer_email=data["customer_email"],
            customer_phone=data["customer_phone"],
            phone_model=phone_model,
            subtotal=Decimal("0.00"),
            item_discount=Decimal("0.00"),
            website_discount_percentage=website_discount_percentage,
            website_discount_amount=website_discount_amount,
            total_amount=Decimal("0.00"),
            notes=data.get("notes", ""),
            status="pending",
            payment_status="pending",
        )

        # Create order items
        for item_data in data["items"]:
            repair_price = RepairPrice.objects.select_related("problem").get(
                phone_model=phone_model,
                problem_id=item_data["problem_id"],
                part_type=item_data["part_type"],
                is_active=True,
            )

            OrderItem.objects.create(
                order=order,
                problem=repair_price.problem,
                part_type=item_data["part_type"],
                base_price=repair_price.base_price,
                discount_percentage=repair_price.discount_percentage,
                discount_amount=repair_price.discount_amount,
                final_price=repair_price.final_price,
                warranty_days=repair_price.warranty_days,
            )

        # Calculate totals
        order.calculate_totals()
        order.save()

        # Create Stripe Payment Intent
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(order.total_amount * 100),  # Convert to cents
                currency='bdt',  # Bangladesh Taka
                metadata={
                    'order_id': order.id,
                    'order_number': order.order_number,
                    'customer_email': order.customer_email,
                    'phone_model': str(phone_model)
                },
                description=f"Repair Order {order.order_number} - {phone_model}"
            )
            
            order.payment_intent_id = payment_intent.id
            order.save()
            
            output_serializer = OrderSerializer(order)
            
            return Response(
                {
                    "success": True,
                    "message": "Order created successfully",
                    "data": {
                        "order": output_serializer.data,
                        "payment": {
                            "client_secret": payment_intent.client_secret,
                            "payment_intent_id": payment_intent.id,
                            "amount": str(order.total_amount),
                            "currency": "BDT"
                        }
                    }
                },
                status=status.HTTP_201_CREATED,
            )
            
        except stripe.error.StripeError as e:
            # If Stripe fails, delete the order
            order.delete()
            return Response(
                {
                    "success": False,
                    "message": f"Payment initialization failed: {str(e)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def confirm_payment(self, request, pk=None):
        """
        Confirm payment after successful Stripe payment
        Body: {
            "payment_intent_id": "pi_xxxxxxxxxxxxx"
        }
        """
        order = self.get_object()
        
        payment_intent_id = request.data.get('payment_intent_id')
        
        if not payment_intent_id or order.payment_intent_id != payment_intent_id:
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
                    order.payment_method = payment_intent.payment_method_types[0] if payment_intent.payment_method_types else 'card'
                    order.save()
                    
                    # Set warranty expiry for all items
                    for item in order.order_items.all():
                        item.set_warranty_expiry()
                        item.save()
                
                serializer = OrderSerializer(order)
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

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def cancel_order(self, request, pk=None):
        """
        Cancel an order and process refund if payment was made
        """
        order = self.get_object()
        
        # Only allow cancellation of pending/confirmed orders
        if order.status not in ['pending', 'confirmed']:
            return Response({
                'success': False,
                'message': f'Cannot cancel order with status: {order.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Refund if payment was made
            if order.payment_status == 'paid' and order.payment_intent_id:
                try:
                    refund = stripe.Refund.create(
                        payment_intent=order.payment_intent_id
                    )
                    order.payment_status = 'refunded'
                except stripe.error.StripeError as e:
                    return Response({
                        'success': False,
                        'message': f'Refund failed: {str(e)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            order.status = 'cancelled'
            order.save()
        
        serializer = OrderSerializer(order)
        return Response({
            'success': True,
            'message': 'Order cancelled successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def calculate_order_price(self, request):
        """
        Calculate total price for selected repairs before creating order
        Body: {
            "phone_model_id": 1,
            "items": [
                {"problem_id": 1, "part_type": "original"},
                {"problem_id": 2, "part_type": "duplicate"}
            ]
        }
        """
        phone_model_id = request.data.get("phone_model_id")
        items_data = request.data.get("items", [])

        if not phone_model_id:
            return Response(
                {"success": False, "message": "phone_model_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not items_data:
            return Response(
                {"success": False, "message": "items list is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            phone_model = PhoneModel.objects.get(id=phone_model_id, is_active=True)
        except PhoneModel.DoesNotExist:
            return Response(
                {"success": False, "message": "Invalid or inactive phone model"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get website discount
        website_discount_obj = WebsiteDiscount.objects.filter(is_active=True).first()
        website_discount_percentage = (
            website_discount_obj.percentage if website_discount_obj else Decimal("0.00")
        )
        website_discount_amount = (
            website_discount_obj.amount if website_discount_obj else Decimal("0.00")
        )

        # Calculate pricing
        subtotal = Decimal("0.00")
        item_discount = Decimal("0.00")
        items_breakdown = []

        for item_data in items_data:
            problem_id = item_data.get("problem_id")
            part_type = item_data.get("part_type", "original")

            try:
                repair_price = RepairPrice.objects.select_related("problem").get(
                    phone_model=phone_model,
                    problem_id=problem_id,
                    part_type=part_type,
                    is_active=True,
                )
                
                if not repair_price.in_stock:
                    return Response({
                        'success': False,
                        'message': f'Part not in stock for {repair_price.problem.name} ({part_type})'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                base_price = repair_price.base_price
                final_price = repair_price.final_price
                discount = base_price - final_price

                subtotal += base_price
                item_discount += discount

                items_breakdown.append(
                    {
                        "problem_id": problem_id,
                        "problem_name": repair_price.problem.name,
                        "part_type": part_type,
                        "base_price": str(base_price),
                        "discount": str(discount),
                        "final_price": str(final_price),
                        "warranty_days": repair_price.warranty_days,
                    }
                )

            except RepairPrice.DoesNotExist:
                return Response(
                    {
                        "success": False,
                        "message": f"Invalid repair option for problem ID {problem_id} with part type {part_type}",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Price after item discounts
        price_after_items = subtotal - item_discount

        # Apply website discount
        website_discount = (
            price_after_items * (website_discount_percentage / Decimal("100"))
        ) + website_discount_amount

        # Final total
        total_amount = max(price_after_items - website_discount, Decimal("0.00"))
        total_discount = subtotal - total_amount

        return Response(
            {
                "success": True,
                "message": "Repair price calculated successfully",
                "data": {
                    "phone_model": phone_model.name,
                    "brand": phone_model.brand.name,
                    "subtotal": str(subtotal),
                    "item_discount": str(item_discount),
                    "price_after_item_discount": str(price_after_items),
                    "website_discount_percentage": str(website_discount_percentage),
                    "website_discount_amount": str(website_discount_amount),
                    "website_discount": str(website_discount),
                    "total_amount": str(total_amount),
                    "total_discount": str(total_discount),
                    "items": items_breakdown,
                },
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['get'], permission_classes=[IsAdmin])
    def payment_status(self, request, pk=None):
        """
        Check payment status of an order
        """
        order = self.get_object()
        
        response_data = {
            'order_number': order.order_number,
            'status': order.status,
            'payment_status': order.payment_status,
            'total_amount': str(order.total_amount),
        }
        
        # If payment intent exists, fetch latest status from Stripe
        if order.payment_intent_id:
            try:
                payment_intent = stripe.PaymentIntent.retrieve(order.payment_intent_id)
                response_data['stripe_status'] = payment_intent.status
                response_data['payment_method'] = order.payment_method
            except stripe.error.StripeError:
                pass
        
        return Response({
            'success': True,
            'message': 'Payment status retrieved',
            'data': response_data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Confirm an order (admin only in production) - Legacy endpoint"""
        order = self.get_object()

        if order.status != "pending":
            return Response(
                {
                    "success": False,
                    "message": "Only pending orders can be confirmed",
                    "data": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = "confirmed"
        order.confirmed_at = timezone.now()
        order.save()

        # Set warranty expiry for all items
        for item in order.order_items.all():
            item.set_warranty_expiry()
            item.save()

        serializer = self.get_serializer(order)
        return Response(
            {"success": True, "data": serializer.data}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel an order - Legacy endpoint (use cancel_order instead)"""
        order = self.get_object()

        if order.status in ["completed", "cancelled", "refunded"]:
            return Response(
                {
                    "success": False,
                    "message": f"Cannot cancel order with status: {order.status}",
                    "data": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = "cancelled"
        order.save()

        serializer = self.get_serializer(order)
        return Response(
            {"success": True, "data": serializer.data}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["get"])
    def track(self, request, pk=None):
        """Track order status"""
        order = self.get_object()
        serializer = self.get_serializer(order)
        return Response(
            {"success": True, "data": serializer.data}, status=status.HTTP_200_OK
        )
    
#=========== Repair Review Portion =============
class RepairReviewViewSet(viewsets.ModelViewSet):
    serializer_class = RepairReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    http_method_names = ['get', 'post', 'delete']  # Only allow GET, POST, DELETE

    def get_queryset(self):
        queryset = PhoneReview.objects.select_related('phone_model__brand', 'order')
        
        # Filter by phone model (for admin to see all reviews of a product)
        phone_id = self.request.query_params.get('phone_model')
        if phone_id:
            queryset = queryset.filter(phone_model_id=phone_id)
        
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
        create_serializer = RepairReviewCreateSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)
        
        # Get order
        order = Order.objects.get(id=create_serializer.validated_data['order_id'])
        
        # Create review
        review = PhoneReview.objects.create(
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


# ========== NEW VIEW FOR ADMIN REPAIR ORDER LIST ==========
from rest_framework.views import APIView
from django.db.models import Count, Sum, Avg, Q

class AdminRepairOrderListView(APIView):
    """
    API endpoint for admins to view all repair orders with comprehensive details
    Requires authentication and admin role
    GET: Returns list of all repair orders with filtering and statistics
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Check if user is admin
        if request.user.role != 'admin':
            return Response({
                'success': False,
                'message': 'Permission denied. Only admins can access all repair orders.'
            }, status=status.HTTP_403_FORBIDDEN)

        # Get all orders with related data
        queryset = Order.objects.select_related(
            'user', 'phone_model__brand'
        ).prefetch_related(
            Prefetch(
                'order_items',
                queryset=OrderItem.objects.select_related('problem')
            )
        )

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

        # Filter by phone brand
        brand = request.query_params.get('brand')
        if brand:
            queryset = queryset.filter(phone_model__brand__slug=brand)

        # Filter by phone model
        phone_model = request.query_params.get('phone_model')
        if phone_model:
            queryset = queryset.filter(phone_model_id=phone_model)

        # Filter by payment method
        payment_method = request.query_params.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
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
        
        # Count total repair items across all orders
        total_repair_items = OrderItem.objects.filter(
            order__in=queryset
        ).count()
        
        # # Most common repair problems
        # top_problems = OrderItem.objects.filter(
        #     order__in=queryset
        # ).values(
        #     'problem__name'
        # ).annotate(
        #     count=Count('id')
        # ).order_by('-count')[:5]
        # ========== END STATISTICS ==========

        # Serialize order data
        serializer = AdminRepairOrderListSerializer(queryset, many=True)

        return Response({
            'success': True,
            'message': 'Admin repair order list retrieved successfully',
            'statistics': {
                'total_orders': total_orders,
                'status_summary': status_summary,
                'payment_summary': payment_summary,
                'total_revenue': str(total_revenue),
                'pending_revenue': str(pending_revenue),
                # 'average_order_value': str(round(average_order_value, 2)) if average_order_value else '0.00',
                'total_repair_items': total_repair_items,
                # 'top_repair_problems': list(top_problems)
            },
            'data': serializer.data
        }, status=status.HTTP_200_OK)
# ========== END NEW VIEW ==========