from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdmin
from shops.models import Shop
from products.models import Product
from orders.models import Order, OrderItem
from payments.models import (
    AdminCommission,
    FinancialTransaction,
)


# ================================================================
# ADMIN DASHBOARD
# ================================================================

class AdminDashboardView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request):

        total_users = User.objects.count()

        total_customers = User.objects.filter(
            role="customer"
        ).count()

        total_shop_owners = User.objects.filter(
            role="shop_owner"
        ).count()

        total_shops = Shop.objects.count()

        active_shops = Shop.objects.filter(
            is_active=True
        ).count()

        inactive_shops = Shop.objects.filter(
            is_active=False
        ).count()

        total_products = Product.objects.count()

        available_products = Product.objects.filter(
            is_available=True
        ).count()

        total_orders = Order.objects.count()

        pending_orders = Order.objects.filter(
            status="pending"
        ).count()

        processing_orders = Order.objects.filter(
            status="processing"
        ).count()

        shipped_orders = Order.objects.filter(
            status="shipped"
        ).count()

        delivered_orders = Order.objects.filter(
            status="delivered"
        ).count()

        cancelled_orders = Order.objects.filter(
            status="cancelled"
        ).count()

        sales_expression = ExpressionWrapper(
            F("price") * F("quantity"),
            output_field=DecimalField(
                max_digits=14,
                decimal_places=2,
            ),
        )

        total_sales = (
            OrderItem.objects
            .exclude(order__status="cancelled")
            .aggregate(
                total=Sum(sales_expression)
            )["total"]
            or Decimal("0.00")
        )

        total_sales = Decimal(total_sales).quantize(
            Decimal("0.01")
        )

        commission = (
            AdminCommission.objects
            .aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        commission = Decimal(commission).quantize(
            Decimal("0.01")
        )

        return Response({
            "users": {
                "total": total_users,
                "customers": total_customers,
                "shop_owners": total_shop_owners,
            },
            "shops": {
                "total": total_shops,
                "active": active_shops,
                "inactive": inactive_shops,
            },
            "products": {
                "total": total_products,
                "available": available_products,
            },
            "orders": {
                "total": total_orders,
                "pending": pending_orders,
                "processing": processing_orders,
                "shipped": shipped_orders,
                "delivered": delivered_orders,
                "cancelled": cancelled_orders,
            },
            "financial": {
                "sales": str(total_sales),
                "commission": str(commission),
            },
        })


# ================================================================
# COMMISSION HISTORY / RECONCILIATION
# ================================================================

class AdminCommissionHistoryView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request):
        commissions = (
            AdminCommission.objects
            .select_related(
                "order",
                "order_item",
                "shop",
                "seller",
            )
            .order_by("-id")
        )

        admin = request.user

        total_commission = Decimal("0.00")
        admin_attributed = Decimal("0.00")
        legacy_attributed = Decimal("0.00")

        history = []

        for commission in commissions:
            amount = Decimal(
                commission.total_amount
            ).quantize(Decimal("0.01"))

            total_commission += amount

            reference = (
                f"COMMISSION-"
                f"{commission.order_id}-"
                f"{commission.order_item_id}"
            )

            transaction = (
                FinancialTransaction.objects
                .filter(reference=reference)
                .first()
            )

            transaction_user = (
                transaction.user.username
                if transaction and transaction.user
                else None
            )

            is_admin_attributed = (
                transaction is not None
                and transaction.user_id == admin.id
            )

            if is_admin_attributed:
                admin_attributed += amount
                attribution = "Admin wallet"
                historical = False
            else:
                legacy_attributed += amount
                attribution = (
                    "Historical record"
                    if transaction_user
                    else "Unattributed record"
                )
                historical = True

            seller_name = (
                commission.seller.username
                if commission.seller
                else None
            )

            history.append({
                "id": commission.id,
                "order_id": commission.order_id,
                "order_item_id": commission.order_item_id,
                "amount": str(amount),
                "quantity": commission.quantity,
                "amount_per_unit": str(
                    commission.amount_per_unit
                ),
                "seller": seller_name,
                "transaction_user": transaction_user,
                "transaction_reference": reference,
                "attribution": attribution,
                "historical": historical,
                "created_at": (
                    commission.created_at
                    if hasattr(commission, "created_at")
                    else None
                ),
            })

        return Response({
            "summary": {
                "total_commission": str(
                    total_commission.quantize(
                        Decimal("0.01")
                    )
                ),
                "admin_attributed": str(
                    admin_attributed.quantize(
                        Decimal("0.01")
                    )
                ),
                "historical_or_unattributed": str(
                    legacy_attributed.quantize(
                        Decimal("0.01")
                    )
                ),
            },
            "history": history,
        })



# ================================================================
# CUSTOMERS
# ================================================================

class AdminCustomersView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request):

        customers = User.objects.filter(
            role="customer"
        ).order_by("-date_joined")

        data = []

        for customer in customers:
            data.append({
                "id": customer.id,
                "username": customer.username,
                "email": customer.email,
                "phone": customer.phone,
                "is_active": customer.is_active,
                "date_joined": customer.date_joined,
            })

        return Response({
            "count": len(data),
            "customers": data,
        })


class AdminCustomerDetailView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request, pk):

        try:
            customer = User.objects.get(
                pk=pk,
                role="customer",
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Customer not found."},
                status=404,
            )

        orders = Order.objects.filter(
            customer=customer
        )

        total_spent = (
            orders
            .exclude(status="cancelled")
            .aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        return Response({
            "id": customer.id,
            "username": customer.username,
            "email": customer.email,
            "phone": customer.phone,
            "is_active": customer.is_active,
            "date_joined": customer.date_joined,
            "orders": orders.count(),
            "total_spent": str(
                Decimal(total_spent).quantize(
                    Decimal("0.01")
                )
            ),
        })


class AdminCustomerStatusView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def patch(self, request, pk):

        try:
            customer = User.objects.get(
                pk=pk,
                role="customer",
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Customer not found."},
                status=404,
            )

        is_active = request.data.get("is_active")

        if not isinstance(is_active, bool):
            return Response(
                {
                    "is_active":
                        "This field must be true or false."
                },
                status=400,
            )

        customer.is_active = is_active
        customer.save(update_fields=["is_active"])

        return Response({
            "message": (
                "Customer activated successfully."
                if is_active
                else
                "Customer deactivated successfully."
            ),
            "customer": {
                "id": customer.id,
                "username": customer.username,
                "is_active": customer.is_active,
            },
        })


class AdminCustomerOrdersView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request, pk):

        try:
            customer = User.objects.get(
                pk=pk,
                role="customer",
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Customer not found."},
                status=404,
            )

        orders = (
            Order.objects
            .filter(customer=customer)
            .prefetch_related("items__product")
            .order_by("-created_at")
        )

        data = []

        for order in orders:

            items = []

            for item in order.items.all():

                items.append({
                    "product_id": item.product.id,
                    "product_name": item.product.name,
                    "quantity": item.quantity,
                    "price": str(item.price),
                    "total_price": str(
                        item.total_price
                    ),
                })

            data.append({
                "id": order.id,
                "full_name": order.full_name,
                "phone": order.phone,
                "address": order.address,
                "payment_method": order.payment_method,
                "status": order.status,
                "delivery_status": order.delivery_status,
                "total_amount": str(order.total_amount),
                "created_at": order.created_at,
                "items": items,
            })

        return Response({
            "customer": {
                "id": customer.id,
                "username": customer.username,
                "email": customer.email,
            },
            "count": len(data),
            "orders": data,
        })


# ================================================================
# SHOPS
# ================================================================

class AdminShopsView(APIView):
    """
    GET /api/admin/shops/

    Returns all shops.
    """

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request):

        shops = (
            Shop.objects
            .select_related("owner")
            .prefetch_related("products")
            .order_by("-created_at")
        )

        data = []

        for shop in shops:

            products = shop.products.all()

            data.append({
                "id": shop.id,
                "name": shop.name,
                "description": shop.description,
                "phone": shop.phone,
                "address": shop.address,
                "logo": (
                    request.build_absolute_uri(
                        shop.logo.url
                    )
                    if shop.logo
                    else None
                ),
                "is_active": shop.is_active,
                "created_at": shop.created_at,
                "updated_at": shop.updated_at,

                "owner": {
                    "id": shop.owner.id,
                    "username": shop.owner.username,
                    "email": shop.owner.email,
                    "phone": shop.owner.phone,
                },

                "products_count": products.count(),

                "available_products": products.filter(
                    is_available=True
                ).count(),
            })

        return Response({
            "count": len(data),
            "shops": data,
        })


class AdminShopDetailView(APIView):
    """
    GET /api/admin/shops/<id>/

    Returns detailed information about one shop.
    """

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request, pk):

        try:
            shop = (
                Shop.objects
                .select_related("owner")
                .get(pk=pk)
            )
        except Shop.DoesNotExist:
            return Response(
                {"detail": "Shop not found."},
                status=404,
            )

        products = Product.objects.filter(
            shop=shop
        )

        orders = (
            Order.objects
            .filter(
                items__product__shop=shop
            )
            .distinct()
        )

        sales_expression = ExpressionWrapper(
            F("price") * F("quantity"),
            output_field=DecimalField(
                max_digits=14,
                decimal_places=2,
            ),
        )

        total_sales = (
            OrderItem.objects
            .filter(
                product__shop=shop
            )
            .exclude(
                order__status="cancelled"
            )
            .aggregate(
                total=Sum(sales_expression)
            )["total"]
            or Decimal("0.00")
        )

        total_sales = Decimal(
            total_sales
        ).quantize(
            Decimal("0.01")
        )

        commission = (
            total_sales * Decimal("0.10")
        ).quantize(
            Decimal("0.01")
        )

        return Response({
            "id": shop.id,
            "name": shop.name,
            "description": shop.description,
            "phone": shop.phone,
            "address": shop.address,
            "logo": (
                request.build_absolute_uri(
                    shop.logo.url
                )
                if shop.logo
                else None
            ),
            "is_active": shop.is_active,
            "created_at": shop.created_at,
            "updated_at": shop.updated_at,

            "owner": {
                "id": shop.owner.id,
                "username": shop.owner.username,
                "email": shop.owner.email,
                "phone": shop.owner.phone,
                "is_active": shop.owner.is_active,
            },

            "products_count": products.count(),

            "available_products": products.filter(
                is_available=True
            ).count(),

            "orders_count": orders.count(),

            "total_sales": str(total_sales),

            "commission": str(commission),
        })


class AdminShopStatusView(APIView):
    """
    PATCH /api/admin/shops/<id>/status/

    Activate or deactivate a shop.
    """

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def patch(self, request, pk):

        try:
            shop = Shop.objects.get(pk=pk)
        except Shop.DoesNotExist:
            return Response(
                {"detail": "Shop not found."},
                status=404,
            )

        is_active = request.data.get("is_active")

        if not isinstance(is_active, bool):
            return Response(
                {
                    "is_active":
                        "This field must be true or false."
                },
                status=400,
            )

        shop.is_active = is_active
        shop.save(update_fields=["is_active"])

        return Response({
            "message": (
                "Shop activated successfully."
                if is_active
                else
                "Shop deactivated successfully."
            ),
            "shop": {
                "id": shop.id,
                "name": shop.name,
                "is_active": shop.is_active,
            },
        })


class AdminShopProductsView(APIView):
    """
    GET /api/admin/shops/<id>/products/
    """

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request, pk):

        try:
            shop = Shop.objects.get(pk=pk)
        except Shop.DoesNotExist:
            return Response(
                {"detail": "Shop not found."},
                status=404,
            )

        products = Product.objects.filter(
            shop=shop
        ).order_by("-created_at")

        data = []

        for product in products:

            data.append({
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": str(product.price),
                "quantity": product.quantity,
                "category": product.category,

                "image": (
                    request.build_absolute_uri(
                        product.image.url
                    )
                    if product.image
                    else None
                ),

                "video": (
                    request.build_absolute_uri(
                        product.video.url
                    )
                    if product.video
                    else None
                ),

                "is_available": product.is_available,
                "views": product.views,
                "likes": product.likes,
                "created_at": product.created_at,
                "updated_at": product.updated_at,
            })

        return Response({
            "shop": {
                "id": shop.id,
                "name": shop.name,
            },
            "count": len(data),
            "products": data,
        })


class AdminShopOrdersView(APIView):
    """
    GET /api/admin/shops/<id>/orders/

    Returns orders containing products
    belonging to this shop.
    """

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request, pk):

        try:
            shop = Shop.objects.get(pk=pk)
        except Shop.DoesNotExist:
            return Response(
                {"detail": "Shop not found."},
                status=404,
            )

        orders = (
            Order.objects
            .filter(
                items__product__shop=shop
            )
            .prefetch_related(
                "items__product"
            )
            .distinct()
            .order_by("-created_at")
        )

        data = []

        for order in orders:

            items = []

            for item in order.items.all():

                if item.product.shop_id != shop.id:
                    continue

                items.append({
                    "product_id": item.product.id,
                    "product_name": item.product.name,
                    "quantity": item.quantity,
                    "price": str(item.price),
                    "total_price": str(
                        item.total_price
                    ),
                })

            if not items:
                continue

            data.append({
                "id": order.id,
                "customer": {
                    "id": order.customer.id,
                    "username": order.customer.username,
                    "email": order.customer.email,
                },
                "full_name": order.full_name,
                "phone": order.phone,
                "address": order.address,
                "payment_method": order.payment_method,
                "status": order.status,
                "delivery_status": order.delivery_status,
                "total_amount": str(order.total_amount),
                "created_at": order.created_at,
                "items": items,
            })

        return Response({
            "shop": {
                "id": shop.id,
                "name": shop.name,
            },
            "count": len(data),
            "orders": data,
        })

        # ================================================================
# SHOP OWNERS
# ================================================================

class AdminShopOwnersView(APIView):
    """
    GET /api/admin/shop-owners/

    Returns all shop owners and their shops.
    """

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request):

        owners = (
            User.objects
            .filter(role="shop_owner")
            .prefetch_related("shop")
            .order_by("-date_joined")
        )

        data = []

        for owner in owners:

            shop = getattr(owner, "shop", None)

            if shop:
                products = Product.objects.filter(
                    shop=shop
                )

                shop_data = {
                    "id": shop.id,
                    "name": shop.name,
                    "is_active": shop.is_active,
                    "products_count": products.count(),
                    "available_products": products.filter(
                        is_available=True
                    ).count(),
                }
            else:
                shop_data = None

            data.append({
                "id": owner.id,
                "username": owner.username,
                "email": owner.email,
                "phone": owner.phone,
                "is_active": owner.is_active,
                "date_joined": owner.date_joined,
                "shop": shop_data,
            })

        return Response({
            "count": len(data),
            "shop_owners": data,
        })


# ================================================================
# CREATE SHOP OWNER
# ================================================================

class AdminCreateShopOwnerView(APIView):
    """
    POST /api/admin/shop-owners/create/

    Admin creates:
    - Shop owner account
    - Shop belonging to that owner
    """

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def post(self, request):

        username = str(
            request.data.get("username", "")
        ).strip()

        email = str(
            request.data.get("email", "")
        ).strip()

        password = str(
            request.data.get("password", "")
        )

        phone = str(
            request.data.get("phone", "")
        ).strip()

        shop_name = str(
            request.data.get("shop_name", "")
        ).strip()

        shop_description = str(
            request.data.get("shop_description", "")
        ).strip()

        shop_phone = str(
            request.data.get("shop_phone", "")
        ).strip()

        shop_address = str(
            request.data.get("shop_address", "")
        ).strip()

        # --------------------------------------------------------
        # VALIDATION
        # --------------------------------------------------------

        if not username:
            return Response(
                {"detail": "Username is required."},
                status=400,
            )

        if not email:
            return Response(
                {"detail": "Email is required."},
                status=400,
            )

        if not password:
            return Response(
                {"detail": "Password is required."},
                status=400,
            )

        if len(password) < 6:
            return Response(
                {
                    "detail":
                        "Password must be at least 6 characters."
                },
                status=400,
            )

        if not shop_name:
            return Response(
                {"detail": "Shop name is required."},
                status=400,
            )

        # --------------------------------------------------------
        # DUPLICATE CHECKS
        # --------------------------------------------------------

        if User.objects.filter(
            username__iexact=username
        ).exists():
            return Response(
                {
                    "detail":
                        "This username is already registered."
                },
                status=400,
            )

        if User.objects.filter(
            email__iexact=email
        ).exists():
            return Response(
                {
                    "detail":
                        "This email is already registered."
                },
                status=400,
            )

        # --------------------------------------------------------
        # CREATE OWNER + SHOP
        # --------------------------------------------------------

        try:
            from django.db import transaction

            with transaction.atomic():

                owner = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    role=User.Role.SHOP_OWNER,
                    phone=phone,
                )

                shop = Shop.objects.create(
                    owner=owner,
                    name=shop_name,
                    description=shop_description,
                    phone=shop_phone,
                    address=shop_address,
                    is_active=True,
                )

        except Exception as exc:

            return Response(
                {
                    "detail":
                        f"Unable to create shop owner: {exc}"
                },
                status=400,
            )

        # --------------------------------------------------------
        # RESPONSE
        # --------------------------------------------------------

        return Response(
            {
                "message":
                    "Shop owner created successfully.",
                "shop_owner": {
                    "id": owner.id,
                    "username": owner.username,
                    "email": owner.email,
                    "phone": owner.phone,
                    "role": owner.role,
                    "is_active": owner.is_active,
                },
                "shop": {
                    "id": shop.id,
                    "name": shop.name,
                    "description": shop.description,
                    "phone": shop.phone,
                    "address": shop.address,
                    "is_active": shop.is_active,
                },
            },
            status=201,
        )

class AdminShopOwnerDetailView(APIView):
    """
    GET /api/admin/shop-owners/<id>/

    Returns detailed information about one shop owner.
    """

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request, pk):

        try:
            owner = (
                User.objects
                .filter(role="shop_owner")
                .prefetch_related("shop")
                .get(pk=pk)
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Shop owner not found."},
                status=404,
            )

        shop = getattr(owner, "shop", None)

        if shop:

            products = Product.objects.filter(
                shop=shop
            )

            orders = (
                Order.objects
                .filter(
                    items__product__shop=shop
                )
                .distinct()
            )

            sales_expression = ExpressionWrapper(
                F("price") * F("quantity"),
                output_field=DecimalField(
                    max_digits=14,
                    decimal_places=2,
                ),
            )

            total_sales = (
                OrderItem.objects
                .filter(product__shop=shop)
                .exclude(order__status="cancelled")
                .aggregate(
                    total=Sum(sales_expression)
                )["total"]
                or Decimal("0.00")
            )

            total_sales = Decimal(
                total_sales
            ).quantize(
                Decimal("0.01")
            )

            commission = (
                total_sales * Decimal("0.10")
            ).quantize(
                Decimal("0.01")
            )

            shop_data = {
                "id": shop.id,
                "name": shop.name,
                "description": shop.description,
                "phone": shop.phone,
                "address": shop.address,
                "logo": (
                    request.build_absolute_uri(
                        shop.logo.url
                    )
                    if shop.logo
                    else None
                ),
                "is_active": shop.is_active,
                "products_count": products.count(),
                "available_products": products.filter(
                    is_available=True
                ).count(),
                "orders_count": orders.count(),
                "total_sales": str(total_sales),
                "commission": str(commission),
            }

        else:
            shop_data = None

        return Response({
            "id": owner.id,
            "username": owner.username,
            "email": owner.email,
            "phone": owner.phone,
            "is_active": owner.is_active,
            "date_joined": owner.date_joined,
            "shop": shop_data,
        })


class AdminShopOwnerStatusView(APIView):
    """
    PATCH /api/admin/shop-owners/<id>/status/

    Activate or deactivate a shop owner's account.
    """

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def patch(self, request, pk):

        try:
            owner = User.objects.get(
                pk=pk,
                role="shop_owner",
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Shop owner not found."},
                status=404,
            )

        is_active = request.data.get("is_active")

        if not isinstance(is_active, bool):
            return Response(
                {
                    "is_active":
                        "This field must be true or false."
                },
                status=400,
            )

        owner.is_active = is_active
        owner.save(update_fields=["is_active"])

        return Response({
            "message": (
                "Shop owner activated successfully."
                if is_active
                else
                "Shop owner deactivated successfully."
            ),
            "shop_owner": {
                "id": owner.id,
                "username": owner.username,
                "is_active": owner.is_active,
            },
        })


class AdminShopOwnerProductsView(APIView):
    """
    GET /api/admin/shop-owners/<id>/products/
    """

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request, pk):

        try:
            owner = User.objects.get(
                pk=pk,
                role="shop_owner",
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Shop owner not found."},
                status=404,
            )

        shop = getattr(owner, "shop", None)

        if not shop:
            return Response({
                "shop_owner": {
                    "id": owner.id,
                    "username": owner.username,
                },
                "count": 0,
                "products": [],
            })

        products = (
            Product.objects
            .filter(shop=shop)
            .order_by("-created_at")
        )

        data = []

        for product in products:

            data.append({
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": str(product.price),
                "quantity": product.quantity,
                "category": product.category,
                "image": (
                    request.build_absolute_uri(
                        product.image.url
                    )
                    if product.image
                    else None
                ),
                "video": (
                    request.build_absolute_uri(
                        product.video.url
                    )
                    if product.video
                    else None
                ),
                "is_available": product.is_available,
                "views": product.views,
                "likes": product.likes,
                "created_at": product.created_at,
                "updated_at": product.updated_at,
            })

        return Response({
            "shop_owner": {
                "id": owner.id,
                "username": owner.username,
            },
            "shop": {
                "id": shop.id,
                "name": shop.name,
            },
            "count": len(data),
            "products": data,
        })


class AdminShopOwnerOrdersView(APIView):
    """
    GET /api/admin/shop-owners/<id>/orders/
    """

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request, pk):

        try:
            owner = User.objects.get(
                pk=pk,
                role="shop_owner",
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Shop owner not found."},
                status=404,
            )

        shop = getattr(owner, "shop", None)

        if not shop:
            return Response({
                "shop_owner": {
                    "id": owner.id,
                    "username": owner.username,
                },
                "count": 0,
                "orders": [],
            })

        orders = (
            Order.objects
            .filter(
                items__product__shop=shop
            )
            .prefetch_related(
                "items__product"
            )
            .distinct()
            .order_by("-created_at")
        )

        data = []

        for order in orders:

            items = []

            for item in order.items.all():

                if item.product.shop_id != shop.id:
                    continue

                items.append({
                    "product_id": item.product.id,
                    "product_name": item.product.name,
                    "quantity": item.quantity,
                    "price": str(item.price),
                    "total_price": str(
                        item.total_price
                    ),
                })

            if not items:
                continue

            data.append({
                "id": order.id,
                "customer": {
                    "id": order.customer.id,
                    "username": order.customer.username,
                    "email": order.customer.email,
                },
                "full_name": order.full_name,
                "phone": order.phone,
                "address": order.address,
                "payment_method": order.payment_method,
                "status": order.status,
                "delivery_status": order.delivery_status,
                "total_amount": str(order.total_amount),
                "created_at": order.created_at,
                "items": items,
            })

        return Response({
            "shop_owner": {
                "id": owner.id,
                "username": owner.username,
            },
            "shop": {
                "id": shop.id,
                "name": shop.name,
            },
            "count": len(data),
            "orders": data,
        })