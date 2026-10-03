import json
import unittest
from unittest.mock import patch

with patch("feature_flag_service.FeatureFlagService"):
    import server


class VoucherQueryTest(unittest.TestCase):
    def setUp(self):
        self.handler = server.GetVoucherHandler.__new__(server.GetVoucherHandler)
        self.connection_patch = patch.object(server.pymysql, "connect")
        self.connect = self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)
        self.connection = self.connect.return_value
        self.cursor = self.connection.cursor.return_value

    def test_disabled_flag_returns_the_existing_voucher(self):
        server.feature_flag_service.is_enabled.return_value = False
        self.cursor.rowcount = 1
        self.cursor.fetchone.return_value = (
            1,
            "order-1",
            "2026-10-03",
            "10:00",
            "Alice",
            "G1234",
            1,
            "4A",
            "Shanghai",
            "Beijing",
            50.0,
        )

        voucher = json.loads(self.handler.fetchVoucherByOrderId("order-1"))

        self.cursor.execute.assert_called_once_with("SELECT * FROM voucher where order_id = %s", ("order-1",))
        self.assertEqual(voucher["order_id"], "order-1")
        self.connection.close.assert_called_once()

    def test_enabled_flag_executes_the_malformed_nested_query(self):
        server.feature_flag_service.is_enabled.return_value = True
        self.cursor.execute.side_effect = server.pymysql.err.OperationalError(
            1248, "Every derived table must have its own alias"
        )

        with self.assertRaises(server.pymysql.err.OperationalError):
            self.handler.fetchVoucherByOrderId("order-1")

        self.cursor.execute.assert_called_once_with(
            "SELECT * FROM (SELECT * FROM voucher where order_id = %s)",
            ("order-1",),
        )
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    def test_missing_voucher_keeps_the_cache_miss_behavior(self):
        server.feature_flag_service.is_enabled.return_value = False
        self.cursor.rowcount = 0
        self.cursor.fetchone.return_value = None

        self.assertIsNone(self.handler.fetchVoucherByOrderId("missing-order"))
        self.connection.close.assert_called_once()

    def test_cursor_failure_still_closes_the_connection(self):
        server.feature_flag_service.is_enabled.return_value = False
        self.connection.cursor.side_effect = RuntimeError("connection lost")

        with self.assertRaises(RuntimeError):
            self.handler.fetchVoucherByOrderId("order-1")

        self.connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
