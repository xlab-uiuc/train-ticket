import requests
import os
import subprocess
from datetime import date, timedelta

# Use today's date for all travel queries (travel-service rejects past dates)
TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def _discover_gateway():
    """Auto-discover gateway URL from k8s NodePort service."""
    env = os.environ.get("GATEWAY_URL")
    if env:
        return env.rstrip("/")
    try:
        ns = os.environ.get("NAMESPACE", "train-ticket")
        node_port = (
            subprocess.check_output(
                [
                    "kubectl",
                    "get",
                    "svc",
                    "ts-gateway-service",
                    "-n",
                    ns,
                    "-o",
                    "jsonpath={.spec.ports[0].nodePort}",
                ],
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
            .decode()
            .strip()
        )
        node_ip = (
            subprocess.check_output(
                [
                    "kubectl",
                    "get",
                    "nodes",
                    "-o",
                    'jsonpath={.items[0].status.addresses[?(@.type=="InternalIP")].address}',
                ],
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
            .decode()
            .strip()
        )
        if node_port and node_ip:
            return f"http://{node_ip}:{node_port}"
    except Exception:
        pass
    raise RuntimeError(
        "Cannot discover gateway. Set GATEWAY_URL env var or ensure kubectl is configured."
    )


GW = _discover_gateway()
TIMEOUT = 30
TIMEOUT_LONG = 60

passed = 0
failed = 0
errors = []


def result(label, http_code, ok, detail=""):
    global passed, failed
    tag = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
        errors.append(label)
    msg = f"[{tag}] {label} (HTTP {http_code})"
    if detail:
        msg += f" {detail}"
    print(msg)


def parse_response(label, r):
    """Parse response, handling JSON objects, bare values (bool/string), and non-JSON."""
    ok_status = r.status_code in (200, 201)
    try:
        d = r.json()
    except ValueError:
        result(label, r.status_code, ok_status, f"body={r.text[:100]}")
        return r
    if isinstance(d, (bool, int, float)):
        result(label, r.status_code, ok_status, f"data={d}")
        return r
    if isinstance(d, str):
        result(label, r.status_code, ok_status, f"data={d[:80]}")
        return r
    if isinstance(d, list):
        result(label, r.status_code, ok_status, f"items={len(d)}")
        return r
    s = d.get("status", "?")
    data = d.get("data")
    if isinstance(data, list):
        result(label, r.status_code, ok_status, f"status={s} items={len(data)}")
    elif isinstance(data, dict):
        result(
            label, r.status_code, ok_status, f"status={s} keys={list(data.keys())[:5]}"
        )
    elif data is not None:
        result(label, r.status_code, ok_status, f"status={s} data={str(data)[:80]}")
    else:
        result(
            label, r.status_code, ok_status, f"status={s} msg={d.get('msg', '')[:80]}"
        )
    return r


def _req(method, path, token, label, body=None, timeout=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        r = requests.request(
            method,
            f"{GW}{path}",
            headers=headers,
            json=body,
            timeout=timeout or TIMEOUT,
        )
        return parse_response(label, r)
    except Exception as e:
        result(label, 0, False, str(e)[:100])
        return None


def get(path, token, label, timeout=None):
    return _req("GET", path, token, label, timeout=timeout)


def post(path, token, body, label, timeout=None):
    return _req("POST", path, token, label, body=body, timeout=timeout)


def put(path, token, body, label, timeout=None):
    return _req("PUT", path, token, label, body=body, timeout=timeout)


def delete(path, token, label, timeout=None):
    return _req("DELETE", path, token, label, timeout=timeout)


def patch(path, token, label, timeout=None):
    return _req("PATCH", path, token, label, timeout=timeout)


def get_raw(path, label, timeout=None):
    """GET without auth, returns raw response."""
    try:
        r = requests.get(f"{GW}{path}", timeout=timeout or TIMEOUT)
        return r
    except Exception as e:
        result(label, 0, False, str(e)[:100])
        return None


# ============================================================
# Test data (from existing DB state)
# ============================================================
USER_ID = "4d2a46c7-71cb-4cf1-b5bb-b68406d9da6f"
CONTACT_ID_1 = "9faa8e1c-0cfb-45bc-ad87-1c39cfd8c0f1"  # Contacts_One
CONTACT_ID_2 = "8e07a16d-8bd0-41b1-86c8-97b05440317e"  # Contacts_Two
ORDER_ID = (
    "446dec65-3ae7-42f1-981c-16aa433ecdef"  # status=0, G1237, nanjing->shanghaihongqiao
)
ORDER_ID_2 = (
    "3da59d0b-2897-490b-bf50-cbc932860a8a"  # status=0, G1234, shanghai->beijing
)
ORDER_OTHER_ID = (
    "68ea1421-8982-4963-8211-4cd148ad3259"  # status=1, K1235, shanghai->taiyuan
)
STATION_ID_SHANGHAI = "974a0ec1-93bd-45d1-b96d-01c40d1086f2"
ROUTE_ID = (
    "0b23bd3e-876a-4af3-b920-c50a90c90b04"  # shanghai->nanjing->shijiazhuang->taiyuan
)

NOTIFY_INFO = {
    "id": "",
    "sendStatus": False,
    "email": "test@test.com",
    "orderNumber": ORDER_ID,
    "username": "fdse_microservice",
    "startPlace": "shanghai",
    "endPlace": "beijing",
    "startTime": "08:00",
    "date": TODAY,
    "seatClass": "2",
    "seatNumber": "1A",
    "price": "100",
}

ORDER_QUERY = {
    "loginId": USER_ID,
    "enableStateQuery": False,
    "enableTravelDateQuery": False,
    "enableBoughtDateQuery": False,
    "travelDateStart": "",
    "travelDateEnd": "",
    "boughtDateStart": "",
    "boughtDateEnd": "",
    "state": 0,
}


def main():
    print("=" * 70)
    print("Train Ticket API Check")
    print("=" * 70)
    print()

    # === LOGIN (regular user) ===
    r = requests.post(
        f"{GW}/api/v1/users/login",
        json={
            "username": "fdse_microservice",
            "password": "111111",
            "verificationCode": "1234",
        },
        timeout=TIMEOUT,
    )
    d = r.json()
    token = d["data"]["token"]
    result(
        "login (user)", r.status_code, d["status"] == 1, f"userId={d['data']['userId']}"
    )

    # === LOGIN (admin) ===
    r = requests.post(
        f"{GW}/api/v1/users/login",
        json={"username": "admin", "password": "222222", "verificationCode": "1234"},
        timeout=TIMEOUT,
    )
    d = r.json()
    admin_token = d["data"]["token"]
    result(
        "login (admin)",
        r.status_code,
        d["status"] == 1,
        f"userId={d['data']['userId']}",
    )
    print()

    # =================================================================
    # 1. ts-admin-basic-info-service (21 endpoints)
    # =================================================================
    print("--- ts-admin-basic-info-service (21 endpoints) ---")
    get("/api/v1/adminbasicservice/welcome", admin_token, "admin-basic: welcome")
    get(
        "/api/v1/adminbasicservice/adminbasic/contacts",
        admin_token,
        "admin-basic: GET contacts",
    )
    get(
        "/api/v1/adminbasicservice/adminbasic/stations",
        admin_token,
        "admin-basic: GET stations",
    )
    get(
        "/api/v1/adminbasicservice/adminbasic/trains",
        admin_token,
        "admin-basic: GET trains",
    )
    get(
        "/api/v1/adminbasicservice/adminbasic/configs",
        admin_token,
        "admin-basic: GET configs",
    )
    get(
        "/api/v1/adminbasicservice/adminbasic/prices",
        admin_token,
        "admin-basic: GET prices",
    )
    # POST/PUT/DELETE on admin-basic require ROLE_ADMIN
    post(
        "/api/v1/adminbasicservice/adminbasic/configs",
        admin_token,
        {"name": "TestConfig", "value": "42", "description": "test"},
        "admin-basic: POST config",
    )
    put(
        "/api/v1/adminbasicservice/adminbasic/configs",
        admin_token,
        {"name": "TestConfig", "value": "43", "description": "test updated"},
        "admin-basic: PUT config",
    )
    delete(
        "/api/v1/adminbasicservice/adminbasic/configs/TestConfig",
        admin_token,
        "admin-basic: DELETE config",
    )
    print()

    # =================================================================
    # 2. ts-admin-order-service (5 endpoints) - needs ROLE_ADMIN
    # =================================================================
    print("--- ts-admin-order-service (5 endpoints) ---")
    get("/api/v1/adminorderservice/welcome", admin_token, "admin-order: welcome")
    get("/api/v1/adminorderservice/adminorder", admin_token, "admin-order: GET all")
    print()

    # =================================================================
    # 3. ts-admin-route-service (4 endpoints) - needs ROLE_ADMIN
    # =================================================================
    print("--- ts-admin-route-service (4 endpoints) ---")
    get("/api/v1/adminrouteservice/welcome", admin_token, "admin-route: welcome")
    get("/api/v1/adminrouteservice/adminroute", admin_token, "admin-route: GET all")
    print()

    # =================================================================
    # 4. ts-admin-travel-service (5 endpoints) - needs ROLE_ADMIN
    # =================================================================
    print("--- ts-admin-travel-service (5 endpoints) ---")
    get("/api/v1/admintravelservice/welcome", admin_token, "admin-travel: welcome")
    get("/api/v1/admintravelservice/admintravel", admin_token, "admin-travel: GET all")
    print()

    # =================================================================
    # 5. ts-admin-user-service (5 endpoints) - needs ROLE_ADMIN
    # =================================================================
    print("--- ts-admin-user-service (5 endpoints) ---")
    get("/api/v1/adminuserservice/users/welcome", admin_token, "admin-user: welcome")
    get("/api/v1/adminuserservice/users", admin_token, "admin-user: GET all")
    print()

    # =================================================================
    # 6. ts-assurance-service (9 endpoints)
    # =================================================================
    print("--- ts-assurance-service (9 endpoints) ---")
    get("/api/v1/assuranceservice/welcome", token, "assurance: welcome")
    get("/api/v1/assuranceservice/assurances", token, "assurance: GET all")
    get("/api/v1/assuranceservice/assurances/types", token, "assurance: GET types")
    # Create assurance for an order
    get(
        f"/api/v1/assuranceservice/assurances/1/{ORDER_ID}",
        token,
        "assurance: create (type=1)",
    )
    get(
        f"/api/v1/assuranceservice/assurance/orderid/{ORDER_ID}",
        token,
        "assurance: GET by orderId",
    )
    # Get the assurance we just created to get its ID
    r = get(
        f"/api/v1/assuranceservice/assurance/orderid/{ORDER_ID}",
        token,
        "assurance: GET by orderId (for ID)",
    )
    assurance_id = ""
    if r and r.status_code == 200:
        try:
            ad = r.json().get("data")
            if ad:
                assurance_id = ad.get("id", "")
        except Exception:
            pass
    if assurance_id:
        get(
            f"/api/v1/assuranceservice/assurances/assuranceid/{assurance_id}",
            token,
            "assurance: GET by assuranceId",
        )
        patch(
            f"/api/v1/assuranceservice/assurances/{assurance_id}/{ORDER_ID}/1",
            token,
            "assurance: PATCH modify",
        )
        delete(
            f"/api/v1/assuranceservice/assurances/assuranceid/{assurance_id}",
            token,
            "assurance: DELETE by assuranceId",
        )
    else:
        print("  (skipping assurance ID-based tests, no assurance created)")
    delete(
        f"/api/v1/assuranceservice/assurances/orderid/{ORDER_ID_2}",
        token,
        "assurance: DELETE by orderId",
    )
    print()

    # =================================================================
    # 7. ts-auth-service (6 endpoints)
    # =================================================================
    print("--- ts-auth-service (6 endpoints) ---")
    get("/api/v1/auth/hello", token, "auth: hello")
    get("/api/v1/users/hello", token, "auth-user: hello")
    # login already tested above
    get("/api/v1/users", admin_token, "auth-user: GET all users")
    # POST /api/v1/auth and DELETE /api/v1/users/{id} skipped to avoid creating/deleting users
    print()

    # =================================================================
    # 8. ts-avatar-service (1 endpoint)
    # =================================================================
    print("--- ts-avatar-service (1 endpoint) ---")
    # Avatar service expects a base64-encoded image with a human face.
    import base64 as _b64
    import os as _os

    _avatar_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)), "..", "images", "avatar.png"
    )
    if _os.path.exists(_avatar_path):
        with open(_avatar_path, "rb") as f:
            _avatar_b64 = _b64.b64encode(f.read()).decode()
        post("/api/v1/avatar", token, {"img": _avatar_b64}, "avatar: POST")
    else:
        print("  (skipping avatar test, tests/avatar.png not found)")
    print()

    # =================================================================
    # 9. ts-basic-service (4 endpoints)
    # =================================================================
    print("--- ts-basic-service (4 endpoints) ---")
    get("/api/v1/basicservice/welcome", token, "basic: welcome")
    get("/api/v1/basicservice/basic/shanghai", token, "basic: GET stationId")
    post(
        "/api/v1/basicservice/basic/travel",
        token,
        {
            "trip": {
                "tripId": {"type": "D", "number": "1345"},
                "trainTypeName": "DongCheOne",
                "routeId": "unknown",
                "startStationName": "shanghai",
                "terminalStationName": "suzhou",
                "startTime": "08:00",
                "endTime": "10:00",
            },
            "startPlace": "shanghai",
            "endPlace": "suzhou",
            "departureTime": TODAY,
        },
        "basic: POST travel query",
        timeout=TIMEOUT_LONG,
    )
    post("/api/v1/basicservice/basic/travels", token, [], "basic: POST travels (empty)")
    print()

    # =================================================================
    # 10. ts-cancel-service (4 endpoints)
    # =================================================================
    print("--- ts-cancel-service (4 endpoints) ---")
    get("/api/v1/cancelservice/welcome", token, "cancel: welcome")
    get(
        f"/api/v1/cancelservice/cancel/refound/{ORDER_ID}",
        token,
        "cancel: refund calc",
        timeout=TIMEOUT_LONG,
    )
    get(
        f"/api/v1/cancelservice/cancel/{ORDER_OTHER_ID}/{USER_ID}",
        token,
        "cancel: cancel ticket",
        timeout=TIMEOUT_LONG,
    )
    get(
        "/api/v1/cancelservice/test/flag/fault_inject_cancel",
        token,
        "cancel: test flag",
    )
    print()

    # =================================================================
    # 11. ts-config-service (6 endpoints)
    # =================================================================
    print("--- ts-config-service (6 endpoints) ---")
    get("/api/v1/configservice/welcome", token, "config: welcome")
    get("/api/v1/configservice/configs", token, "config: GET all")
    get(
        "/api/v1/configservice/configs/DirectTicketAllocationProportion",
        token,
        "config: GET by name",
    )
    post(
        "/api/v1/configservice/configs",
        token,
        {"name": "TestCfg2", "value": "99", "description": "test"},
        "config: POST create",
    )
    put(
        "/api/v1/configservice/configs",
        token,
        {"name": "TestCfg2", "value": "100", "description": "updated"},
        "config: PUT update",
    )
    delete("/api/v1/configservice/configs/TestCfg2", token, "config: DELETE")
    print()

    # =================================================================
    # 12. ts-consign-price-service (5 endpoints)
    # =================================================================
    print("--- ts-consign-price-service (5 endpoints) ---")
    get("/api/v1/consignpriceservice/welcome", token, "consign-price: welcome")
    get(
        "/api/v1/consignpriceservice/consignprice/5.0/true",
        token,
        "consign-price: calc 5kg within",
    )
    get(
        "/api/v1/consignpriceservice/consignprice/10.0/false",
        token,
        "consign-price: calc 10kg beyond",
    )
    get(
        "/api/v1/consignpriceservice/consignprice/price",
        token,
        "consign-price: GET price info",
    )
    get(
        "/api/v1/consignpriceservice/consignprice/config",
        token,
        "consign-price: GET config",
    )
    # POST to modify config skipped to avoid changing pricing
    print()

    # =================================================================
    # 13. ts-consign-service (6 endpoints)
    # =================================================================
    print("--- ts-consign-service (6 endpoints) ---")
    get("/api/v1/consignservice/welcome", token, "consign: welcome")
    import uuid

    _consign_order_id = str(uuid.uuid4())  # unique per run to avoid NonUniqueResult
    post(
        "/api/v1/consignservice/consigns",
        token,
        {
            "id": "",
            "orderId": _consign_order_id,
            "accountId": USER_ID,
            "handleDate": TODAY,
            "targetDate": TOMORROW,
            "from": "shanghai",
            "to": "beijing",
            "consignee": "TestUser",
            "phone": "1234567890",
            "weight": 3.5,
            "isWithin": True,
        },
        "consign: POST insert",
        timeout=TIMEOUT_LONG,
    )
    get(
        f"/api/v1/consignservice/consigns/account/{USER_ID}",
        token,
        "consign: GET by account",
    )
    get(
        f"/api/v1/consignservice/consigns/order/{_consign_order_id}",
        token,
        "consign: GET by order",
    )
    get("/api/v1/consignservice/consigns/TestUser", token, "consign: GET by consignee")
    put(
        "/api/v1/consignservice/consigns",
        token,
        {
            "id": "",
            "orderId": _consign_order_id,
            "accountId": USER_ID,
            "handleDate": TODAY,
            "targetDate": TOMORROW,
            "from": "shanghai",
            "to": "beijing",
            "consignee": "TestUser",
            "phone": "1234567890",
            "weight": 4.0,
            "isWithin": True,
        },
        "consign: PUT update",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 14. ts-contacts-service (8 endpoints)
    # =================================================================
    print("--- ts-contacts-service (8 endpoints) ---")
    get("/api/v1/contactservice/contacts/welcome", token, "contacts: welcome")
    get("/api/v1/contactservice/contacts", token, "contacts: GET all")
    get(f"/api/v1/contactservice/contacts/{CONTACT_ID_1}", token, "contacts: GET by id")
    get(
        f"/api/v1/contactservice/contacts/account/{USER_ID}",
        token,
        "contacts: GET by account",
    )
    # POST create, PUT modify, DELETE - test with a temp contact
    post(
        "/api/v1/contactservice/contacts/admin",
        token,
        {
            "accountId": USER_ID,
            "name": "TempContact",
            "documentType": 1,
            "documentNumber": "TEMP001",
            "phoneNumber": "0000000000",
        },
        "contacts: POST admin create",
    )
    # Get the temp contact ID
    r = get(
        f"/api/v1/contactservice/contacts/account/{USER_ID}",
        token,
        "contacts: GET account (find temp)",
    )
    temp_contact_id = ""
    if r and r.status_code == 200:
        try:
            for c in r.json().get("data", []):
                if c.get("name") == "TempContact":
                    temp_contact_id = c["id"]
        except Exception:
            pass
    if temp_contact_id:
        put(
            "/api/v1/contactservice/contacts",
            token,
            {
                "id": temp_contact_id,
                "accountId": USER_ID,
                "name": "TempContactUpdated",
                "documentType": 1,
                "documentNumber": "TEMP001",
                "phoneNumber": "1111111111",
            },
            "contacts: PUT update",
        )
        delete(
            f"/api/v1/contactservice/contacts/{temp_contact_id}",
            token,
            "contacts: DELETE",
        )
    print()

    # =================================================================
    # 15. ts-delivery-service (0 endpoints - MQ only)
    # =================================================================
    print("--- ts-delivery-service (0 endpoints - RabbitMQ consumer only, skip) ---")
    print()

    # =================================================================
    # 16. ts-execute-service (3 endpoints)
    # =================================================================
    print("--- ts-execute-service (3 endpoints) ---")
    get("/api/v1/executeservice/welcome", token, "execute: welcome")
    get(
        f"/api/v1/executeservice/execute/collected/{ORDER_ID}",
        token,
        "execute: collect",
        timeout=TIMEOUT_LONG,
    )
    get(
        f"/api/v1/executeservice/execute/execute/{ORDER_ID}",
        token,
        "execute: execute",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 17. ts-food-delivery-service (9 endpoints)
    # =================================================================
    print("--- ts-food-delivery-service (9 endpoints) ---")
    get("/api/v1/fooddeliveryservice/welcome", token, "food-delivery: welcome")
    get("/api/v1/fooddeliveryservice/orders/all", token, "food-delivery: GET all")
    print()

    # =================================================================
    # 18. ts-food-service (9 endpoints)
    # =================================================================
    print("--- ts-food-service (9 endpoints) ---")
    get("/api/v1/foodservice/welcome", token, "food: welcome")
    get(
        "/api/v1/foodservice/test_send_delivery",
        token,
        "food: test_send_delivery",
        timeout=TIMEOUT_LONG,
    )
    get("/api/v1/foodservice/orders", token, "food: GET all orders")
    post(
        "/api/v1/foodservice/orders",
        token,
        {
            "id": "",
            "orderId": ORDER_ID,
            "foodType": 1,
            "stationName": "shanghai",
            "storeName": "TestStore",
            "foodName": "Noodles",
            "price": 5.0,
        },
        "food: POST create order",
        timeout=TIMEOUT_LONG,
    )
    get(f"/api/v1/foodservice/orders/{ORDER_ID}", token, "food: GET order by orderId")
    post("/api/v1/foodservice/createOrderBatch", token, [], "food: POST batch (empty)")
    put(
        "/api/v1/foodservice/orders",
        token,
        {
            "id": "",
            "orderId": ORDER_ID,
            "foodType": 1,
            "stationName": "shanghai",
            "storeName": "TestStore",
            "foodName": "Rice",
            "price": 6.0,
        },
        "food: PUT update order",
        timeout=TIMEOUT_LONG,
    )
    delete(f"/api/v1/foodservice/orders/{ORDER_ID}", token, "food: DELETE order")
    get(
        f"/api/v1/foodservice/foods/{TODAY}/shanghai/suzhou/D1345",
        token,
        "food: GET foods for trip",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 19. ts-gateway-service (0 endpoints - router only)
    # =================================================================
    print(
        "--- ts-gateway-service (0 endpoints - Spring Cloud Gateway router, skip) ---"
    )
    print()

    # =================================================================
    # 20. ts-inside-payment-service (9 endpoints)
    # =================================================================
    print("--- ts-inside-payment-service (9 endpoints) ---")
    get("/api/v1/inside_pay_service/welcome", token, "inside-pay: welcome")
    get(
        "/api/v1/inside_pay_service/inside_payment/account",
        token,
        "inside-pay: GET accounts",
    )
    get(
        "/api/v1/inside_pay_service/inside_payment/payment",
        token,
        "inside-pay: GET payments",
    )
    get(
        "/api/v1/inside_pay_service/inside_payment/money",
        token,
        "inside-pay: GET money records",
    )
    post(
        "/api/v1/inside_pay_service/inside_payment",
        token,
        {"userId": USER_ID, "orderId": ORDER_ID, "tripId": "G1237", "price": "0.01"},
        "inside-pay: POST pay",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/inside_pay_service/inside_payment/account",
        token,
        {"userId": USER_ID, "money": "0"},
        "inside-pay: POST create account",
    )
    get(
        f"/api/v1/inside_pay_service/inside_payment/{USER_ID}/1",
        token,
        "inside-pay: add money",
    )
    get(
        f"/api/v1/inside_pay_service/inside_payment/drawback/{USER_ID}/1",
        token,
        "inside-pay: drawback",
    )
    post(
        "/api/v1/inside_pay_service/inside_payment/difference",
        token,
        {"userId": USER_ID, "orderId": ORDER_ID, "tripId": "G1237", "price": "0.01"},
        "inside-pay: POST pay difference",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 21. ts-news-service (1 endpoint)
    # =================================================================
    print("--- ts-news-service (1 endpoint) ---")
    get("/api/v1/newsservice/", token, "news: GET /")
    print()

    # =================================================================
    # 22. ts-notification-service (7 endpoints)
    # =================================================================
    print("--- ts-notification-service (7 endpoints) ---")
    get("/api/v1/notifyservice/welcome", token, "notify: welcome")
    get(
        "/api/v1/notifyservice/test_send_mq",
        token,
        "notify: test_send_mq",
        timeout=TIMEOUT_LONG,
    )
    get(
        "/api/v1/notifyservice/test_send_mail",
        token,
        "notify: test_send_mail",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/notifyservice/notification/preserve_success",
        token,
        NOTIFY_INFO,
        "notify: preserve_success",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/notifyservice/notification/order_create_success",
        token,
        NOTIFY_INFO,
        "notify: order_create_success",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/notifyservice/notification/order_changed_success",
        token,
        NOTIFY_INFO,
        "notify: order_changed_success",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/notifyservice/notification/order_cancel_success",
        token,
        NOTIFY_INFO,
        "notify: order_cancel_success",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 23. ts-order-other-service (16 endpoints)
    # =================================================================
    print("--- ts-order-other-service (16 endpoints) ---")
    get("/api/v1/orderOtherService/welcome", token, "order-other: welcome")
    get("/api/v1/orderOtherService/orderOther", token, "order-other: GET all")
    get(
        f"/api/v1/orderOtherService/orderOther/{ORDER_OTHER_ID}",
        token,
        "order-other: GET by id",
    )
    get(
        f"/api/v1/orderOtherService/orderOther/price/{ORDER_OTHER_ID}",
        token,
        "order-other: GET price",
    )
    get(
        f"/api/v1/orderOtherService/orderOther/orderPay/{ORDER_OTHER_ID}",
        token,
        "order-other: orderPay",
    )
    get(
        f"/api/v1/orderOtherService/orderOther/status/{ORDER_OTHER_ID}/1",
        token,
        "order-other: modify status",
    )
    get(
        f"/api/v1/orderOtherService/orderOther/security/{TODAY}/{USER_ID}",
        token,
        "order-other: security check",
        timeout=TIMEOUT_LONG,
    )
    get(
        f"/api/v1/orderOtherService/orderOther/{TODAY}/K1235",
        token,
        "order-other: sold tickets",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/orderOtherService/orderOther/tickets",
        token,
        {
            "travelDate": TODAY,
            "trainNumber": "K1235",
            "startStation": "shanghai",
            "destStation": "taiyuan",
            "seatType": 2,
            "totalNum": 0,
            "stations": ["shanghai", "nanjing", "shijiazhuang", "taiyuan"],
        },
        "order-other: POST tickets",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/orderOtherService/orderOther/query",
        token,
        ORDER_QUERY,
        "order-other: POST query",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/orderOtherService/orderOther/refresh",
        token,
        ORDER_QUERY,
        "order-other: POST refresh",
        timeout=TIMEOUT_LONG,
    )
    # PUT, POST create, POST admin, DELETE skipped to avoid mutating real orders
    print()

    # =================================================================
    # 24. ts-order-service (16 endpoints)
    # =================================================================
    print("--- ts-order-service (16 endpoints) ---")
    get("/api/v1/orderservice/welcome", token, "order: welcome")
    get("/api/v1/orderservice/order", token, "order: GET all")
    get(f"/api/v1/orderservice/order/{ORDER_ID}", token, "order: GET by id")
    get(f"/api/v1/orderservice/order/price/{ORDER_ID}", token, "order: GET price")
    get(f"/api/v1/orderservice/order/orderPay/{ORDER_ID}", token, "order: orderPay")
    get(
        f"/api/v1/orderservice/order/status/{ORDER_ID}/0", token, "order: modify status"
    )
    get(
        f"/api/v1/orderservice/order/security/{TODAY}/{USER_ID}",
        token,
        "order: security check",
        timeout=TIMEOUT_LONG,
    )
    get(
        f"/api/v1/orderservice/order/{TODAY}/G1234",
        token,
        "order: sold tickets",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/orderservice/order/tickets",
        token,
        {
            "travelDate": TODAY,
            "trainNumber": "G1234",
            "startStation": "shanghai",
            "destStation": "beijing",
            "seatType": 2,
            "totalNum": 0,
            "stations": ["shanghai", "nanjing", "shijiazhuang", "taiyuan", "beijing"],
        },
        "order: POST tickets",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/orderservice/order/query",
        token,
        ORDER_QUERY,
        "order: POST query",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/orderservice/order/refresh",
        token,
        ORDER_QUERY,
        "order: POST refresh",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 25. ts-payment-service (4 endpoints)
    # =================================================================
    print("--- ts-payment-service (4 endpoints) ---")
    get("/api/v1/paymentservice/welcome", token, "payment: welcome")
    get("/api/v1/paymentservice/payment", token, "payment: GET all")
    post(
        "/api/v1/paymentservice/payment",
        token,
        {"id": "", "orderId": ORDER_ID, "userId": USER_ID, "price": "0.01"},
        "payment: POST pay",
    )
    post(
        "/api/v1/paymentservice/payment/money",
        token,
        {"id": "", "orderId": ORDER_ID, "userId": USER_ID, "price": "0.01"},
        "payment: POST addMoney",
    )
    print()

    # =================================================================
    # 26. ts-preserve-other-service (2 endpoints)
    # =================================================================
    print("--- ts-preserve-other-service (2 endpoints) ---")
    get("/api/v1/preserveotherservice/welcome", token, "preserve-other: welcome")
    post(
        "/api/v1/preserveotherservice/preserveOther",
        token,
        {
            "accountId": USER_ID,
            "contactsId": CONTACT_ID_2,
            "tripId": "K1345",
            "seatType": 2,
            "date": TODAY,
            "from": "shanghai",
            "to": "taiyuan",
            "assurance": 0,
            "foodType": 0,
            "stationName": "",
            "storeName": "",
            "foodName": "",
            "foodPrice": 0,
            "handleDate": "",
            "consigneeName": "",
            "consigneePhone": "",
            "consigneeWeight": 0,
            "isWithin": False,
        },
        "preserve-other: POST preserve",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 27. ts-preserve-service (2 endpoints)
    # =================================================================
    print("--- ts-preserve-service (2 endpoints) ---")
    get("/api/v1/preserveservice/welcome", token, "preserve: welcome")
    post(
        "/api/v1/preserveservice/preserve",
        token,
        {
            "accountId": USER_ID,
            "contactsId": CONTACT_ID_1,
            "tripId": "D1345",
            "seatType": 2,
            "date": TODAY,
            "from": "shanghai",
            "to": "suzhou",
            "assurance": 0,
            "foodType": 0,
            "stationName": "",
            "storeName": "",
            "foodName": "",
            "foodPrice": 0,
            "handleDate": "",
            "consigneeName": "",
            "consigneePhone": "",
            "consigneeWeight": 0,
            "isWithin": False,
        },
        "preserve: POST preserve",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 28. ts-price-service (7 endpoints)
    # =================================================================
    print("--- ts-price-service (7 endpoints) ---")
    get("/api/v1/priceservice/prices/welcome", token, "price: welcome")
    get("/api/v1/priceservice/prices", token, "price: GET all")
    # Get a real price to find routeId/trainType
    r = get("/api/v1/priceservice/prices", token, "price: GET all (for IDs)")
    price_id = ""
    if r and r.status_code == 200:
        try:
            prices = r.json().get("data", [])
            if prices:
                p = prices[0]
                get(
                    f"/api/v1/priceservice/prices/{p['routeId']}/{p['trainType']}",
                    token,
                    "price: GET by route+train",
                )
                price_id = p.get("id", "")
        except Exception:
            pass
    post(
        "/api/v1/priceservice/prices/byRouteIdsAndTrainTypes",
        token,
        [f"{ROUTE_ID}:GaoTieOne"],
        "price: POST byRouteIdsAndTrainTypes",
    )
    # POST create, PUT update, DELETE skipped to avoid changing pricing data
    print()

    # =================================================================
    # 29. ts-rebook-service (3 endpoints)
    # =================================================================
    print("--- ts-rebook-service (3 endpoints) ---")
    get("/api/v1/rebookservice/welcome", token, "rebook: welcome")
    post(
        "/api/v1/rebookservice/rebook",
        token,
        {
            "loginId": USER_ID,
            "orderId": ORDER_ID,
            "oldTripId": "G1237",
            "tripId": "G1234",
            "seatType": 2,
            "date": TODAY,
        },
        "rebook: POST rebook",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/rebookservice/rebook/difference",
        token,
        {
            "loginId": USER_ID,
            "orderId": ORDER_ID,
            "oldTripId": "G1237",
            "tripId": "G1234",
            "seatType": 2,
            "date": TODAY,
        },
        "rebook: POST difference",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 30. ts-route-plan-service (4 endpoints)
    # =================================================================
    print("--- ts-route-plan-service (4 endpoints) ---")
    get("/api/v1/routeplanservice/welcome", token, "route-plan: welcome")
    post(
        "/api/v1/routeplanservice/routePlan/cheapestRoute",
        token,
        {
            "startStation": "shanghai",
            "endStation": "taiyuan",
            "travelDate": TODAY,
            "num": 5,
        },
        "route-plan: cheapest",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/routeplanservice/routePlan/quickestRoute",
        token,
        {
            "startStation": "shanghai",
            "endStation": "taiyuan",
            "travelDate": TODAY,
            "num": 5,
        },
        "route-plan: quickest",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/routeplanservice/routePlan/minStopStations",
        token,
        {
            "startStation": "shanghai",
            "endStation": "taiyuan",
            "travelDate": TODAY,
            "num": 5,
        },
        "route-plan: minStops",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 31. ts-route-service (7 endpoints)
    # =================================================================
    print("--- ts-route-service (7 endpoints) ---")
    get("/api/v1/routeservice/welcome", token, "route: welcome")
    get("/api/v1/routeservice/routes", token, "route: GET all")
    get(f"/api/v1/routeservice/routes/{ROUTE_ID}", token, "route: GET by id")
    get(
        "/api/v1/routeservice/routes/shanghai/nanjing", token, "route: GET by start/end"
    )
    post("/api/v1/routeservice/routes/byIds", token, [ROUTE_ID], "route: POST byIds")
    # POST create, DELETE skipped to avoid mutating route data
    print()

    # =================================================================
    # 32. ts-seat-service (3 endpoints)
    # =================================================================
    print("--- ts-seat-service (3 endpoints) ---")
    get("/api/v1/seatservice/welcome", token, "seat: welcome")
    post(
        "/api/v1/seatservice/seats/left_tickets",
        token,
        {
            "travelDate": TODAY,
            "trainNumber": "D1345",
            "startStation": "shanghai",
            "destStation": "suzhou",
            "seatType": 2,
            "totalNum": 0,
            "stations": ["shanghai", "suzhou"],
        },
        "seat: POST left_tickets",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/seatservice/seats",
        token,
        {
            "travelDate": TODAY,
            "trainNumber": "D1345",
            "startStation": "shanghai",
            "destStation": "suzhou",
            "seatType": 2,
            "totalNum": 100,
            "stations": ["shanghai", "suzhou"],
        },
        "seat: POST distribute",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 33. ts-security-service (6 endpoints)
    # =================================================================
    print("--- ts-security-service (6 endpoints) ---")
    get("/api/v1/securityservice/welcome", token, "security: welcome")
    get("/api/v1/securityservice/securityConfigs", token, "security: GET all")
    get(
        f"/api/v1/securityservice/securityConfigs/{USER_ID}",
        token,
        "security: check by accountId",
    )
    # POST create, PUT update, DELETE skipped to avoid changing security configs
    print()

    # =================================================================
    # 34. ts-station-food-service (5 endpoints)
    # =================================================================
    print("--- ts-station-food-service (5 endpoints) ---")
    get(
        "/api/v1/stationfoodservice/stationfoodstores/welcome",
        token,
        "station-food: welcome",
    )
    get("/api/v1/stationfoodservice/stationfoodstores", token, "station-food: GET all")
    # GET by stationId returns 500 due to controller param name mismatch (known issue)
    get(
        "/api/v1/stationfoodservice/stationfoodstores/suzhou",
        token,
        "station-food: GET by station",
    )
    post(
        "/api/v1/stationfoodservice/stationfoodstores",
        token,
        ["suzhou", "shanghai"],
        "station-food: POST batch by names",
    )
    # GET by storeId - need a real store ID
    r = requests.get(
        f"{GW}/api/v1/stationfoodservice/stationfoodstores",
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    store_id = ""
    try:
        stores = r.json().get("data", [])
        if stores:
            store_id = stores[0].get("id", "")
    except Exception:
        pass
    if store_id:
        get(
            f"/api/v1/stationfoodservice/stationfoodstores/bystoreid/{store_id}",
            token,
            "station-food: GET by storeId",
        )
    print()

    # =================================================================
    # 35. ts-station-service (9 endpoints)
    # =================================================================
    print("--- ts-station-service (9 endpoints) ---")
    get("/api/v1/stationservice/welcome", token, "station: welcome")
    get("/api/v1/stationservice/stations", token, "station: GET all")
    get("/api/v1/stationservice/stations/id/shanghai", token, "station: GET id by name")
    get(
        f"/api/v1/stationservice/stations/name/{STATION_ID_SHANGHAI}",
        token,
        "station: GET name by id",
    )
    post(
        "/api/v1/stationservice/stations/idlist",
        token,
        ["shanghai", "nanjing", "suzhou"],
        "station: POST idlist",
    )
    post(
        "/api/v1/stationservice/stations/namelist",
        token,
        [STATION_ID_SHANGHAI],
        "station: POST namelist",
    )
    # POST create, PUT update, DELETE skipped to avoid mutating station data
    print()

    # =================================================================
    # 36. ts-ticket-office-service (7 endpoints)
    # =================================================================
    print("--- ts-ticket-office-service (7 endpoints) ---")
    get("/office/", token, "ticket-office: GET /")
    get("/office/getRegionList", token, "ticket-office: getRegionList")
    print()

    # =================================================================
    # 37. ts-train-food-service (3 endpoints)
    # =================================================================
    print("--- ts-train-food-service (3 endpoints) ---")
    get("/api/v1/trainfoodservice/trainfoods/welcome", token, "train-food: welcome")
    get("/api/v1/trainfoodservice/trainfoods", token, "train-food: GET all")
    get("/api/v1/trainfoodservice/trainfoods/D1345", token, "train-food: GET by tripId")
    print()

    # =================================================================
    # 38. ts-train-service (8 endpoints)
    # =================================================================
    print("--- ts-train-service (8 endpoints) ---")
    get("/api/v1/trainservice/trains/welcome", token, "train: welcome")
    get("/api/v1/trainservice/trains", token, "train: GET all")
    get("/api/v1/trainservice/trains/byName/GaoTieOne", token, "train: GET by name")
    post(
        "/api/v1/trainservice/trains/byNames",
        token,
        ["GaoTieOne", "DongCheOne", "ZhiDa"],
        "train: POST byNames",
    )
    # GET by id - need a real train ID
    r = requests.get(
        f"{GW}/api/v1/trainservice/trains",
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    try:
        trains = r.json().get("data", [])
        if trains:
            get(
                f"/api/v1/trainservice/trains/{trains[0]['id']}",
                token,
                "train: GET by id",
            )
    except Exception:
        pass
    # POST create, PUT update, DELETE skipped to avoid mutating train data
    print()

    # =================================================================
    # 39. ts-travel-plan-service (5 endpoints)
    # =================================================================
    print("--- ts-travel-plan-service (5 endpoints) ---")
    get("/api/v1/travelplanservice/welcome", token, "travel-plan: welcome")
    post(
        "/api/v1/travelplanservice/travelPlan/cheapest",
        token,
        {
            "startPlace": "shanghai",
            "endPlace": "taiyuan",
            "departureTime": TODAY,
        },
        "travel-plan: cheapest",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/travelplanservice/travelPlan/quickest",
        token,
        {
            "startPlace": "shanghai",
            "endPlace": "taiyuan",
            "departureTime": TODAY,
        },
        "travel-plan: quickest",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/travelplanservice/travelPlan/minStation",
        token,
        {
            "startPlace": "shanghai",
            "endPlace": "taiyuan",
            "departureTime": TODAY,
        },
        "travel-plan: minStation",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/travelplanservice/travelPlan/transferResult",
        token,
        {
            "startStation": "shanghai",
            "viaStation": "nanjing",
            "endStation": "beijing",
            "travelDate": TODAY,
            "trainType": "G",
        },
        "travel-plan: transferResult",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 40. ts-travel-service (13 endpoints)
    # =================================================================
    print("--- ts-travel-service (13 endpoints) ---")
    get("/api/v1/travelservice/welcome", token, "travel: welcome")
    get("/api/v1/travelservice/trips", token, "travel: GET all trips")
    get("/api/v1/travelservice/admin_trip", token, "travel: GET admin_trip")
    get("/api/v1/travelservice/trips/D1345", token, "travel: GET trip by id")
    get(
        "/api/v1/travelservice/train_types/D1345",
        token,
        "travel: GET train_type by tripId",
    )
    get("/api/v1/travelservice/routes/D1345", token, "travel: GET route by tripId")
    post(
        "/api/v1/travelservice/trips/left",
        token,
        {"startPlace": "shanghai", "endPlace": "suzhou", "departureTime": TODAY},
        "travel: POST trips/left",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/travelservice/trips/left_parallel",
        token,
        {"startPlace": "shanghai", "endPlace": "suzhou", "departureTime": TODAY},
        "travel: POST trips/left_parallel",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/travelservice/trip_detail",
        token,
        {
            "tripId": "D1345",
            "travelDate": TODAY,
            "from": "shanghai",
            "to": "suzhou",
        },
        "travel: POST trip_detail",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/travelservice/trips/routes",
        token,
        [ROUTE_ID],
        "travel: POST trips/routes",
        timeout=TIMEOUT_LONG,
    )
    # POST create, PUT update, DELETE skipped to avoid mutating trip data
    print()

    # =================================================================
    # 41. ts-travel2-service (12 endpoints)
    # =================================================================
    print("--- ts-travel2-service (12 endpoints) ---")
    get("/api/v1/travel2service/welcome", token, "travel2: welcome")
    get("/api/v1/travel2service/trips", token, "travel2: GET all trips")
    get("/api/v1/travel2service/admin_trip", token, "travel2: GET admin_trip")
    get("/api/v1/travel2service/trips/Z1234", token, "travel2: GET trip by id")
    get(
        "/api/v1/travel2service/train_types/Z1234",
        token,
        "travel2: GET train_type by tripId",
    )
    get("/api/v1/travel2service/routes/Z1234", token, "travel2: GET route by tripId")
    post(
        "/api/v1/travel2service/trips/left",
        token,
        {
            "startPlace": "shanghai",
            "endPlace": "taiyuan",
            "departureTime": TODAY,
        },
        "travel2: POST trips/left",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/travel2service/trip_detail",
        token,
        {
            "tripId": "Z1234",
            "travelDate": TODAY,
            "from": "shanghai",
            "to": "taiyuan",
        },
        "travel2: POST trip_detail",
        timeout=TIMEOUT_LONG,
    )
    post(
        "/api/v1/travel2service/trips/routes",
        token,
        [ROUTE_ID],
        "travel2: POST trips/routes",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 42. ts-user-service (7 endpoints)
    # =================================================================
    print("--- ts-user-service (7 endpoints) ---")
    get("/api/v1/userservice/users/hello", token, "user: hello")
    get("/api/v1/userservice/users", token, "user: GET all")
    get(f"/api/v1/userservice/users/id/{USER_ID}", token, "user: GET by userId")
    get("/api/v1/userservice/users/fdse_microservice", token, "user: GET by userName")
    # POST register, PUT update, DELETE skipped to avoid mutating user data
    print()

    # =================================================================
    # 43. ts-verification-code-service (2 endpoints)
    # =================================================================
    print("--- ts-verification-code-service (2 endpoints) ---")
    r = get_raw("/api/v1/verifycode/generate", "verify-code: generate")
    if r:
        ok = r.status_code == 200 and len(r.content) > 100
        result(
            "verify-code: generate", r.status_code, ok, f"size={len(r.content)} bytes"
        )
    get("/api/v1/verifycode/verify/1234", token, "verify-code: verify")
    print()

    # =================================================================
    # 44. ts-voucher-service (1 endpoint)
    # =================================================================
    print("--- ts-voucher-service (1 endpoint) ---")
    # Voucher needs a real order ID from the order service (crashes on null)
    _voucher_order_id = ORDER_ID
    r = get("/api/v1/orderservice/order", token, "voucher: fetch orders for valid ID")
    if r and r.status_code == 200:
        try:
            _orders = r.json().get("data", [])
            if _orders:
                _voucher_order_id = _orders[0]["id"]
        except Exception:
            pass
    post(
        "/getVoucher",
        token,
        {"orderId": _voucher_order_id, "type": 1},
        "voucher: POST getVoucher",
        timeout=TIMEOUT_LONG,
    )
    print()

    # =================================================================
    # 45. ts-wait-order-service (4 endpoints)
    # =================================================================
    print("--- ts-wait-order-service (4 endpoints) ---")
    get("/api/v1/waitorderservice/welcome", token, "wait-order: welcome")
    get("/api/v1/waitorderservice/orders", token, "wait-order: GET all")
    get("/api/v1/waitorderservice/waitlistorders", token, "wait-order: GET waitlist")
    print()

    # =================================================================
    # SUMMARY
    # =================================================================
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    if errors:
        print(f"\nFAILED ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    print("=" * 70)


if __name__ == "__main__":
    main()
