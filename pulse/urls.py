
from django.urls import path
from .views import get_flight_price
from .views import AdminSummaryView
from .views import (
    RegisterView,
    LoginView,
    PriceAlertListCreateView,
    PriceAlertDeactivateView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),

    path("alerts/", PriceAlertListCreateView.as_view(), name="alerts"),
    path(
        "alerts/<int:alert_id>/",
        PriceAlertDeactivateView.as_view(),
        name="alert-deactivate",
    ),
    path("flights/price/", get_flight_price, name="flight-price"),
    path(
    "admin/summary/",
    AdminSummaryView.as_view(),
    name="admin-summary",
),
]
