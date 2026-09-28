from django.db.models import Q
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Rent, RentBooking, RentImage
from .serializers import RentBookingSerializer, RentSerializer
from .services import (
    cancel_rent_booking,
    cancel_rent_booking_by_owner,
    complete_rent_booking,
    confirm_rent_booking,
    create_rent_booking,
    initialize_paystack_rent_payment,
    reject_rent_booking,
    verify_paystack_rent_payment,
    verify_paystack_rent_refund,
)


class VerifyPaystackRentRefundView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = (
                RentBooking.objects
                .select_related("customer", "rent")
                .get(
                    pk=pk,
                    customer=request.user,
                )
            )
        except RentBooking.DoesNotExist:
            return Response(
                {"detail": "Rental booking not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = verify_paystack_rent_refund(
                booking=booking,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.refresh_from_db()

        return Response(
            {
                "message": (
                    "Rental Paystack refund status checked."
                ),
                "refund": result,
                "booking": RentBookingSerializer(
                    booking,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class RentListCreateView(generics.ListCreateAPIView):
    serializer_class = RentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return Rent.objects.select_related("owner").all()

    def perform_create(self, serializer):
        if getattr(self.request.user, "role", None) != "customer":
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Only customers can create rental listings."
            )

        images = self.request.FILES.getlist("images")
        video = self.request.FILES.get("video")

        if images and video:
            raise ValidationError(
                {
                    "media": (
                        "A rent can contain multiple pictures OR one video, "
                        "not pictures and video together."
                    )
                }
            )

        if video and len(self.request.FILES.getlist("video")) > 1:
            raise ValidationError(
                {"video": "Only one video is allowed for a rent."}
            )

        rent = serializer.save(
            owner=self.request.user,
            video=video if video else None,
        )

        if images:
            RentImage.objects.bulk_create(
                [
                    RentImage(rent=rent, image=image)
                    for image in images
                ]
            )


class RentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return Rent.objects.select_related("owner").all()

    def _check_owner(self, request, rent):
        if rent.owner_id != request.user.id:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Only the rental owner can modify this rental."
            )

    def perform_update(self, serializer):
        rent = self.get_object()
        self._check_owner(self.request, rent)
        serializer.save()

    def perform_destroy(self, instance):
        self._check_owner(self.request, instance)

        if instance.bookings.exists():
            raise ValidationError(
                {
                    "detail": (
                        "This rent cannot be deleted because it has "
                        "existing bookings."
                    )
                }
            )

        instance.delete()


class RentBookView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        payment_method = request.data.get(
            "payment_method",
            RentBooking.PAYMENT_WALLET,
        )

        try:
            booking = create_rent_booking(
                rent_id=pk,
                customer=request.user,
                payment_method=payment_method,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RentBookingSerializer(
            booking,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )


class InitializePaystackRentPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            payment = initialize_paystack_rent_payment(
                booking_id=pk,
                customer=request.user,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": (
                    "Paystack rental payment initialized."
                ),
                "booking_id": pk,
                "payment": payment,
            },
            status=status.HTTP_200_OK,
        )


class VerifyPaystackRentPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = verify_paystack_rent_payment(
                booking_id=pk,
                customer=request.user,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RentBookingSerializer(
            booking,
            context={"request": request},
        )

        if booking.payment_status == RentBooking.PAYMENT_PAID:
            message = "Rental payment successful."
        elif booking.payment_status == RentBooking.PAYMENT_FAILED:
            message = "Rental payment failed."
        elif booking.payment_status == RentBooking.PAYMENT_PENDING:
            message = "Rental payment is still pending."
        else:
            message = "Rental payment verification completed."

        return Response(
            {
                "message": message,
                "booking": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class MyRentBookingsView(generics.ListAPIView):
    serializer_class = RentBookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            RentBooking.objects
            .select_related("rent", "rent__owner", "customer")
            .filter(customer=self.request.user)
        )


class OwnerRentBookingsView(generics.ListAPIView):
    serializer_class = RentBookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            RentBooking.objects
            .select_related("rent", "rent__owner", "customer")
            .filter(rent__owner=self.request.user)
        )


class ConfirmRentBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = confirm_rent_booking(
                booking_id=pk,
                owner=request.user,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            RentBookingSerializer(
                booking,
                context={"request": request},
            ).data
        )


class RejectRentBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = reject_rent_booking(
                booking_id=pk,
                owner=request.user,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            RentBookingSerializer(
                booking,
                context={"request": request},
            ).data
        )


class OwnerCancelRentBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = cancel_rent_booking_by_owner(
                booking_id=pk,
                owner=request.user,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            RentBookingSerializer(
                booking,
                context={"request": request},
            ).data
        )


class CustomerConfirmRentBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = complete_rent_booking(
                booking_id=pk,
                customer=request.user,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            RentBookingSerializer(
                booking,
                context={"request": request},
            ).data
        )


class CustomerCancelRentBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = cancel_rent_booking(
                booking_id=pk,
                customer=request.user,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            RentBookingSerializer(
                booking,
                context={"request": request},
            ).data
        )
