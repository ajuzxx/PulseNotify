
import logging
from decimal import Decimal

import requests
from celery import shared_task
from django.conf import settings

from .models import PriceAlert, NotificationLog

logger = logging.getLogger(__name__)


@shared_task
def check_prices():
    active_alerts = PriceAlert.objects.filter(
        status=PriceAlert.Status.ACTIVE
    )

    routes = active_alerts.values_list(
        "origin", "destination"
    ).distinct()

    for origin, destination in routes:
        route = f"{origin}-{destination}"

        try:
            response = requests.get(
                f"{settings.FLIGHT_PRICE_API_URL}",
                params={"route": route},
                timeout=10,
            )
            response.raise_for_status()
            current_price = Decimal(str(response.json()["price"]))

        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.warning("Could not fetch price for %s: %s", route, exc)
            continue

        route_alerts = active_alerts.filter(
            origin=origin,
            destination=destination,
        )

        for alert in route_alerts:
            if current_price <= alert.threshold_price:
                send_notification.delay(alert.id, str(current_price))


@shared_task
def send_notification(alert_id, triggered_price):
    try:
        alert = PriceAlert.objects.get(
            id=alert_id,
            status=PriceAlert.Status.ACTIVE,
        )
    except PriceAlert.DoesNotExist:
        return "Alert no longer active"

    triggered_price = Decimal(str(triggered_price))

    message = (
        f"Price alert triggered! {alert.origin}-{alert.destination} "
        f"is now ₹{triggered_price} — below your threshold of "
        f"₹{alert.threshold_price}"
    )

    NotificationLog.objects.create(
        alert=alert,
        triggered_price=triggered_price,
        message=message,
    )

    alert.status = PriceAlert.Status.TRIGGERED
    alert.save(update_fields=["status"])

    return "Notification logged"
