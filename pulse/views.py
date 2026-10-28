
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
import random
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Count, Q
from rest_framework.permissions import IsAuthenticated

from .models import PriceAlert, NotificationLog
from .permissions import IsAdminUser
from .serializers import RegisterSerializer
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from .models import PriceAlert
from .serializers import PriceAlertSerializer


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()
        access_token = RefreshToken.for_user(user).access_token

        return Response(
            {
                "username": user.username,
                "access": str(access_token),
                "role": user.profile.role,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access_token = RefreshToken.for_user(user).access_token

        return Response(
            {
                "username": user.username,
                "access": str(access_token),
                "role": user.profile.role,
            },
            status=status.HTTP_200_OK,
        )


class PriceAlertListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        alerts = PriceAlert.objects.filter(
            user=request.user
        ).order_by("-created_at")

        serializer = PriceAlertSerializer(alerts, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = PriceAlertSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class PriceAlertDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, alert_id):
        alert = get_object_or_404(
            PriceAlert,
            id=alert_id,
        )

        if alert.user != request.user:
            return Response(
                {"detail": "Not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        alert.status = PriceAlert.Status.INACTIVE
        alert.save(update_fields=["status"])

        return Response(
            {"status": "inactive"},
            status=status.HTTP_200_OK,
        )

MOCK_PRICES = {
    "DEL-BOM": (3000, 7000),
    "BLR-HYD": (1500, 4000),
    "DEL-BLR": (4000, 9000),
    "BOM-GOA": (2000, 5000),
}


@require_GET
def get_flight_price(request):
    route = request.GET.get("route", "").upper()
    price_range = MOCK_PRICES.get(route)

    if not price_range:
        return JsonResponse(
            {"error": "Route not found"},
            status=404,
        )

    price = random.randint(*price_range)

    return JsonResponse({
        "route": route,
        "price": price,
    })


class AdminSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        alert_stats = PriceAlert.objects.aggregate(
            total_alerts=Count("id"),
            active_alerts=Count(
                "id",
                filter=Q(status=PriceAlert.Status.ACTIVE),
            ),
            triggered_alerts=Count(
                "id",
                filter=Q(status=PriceAlert.Status.TRIGGERED),
            ),
        )

        notification_stats = NotificationLog.objects.aggregate(
            total_notifications=Count("id"),
        )

        top_routes = (
            PriceAlert.objects
            .values("origin", "destination")
            .annotate(alert_count=Count("id"))
            .order_by("-alert_count", "origin", "destination")[:5]
        )

        return Response({
            **alert_stats,
            **notification_stats,
            "top_routes": [
                {
                    "route": f"{route['origin']}-{route['destination']}",
                    "alert_count": route["alert_count"],
                }
                for route in top_routes
            ],
        })


