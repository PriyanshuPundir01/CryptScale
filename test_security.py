import unittest
import json
import CryptScale
from CryptScale import app, ADMIN_USERNAME, ADMIN_PASSWORD_HASH
from werkzeug.security import check_password_hash

class TestCryptScaleSecurity(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app.config["TESTING"] = True

    def test_security_headers_present(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Content-Security-Policy", response.headers)
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("1; mode=block", response.headers.get("X-XSS-Protection", ""))
        self.assertEqual(response.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertNotIn("Server", response.headers)

    def test_debug_mode_off_by_default(self):
        self.assertFalse(self.app.debug)

    def test_password_hashing_pbkdf2(self):
        self.assertTrue(ADMIN_PASSWORD_HASH.startswith("pbkdf2:sha256:"))
        self.assertTrue(check_password_hash(ADMIN_PASSWORD_HASH, "CryptScale#Admin2026"))

    def test_admin_routes_protected_against_unauthorized(self):
        res_dash = self.client.get("/admin/dashboard")
        self.assertEqual(res_dash.status_code, 302)
        self.assertIn("/admin/login", res_dash.location)

        res_api = self.client.get("/admin/api/status")
        self.assertEqual(res_api.status_code, 401)
        data = res_api.get_json()
        self.assertIn("Unauthorized", data.get("error", ""))

    def test_admin_login_csrf_and_auth(self):
        # 1. Failed login without CSRF token
        fail_res = self.client.post("/admin/login", data={"username": "admin", "password": "CryptScale#Admin2026"})
        self.assertEqual(fail_res.status_code, 400)

        # 2. Get login page to retrieve CSRF token from session
        with self.client:
            get_res = self.client.get("/admin/login")
            self.assertEqual(get_res.status_code, 200)
            with self.client.session_transaction() as sess:
                token = sess.get("_csrf_token")
            self.assertIsNotNone(token)

            # 3. Successful login with CSRF token
            post_res = self.client.post(
                "/admin/login",
                data={"username": ADMIN_USERNAME, "password": "CryptScale#Admin2026", "csrf_token": token},
                follow_redirects=False
            )
            self.assertEqual(post_res.status_code, 302)
            self.assertIn("/admin/dashboard", post_res.location)

            # 4. Now access dashboard
            dash_res = self.client.get("/admin/dashboard")
            self.assertEqual(dash_res.status_code, 200)
            self.assertIn(b"SECURITY DASHBOARD", dash_res.data)

            # 5. Access protected admin api
            api_res = self.client.get("/admin/api/status")
            self.assertEqual(api_res.status_code, 200)
            api_data = api_res.get_json()
            self.assertEqual(api_data["security"]["debug_mode"], False)
            self.assertEqual(api_data["security"]["rate_limiting"], True)

            # 6. Logout
            logout_res = self.client.get("/admin/logout", follow_redirects=False)
            self.assertEqual(logout_res.status_code, 302)

            # 7. Verify locked out again
            dash_after = self.client.get("/admin/dashboard")
            self.assertEqual(dash_after.status_code, 302)

    def test_api_check_sanitization(self):
        res = self.client.post("/api/check", json={"password": "TestPassword123!\x00extra"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("score", data)
        self.assertIn("entropy", data)

    def test_api_generate_clamping(self):
        res = self.client.post("/api/generate", json={"length": 100})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["length"], 20)

    def test_cors_headers(self):
        res = self.client.options(
            "/api/check",
            headers={"Origin": "http://127.0.0.1:5001", "Access-Control-Request-Method": "POST"}
        )
        self.assertIn("Access-Control-Allow-Origin", res.headers)
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), "http://127.0.0.1:5001")

    def test_rate_limiting_admin_login(self):
        client = self.app.test_client()
        # Admin login is limited to 5 per minute
        for _ in range(5):
            client.get("/admin/login")
        exceeded_res = client.get("/admin/login")
        self.assertEqual(exceeded_res.status_code, 429)

if __name__ == "__main__":
    unittest.main()
