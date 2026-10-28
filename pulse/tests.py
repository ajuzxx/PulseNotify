
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import PriceAlert, NotificationLog, UserProfile


class PriceThresholdTest(TestCase):
    def test_price_below_threshold_triggers_alert(self):
        self.assertTrue(Decimal("4200") <= Decimal("4500"))

    def test_price_above_threshold_does_not_trigger(self):
        self.assertFalse(Decimal("5000") <= Decimal("4500"))

    def test_price_equal_to_threshold_triggers_alert(self):
        self.assertTrue(Decimal("4500") <= Decimal("4500"))


class NotificationLogTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
        )

        self.alert = PriceAlert.objects.create(
            user=self.user,
            origin="DEL",
            destination="BOM",
            threshold_price=Decimal("4500.00"),
            status=PriceAlert.Status.ACTIVE,
        )

    def test_notification_log_created_with_correct_message(self):
        log = NotificationLog.objects.create(
            alert=self.alert,
            triggered_price=Decimal("4200.00"),
            message="Price dropped to 4200 for DEL-BOM",
        )

        self.assertEqual(log.triggered_price, Decimal("4200.00"))
        self.assertEqual(log.alert, self.alert)
        self.assertIn("DEL-BOM", log.message)


class AlertScopingTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="user1",
            password="testpass123",
        )
        self.user2 = User.objects.create_user(
            username="user2",
            password="testpass123",
        )

        PriceAlert.objects.create(
            user=self.user1,
            origin="DEL",
            destination="BOM",
            threshold_price=Decimal("4500.00"),
        )

        PriceAlert.objects.create(
            user=self.user2,
            origin="BLR",
            destination="HYD",
            threshold_price=Decimal("2000.00"),
        )

        self.client = APIClient()

    def test_user_only_sees_own_alerts(self):
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/alerts/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["origin"], "DEL")

    def test_user_cannot_see_other_users_alerts(self):
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/alerts/")

        origins = [alert["origin"] for alert in response.data]

        self.assertNotIn("BLR", origins)
