from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets, permissions, status
from django.core.mail import send_mail
from django.conf import settings
import random
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.decorators import action
from .models import *
from .serializers import *
from .utils import *
import logging
from product.views import *
from brandNew.views import *
from accessories.views import *
from .permissions import IsAdmin, IsOwnerOrReadOnly, IsUser
from django.db.models import Count, Sum, Q
from decimal import Decimal
# from .mypaginations import MyLimitOffsetPagination

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

from .utils import (
    verify_google_access_token, 
    verify_apple_access_token,
    get_google_user_info,
    get_apple_user_info
)


"""Generate JWT tokens"""
def tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


"""Email OTP Registration Flow"""
class SendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = SendOTPSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        email = ser.validated_data['email'].lower()
        code = f"{random.randint(0, 999999):06d}"

        user, created = User.objects.get_or_create(
            email=email,
            defaults={'username': email.split('@')[0]}
        )
        user.verification_code = code
        user.email_verified = False
        user.is_oauth_user = False
        user.username_set = False
        user.save()

        # Render HTML template
        html_content = render_to_string('emails/otp_email.html', {
            'email': email,
            'code': code
        })

        # Send email
        email_message = EmailMultiAlternatives(
            subject='Your Verification Code',
            body=f'Your verification code is {code}',  # fallback text
            from_email=settings.EMAIL_HOST_USER,
            to=[email]
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send(fail_silently=False)

        return Response({"message": "OTP sent to your email."}, status=201)


"""Verify Token"""
class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = VerifyOTPSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        email = ser.validated_data['email'].lower()
        code = ser.validated_data['code']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        if user.verification_code == code:
            user.email_verified = True
            user.verification_code = ''
            user.save()
            return Response({"message": "Email verified successfully. Now set username and password."})

        return Response({"error": "Invalid code"}, status=400)


"""Set Credential"""
class SetCredentialsView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user = request.user if request.user and request.user.is_authenticated else None
        ser = SetCredentialsSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        if user is None:
            email = request.data.get('email')
            if not email:
                return Response({"error": "If not authenticated, include 'email' field."}, status=400)
            try:
                user = User.objects.get(email=email.lower())
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=404)
            if not user.email_verified:
                return Response({"error": "Email not verified"}, status=400)

        if user.username_set:
            return Response({"error": "Credentials already set."}, status=403)

        username = ser.validated_data['username']
        password = ser.validated_data['password']

        if User.objects.filter(username=username).exclude(pk=user.pk).exists():
            return Response({"username": "Already taken."}, status=400)

        user.username = username
        user.set_password(password)
        user.username_set = True
        user.save()

        return Response({"message": "Credentials set successfully. You can now log in."}, status=201)

"""Login View"""
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        key = ser.validated_data['email_or_username']
        password = ser.validated_data['password']

        user = authenticate(username=key, password=password)
        if user is None:
            try:
                u = User.objects.get(email=key.lower())
                user = authenticate(username=u.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            return Response({"error": "Invalid credentials"}, status=401)

        if not user.email_verified:
            return Response({"error": "Email not verified"}, status=403)

        return Response(
            {
                "message": "Login successful",
                "user": {
                    "name": user.username,
                    "email": user.email,
                    "role": user.role,
                },
                "tokens": tokens_for_user(user),
            },
            status=200
        )
        


"""OAuth Register View - Using Access Token"""
class OAuthRegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Log incoming request data for debugging
        logger.info(f"OAuth Register Request Data: {request.data}")
        
        serializer = OAuthRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Serializer Validation Error: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        access_token = serializer.validated_data['access_token']
        provider = serializer.validated_data['provider'].lower()

        logger.info(f"Provider: {provider}")

        # Verify access token and get user email based on provider
        email = None
        user_info = None

        try:
            if provider == 'google':
                # For Google: Use userinfo endpoint (PRIMARY METHOD)
                user_info = get_google_user_info(access_token)
                if user_info:
                    email = user_info.get('email')
                    logger.info(f"Google user info retrieved: {user_info}")
                else:
                    # Fallback: Try tokeninfo endpoint
                    email = verify_google_access_token(access_token)
                    logger.info(f"Google tokeninfo result: {email}")

            elif provider == 'apple':
                # For Apple: Verify JWT token
                email = verify_apple_access_token(access_token)
                logger.info(f"Apple token verification result: {email}")
                
                # Fallback: Get user info without verification
                if not email:
                    user_info = get_apple_user_info(access_token)
                    if user_info:
                        email = user_info.get('email')
                        logger.info(f"Apple user info: {user_info}")
            else:
                return Response(
                    {"error": "Unsupported provider. Use 'google' or 'apple'."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not email:
                logger.error(f"Failed to get email from {provider} token")
                return Response(
                    {
                        "error": f"Invalid {provider} access token or unable to retrieve user information.",
                        "details": "Please ensure the token is valid and has not expired."
                    }, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate username from email (part before @)
            base_username = email.split('@')[0].lower()
            # Remove special characters from username
            base_username = ''.join(c if c.isalnum() or c in ['_', '.'] else '_' for c in base_username)
            username = base_username

            # Check if user already exists
            try:
                existing_user = User.objects.get(email=email)
                logger.info(f"User already exists: {email}")
                return Response(
                    {
                        "message": "User already registered with this email.",
                        "email": email,
                        "username": existing_user.username,
                        "provider": provider
                    }, 
                    status=status.HTTP_200_OK
                )
            except User.DoesNotExist:
                pass

            # Ensure username is unique
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            # Create new user
            user = User.objects.create(
                email=email,
                username=username,
                email_verified=True,
                is_oauth_user=True,
                username_set=True
            )

            # Set unusable password for OAuth users
            user.set_unusable_password()
            user.save()

            logger.info(f"User created successfully: {email}")

            return Response(
                {
                    "message": f"User registered successfully via {provider.title()}.",
                    "email": email,
                    "username": username,
                    "provider": provider
                }, 
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"OAuth Register Error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"An error occurred during registration: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


"""OAuth Login View - Using Access Token"""
class OAuthLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Log incoming request data for debugging
        logger.info(f"OAuth Login Request Data: {request.data}")
        
        serializer = OAuthLoginSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Serializer Validation Error: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        access_token = serializer.validated_data['access_token']
        provider = serializer.validated_data['provider'].lower()

        logger.info(f"Provider: {provider}")

        # Verify access token and get user email based on provider
        email = None
        user_info = None

        try:
            if provider == 'google':
                # For Google: Use userinfo endpoint (PRIMARY METHOD)
                user_info = get_google_user_info(access_token)
                if user_info:
                    email = user_info.get('email')
                    logger.info(f"Google user info retrieved: {user_info}")
                else:
                    # Fallback: Try tokeninfo endpoint
                    email = verify_google_access_token(access_token)
                    logger.info(f"Google tokeninfo result: {email}")

            elif provider == 'apple':
                # For Apple: Verify JWT token
                email = verify_apple_access_token(access_token)
                logger.info(f"Apple token verification result: {email}")
                
                # Fallback: Get user info without verification
                if not email:
                    user_info = get_apple_user_info(access_token)
                    if user_info:
                        email = user_info.get('email')
                        logger.info(f"Apple user info: {user_info}")
            else:
                return Response(
                    {"error": "Unsupported provider. Use 'google' or 'apple'."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not email:
                logger.error(f"Failed to get email from {provider} token")
                return Response(
                    {
                        "error": f"Invalid {provider} access token or unable to retrieve user information.",
                        "details": "Please ensure the token is valid and has not expired."
                    }, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if user exists
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                logger.error(f"User not found: {email}")
                return Response(
                    {
                        "error": "User not registered. Please register first.",
                        "email": email
                    }, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Verify user is an OAuth user
            if not user.is_oauth_user:
                logger.error(f"User is not OAuth user: {email}")
                return Response(
                    {"error": "This account was not registered via OAuth. Please use email/password login."}, 
                    status=status.HTTP_403_FORBIDDEN
                )

            # Generate tokens
            tokens = tokens_for_user(user)

            logger.info(f"User logged in successfully: {email}")

            return Response(
                {
                    "message": f"Logged in successfully via {provider.title()}.",
                    "tokens": tokens,
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "username": user.username,
                        "provider": provider
                    }
                }, 
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"OAuth Login Error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"An error occurred during login: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class UserListView(APIView):
    """
    API endpoint for admins to view all registered users.
    Requires authentication and admin role.
    GET: Returns list of all users with their details
    """
    permission_classes = [IsAuthenticated]
    # pagination_class = MyLimitOffsetPagination

    def get(self, request):
        if request.user.role != 'admin':
            logger.warning(f"Non-admin user {request.user.email} attempted to access user list")
            return Response(
                {"error": "Permission denied. Only admins can access user list."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        users = User.objects.all().order_by('-date_joined')
        
        paginator = MyLimitOffsetPagination()
        page = paginator.paginate_queryset(users, request)  # only paginated queryset
        serializer = UserListSerializer(page, many=True)
        
        logger.info(f"Admin {request.user.email} accessed user list. Total users: {users.count()}")
        
        return Response(
            {
                "message": "User list retrieved successfully",
                "total_users": users.count(),
                "users": serializer.data
            }, 
            status=status.HTTP_200_OK
        )
        
#================ Webhook Implementation ================
# ============================================
# Add this to accounts/views.py
# ============================================
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from rest_framework.views import APIView
import stripe
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    """
    Unified Stripe webhook for all order types
    Handles: Repair Orders, New Phone Orders, Accessory Orders
    """
    permission_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError:
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            return HttpResponse(status=400)

        # Handle successful payment
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            self.handle_payment_success(payment_intent)

        return HttpResponse(status=200)

    def handle_payment_success(self, payment_intent):
        """Handle successful payment for any order type"""
        from product.models import Order
        from brandNew.models import NewPhoneOrder
        from accessories.models import AcsOrder

        payment_intent_id = payment_intent.id

        # Try to find order in all three models
        order = None
        order_type = None

        # Check Repair Orders
        try:
            order = Order.objects.get(payment_intent_id=payment_intent_id)
            order_type = 'repair'
        except Order.DoesNotExist:
            pass

        # Check New Phone Orders
        if not order:
            try:
                order = NewPhoneOrder.objects.get(stripe_payment_intent_id=payment_intent_id)
                order_type = 'phone'
            except NewPhoneOrder.DoesNotExist:
                pass

        # Check Accessory Orders
        if not order:
            try:
                order = AcsOrder.objects.get(stripe_payment_intent_id=payment_intent_id)
                order_type = 'accessory'
            except AcsOrder.DoesNotExist:
                pass

        # If order found, process it
        if order and order.payment_status != 'paid':
            try:
                # Update order
                order.payment_status = 'paid'
                order.status = 'confirmed'
                order.confirmed_at = timezone.now()
                order.save()

                # Send customer email
                self.send_customer_email(order, order_type)

                # Send admin email
                self.send_admin_email(order, order_type)

                logger.info(f"Webhook: Payment confirmed for {order_type} order {order.order_number}")

            except Exception as e:
                logger.error(f"Webhook error: {str(e)}")

    def send_customer_email(self, order, order_type):
        """Send payment confirmation to customer with HTML template"""
        if order_type == 'repair':
            product_name = f"{order.phone_model} Repair"
        elif order_type == 'phone':
            product_name = order.phone_model.name
        else:
            product_name = order.product.title

        subject = f'Payment Successful - Order {order.order_number}'

        html_content = render_to_string('emails/payment_success.html', {
            'customer_name': order.customer_name,
            'order_number': order.order_number,
            'product_name': product_name,
            'total_amount': order.total_amount,
        })

        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=f"Hello {order.customer_name}, your payment was successful!",  # fallback text
                from_email=settings.EMAIL_HOST_USER,
                to=[order.customer_email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
            logger.info(f"Customer email sent to {order.customer_email}")
        except Exception as e:
            logger.error(f"Failed to send customer email: {str(e)}")

    def send_admin_email(self, order, order_type):
        """Send new order notification to admins with HTML template"""
        from accounts.models import User

        if order_type == 'repair':
            product_name = f"{order.phone_model} Repair"
        elif order_type == 'phone':
            product_name = order.phone_model.name
        else:
            product_name = order.product.title

        subject = f'New Order - {order.order_number}'

        html_content = render_to_string('emails/new_order_admin.html', {
            'order_type': order_type.title(),
            'order_number': order.order_number,
            'customer_name': order.customer_name,
            'customer_email': order.customer_email,
            'customer_phone': order.customer_phone,
            'product_name': product_name,
            'total_amount': order.total_amount,
        })

        admin_emails = User.objects.filter(role='admin').values_list('email', flat=True)
        if admin_emails:
            try:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body="New payment received.",  # fallback text
                    from_email=settings.EMAIL_HOST_USER,
                    to=list(admin_emails)
                )
                email.attach_alternative(html_content, "text/html")
                email.send(fail_silently=False)
                logger.info(f"Admin email sent to {len(admin_emails)} admins")
            except Exception as e:
                logger.error(f"Failed to send admin email: {str(e)}")


#================== Combine Order List ====================
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Avg, Q, Prefetch
from decimal import Decimal
from itertools import chain
from operator import attrgetter

class UnifiedAdminOrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'admin':
            return Response({
                'success': False,
                'message': 'Permission denied. Only admins can access all orders.'
            }, status=status.HTTP_403_FORBIDDEN)

        order_type = request.query_params.get('order_type', 'all').lower()
        
        phone_orders = []
        accessory_orders = []
        repair_orders = []
        
        if order_type in ['all', 'phone']:
            phone_queryset = NewPhoneOrder.objects.select_related(
                'user', 'phone_model__brand', 'selected_color'
            ).prefetch_related('phone_model__colors')
            
            phone_queryset = self._apply_common_filters(phone_queryset, request)
            
            brand = request.query_params.get('brand')
            if brand:
                phone_queryset = phone_queryset.filter(phone_model__brand__slug=brand)
            
            phone_orders = list(phone_queryset)
            for order in phone_orders:
                order.order_type = 'phone'

        if order_type in ['all', 'accessory']:
            accessory_queryset = AcsOrder.objects.select_related('user', 'product')
            
            accessory_queryset = self._apply_common_filters(accessory_queryset, request)
            
            product_id = request.query_params.get('product')
            if product_id:
                accessory_queryset = accessory_queryset.filter(product_id=product_id)
            
            city = request.query_params.get('city')
            if city:
                accessory_queryset = accessory_queryset.filter(city__icontains=city)
            
            country = request.query_params.get('country')
            if country:
                accessory_queryset = accessory_queryset.filter(country__icontains=country)
            
            accessory_orders = list(accessory_queryset)
            for order in accessory_orders:
                order.order_type = 'accessory'

        # ========== FETCH AND FILTER REPAIR ORDERS ==========
        if order_type in ['all', 'repair']:
            repair_queryset = Order.objects.select_related(
                'user', 'phone_model__brand'
            ).prefetch_related(
                Prefetch(
                    'order_items',
                    queryset=OrderItem.objects.select_related('problem')
                )
            )
            
            repair_queryset = self._apply_common_filters(repair_queryset, request)
            
            brand = request.query_params.get('brand')
            if brand:
                repair_queryset = repair_queryset.filter(phone_model__brand__slug=brand)
            
            phone_model = request.query_params.get('phone_model')
            if phone_model:
                repair_queryset = repair_queryset.filter(phone_model_id=phone_model)
            
            payment_method = request.query_params.get('payment_method')
            if payment_method:
                repair_queryset = repair_queryset.filter(payment_method=payment_method)
            
            repair_orders = list(repair_queryset)
            for order in repair_orders:
                order.order_type = 'repair'

        # ========== COMBINE AND SORT ALL ORDERS ==========
        combined_orders = sorted(
            chain(phone_orders, accessory_orders, repair_orders),
            key=attrgetter('created_at'),
            reverse=True
        )

        # ========== CALCULATE COMBINED STATISTICS ==========
        statistics = self._calculate_statistics(
            phone_orders, accessory_orders, repair_orders
        )

        # ========== SERIALIZE ORDERS ==========
        serialized_data = []
        for order in combined_orders:
            if order.order_type == 'phone':
                serialized_data.append(self._serialize_phone_order(order))
            elif order.order_type == 'accessory':
                serialized_data.append(self._serialize_accessory_order(order))
            elif order.order_type == 'repair':
                serialized_data.append(self._serialize_repair_order(order))

        return Response({
            'success': True,
            'message': 'Combine order list retrieved successfully',
            'filter_applied': {
                'order_type': order_type,
            },
            'statistics': statistics,
            'data': serialized_data
        }, status=status.HTTP_200_OK)

    def _apply_common_filters(self, queryset, request):
        """Apply filters common to all order types"""
        
        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        payment_status_param = request.query_params.get('payment_status')
        if payment_status_param:
            queryset = queryset.filter(payment_status=payment_status_param)

        customer_email = request.query_params.get('customer_email')
        if customer_email:
            queryset = queryset.filter(customer_email__icontains=customer_email)

        customer_phone = request.query_params.get('customer_phone')
        if customer_phone:
            queryset = queryset.filter(customer_phone__icontains=customer_phone)

        order_number = request.query_params.get('order_number')
        if order_number:
            queryset = queryset.filter(order_number__icontains=order_number)

        date_from = request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)

        return queryset

    def _calculate_statistics(self, phone_orders, accessory_orders, repair_orders):
        """Calculate combined statistics for all order types"""
        
        all_orders = phone_orders + accessory_orders + repair_orders
        total_orders = len(all_orders)
        
        order_type_summary = {
            'phone': len(phone_orders),
            'accessory': len(accessory_orders),
            'repair': len(repair_orders)
        }

        status_summary = {}
        for order in all_orders:
            status = order.status
            status_summary[status] = status_summary.get(status, 0) + 1
        
        payment_summary = {}
        for order in all_orders:
            payment_status = order.payment_status
            payment_summary[payment_status] = payment_summary.get(payment_status, 0) + 1
        
        total_revenue = Decimal('0.00')
        pending_revenue = Decimal('0.00')
        
        for order in all_orders:
            if order.payment_status == 'paid':
                total_revenue += Decimal(str(order.total_amount))
            elif order.payment_status == 'pending':
                pending_revenue += Decimal(str(order.total_amount))
        
        revenue_by_type = {
            'phone': sum(Decimal(str(o.total_amount)) for o in phone_orders if o.payment_status == 'paid'),
            'accessory': sum(Decimal(str(o.total_amount)) for o in accessory_orders if o.payment_status == 'paid'),
            'repair': sum(Decimal(str(o.total_amount)) for o in repair_orders if o.payment_status == 'paid')
        }
        
        return {
            'total_orders': total_orders,
            'order_type_summary': order_type_summary,
            'status_summary': status_summary,
            'payment_summary': payment_summary,
            'total_revenue': str(total_revenue),
            'pending_revenue': str(pending_revenue),
            'revenue_by_type': {k: str(v) for k, v in revenue_by_type.items()}
        }

    def _serialize_phone_order(self, order):
        """Serialize phone order data"""
        return {
            'id': order.id,
            'order_type': 'phone',
            'order_number': order.order_number,
            'customer_name': order.customer_name,
            'customer_email': order.customer_email,
            'customer_phone': order.customer_phone,
            'phone_model': {
                'id': order.phone_model.id,
                'name': order.phone_model.name,
                'brand': order.phone_model.brand.name if order.phone_model.brand else None
            },
            'selected_color': order.selected_color.name if order.selected_color else None,
            'quantity': order.quantity,
            'total_amount': str(order.total_amount),
            'status': order.status,
            'payment_status': order.payment_status,
            'created_at': order.created_at.isoformat(),
            'updated_at': order.updated_at.isoformat()
        }

    def _serialize_accessory_order(self, order):
        """Serialize accessory order data"""
        return {
            'id': order.id,
            'order_type': 'accessory',
            'order_number': order.order_number,
            'customer_name': order.customer_name,
            'customer_email': order.customer_email,
            'customer_phone': order.customer_phone,
            'product': {
                'id': order.product.id,
                'title': order.product.title
            } if order.product else None,
            'quantity': order.quantity,
            'total_amount': str(order.total_amount),
            'city': order.city,
            'country': order.country,
            'status': order.status,
            'payment_status': order.payment_status,
            'created_at': order.created_at.isoformat(),
            'updated_at': order.updated_at.isoformat()
        }

    def _serialize_repair_order(self, order):
        """Serialize repair order data"""
        return {
            'id': order.id,
            'order_type': 'repair',
            'order_number': order.order_number,
            'customer_name': order.customer_name,
            'customer_email': order.customer_email,
            'customer_phone': order.customer_phone,
            'phone_model': {
                'id': order.phone_model.id,
                'name': order.phone_model.name,
                'brand': order.phone_model.brand.name if order.phone_model.brand else None
            } if order.phone_model else None,
            'repair_items': [
                {
                    'problem': item.problem.name if item.problem else None,
                    'price': str(item.price)
                }
                for item in order.order_items.all()
            ],
            'total_amount': str(order.total_amount),
            'payment_method': order.payment_method,
            'status': order.status,
            'payment_status': order.payment_status,
            'created_at': order.created_at.isoformat(),
            'updated_at': order.updated_at.isoformat()
        }