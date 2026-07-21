import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.environment import get_app_env, is_development
from app.web.app import create_dashboard_app


class DevChangeTestRouteIntegrationTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("APP_ENV", None)

    @contextmanager
    def app_env(self, app_env: str | None):
        env = {}
        if app_env is not None:
            env["APP_ENV"] = app_env
        else:
            os.environ.pop("APP_ENV", None)
        with patch.dict(os.environ, env, clear=False):
            yield

    def test_routes_registered_on_app(self):
        with self.app_env("development"):
            app = create_dashboard_app()

        paths = sorted(
            getattr(route, "path", "")
            for route in app.routes
            if getattr(route, "path", "").startswith("/dev/change-test-site")
            or "/api/dev/change-test-site/" in getattr(route, "path", "")
        )

        self.assertTrue(getattr(app.state, "change_test_site_routes_registered", False))
        self.assertIn("/dev/change-test-site", paths)
        self.assertIn("/dev/change-test-site/policy-a", paths)
        self.assertIn("/dev/change-test-site/policy-b", paths)
        self.assertIn("/dev/change-test-site/status", paths)
        self.assertIn("/api/dev/change-test-site/homepage/change", paths)
        self.assertIn("/api/dev/change-test-site/policy-a/change", paths)
        self.assertIn("/api/dev/change-test-site/policy-b/change", paths)
        self.assertIn("/api/dev/change-test-site/reset", paths)
        self.assertNotIn("/dev/change-test-site/dev/change-test-site", paths)

    def test_development_get_routes_return_200(self):
        with self.app_env("development"):
            client = TestClient(create_dashboard_app())
            for path in (
                "/dev/change-test-site",
                "/dev/change-test-site/policy-a",
                "/dev/change-test-site/policy-b",
                "/dev/change-test-site/status",
            ):
                response = client.get(path)
                self.assertEqual(response.status_code, 200, msg=path)

    def test_production_get_routes_return_404(self):
        with self.app_env("production"):
            client = TestClient(create_dashboard_app())
            for path in (
                "/dev/change-test-site",
                "/dev/change-test-site/policy-a",
                "/dev/change-test-site/policy-b",
                "/dev/change-test-site/status",
            ):
                response = client.get(path)
                self.assertEqual(response.status_code, 404, msg=path)
                self.assertEqual(response.json(), {"detail": "Not found"})

    def test_production_mutation_endpoints_return_404(self):
        with self.app_env("production"):
            client = TestClient(create_dashboard_app())
            mutation_requests = [
                ("POST", "/api/dev/change-test-site/homepage/change", {"text": "x"}),
                ("POST", "/api/dev/change-test-site/policy-a/change", {"text": "x"}),
                ("POST", "/api/dev/change-test-site/policy-b/change", {"text": "x"}),
                ("POST", "/api/dev/change-test-site/reset", None),
            ]
            for method, path, payload in mutation_requests:
                response = client.request(method, path, json=payload)
                self.assertEqual(response.status_code, 404, msg=path)
                self.assertEqual(response.json(), {"detail": "Not found"})

    def test_app_env_recognized_after_startup_without_reimport(self):
        with self.app_env(None):
            app = create_dashboard_app()
            client = TestClient(app)
            blocked = client.get("/dev/change-test-site")
            self.assertEqual(blocked.status_code, 404)

            os.environ["APP_ENV"] = "development"
            self.assertTrue(is_development())
            self.assertEqual(get_app_env(), "development")

            enabled = client.get("/dev/change-test-site")
            self.assertEqual(enabled.status_code, 200)

    def test_dev_and_test_aliases_enable_routes(self):
        for app_env in ("dev", "test"):
            with self.subTest(app_env=app_env):
                with self.app_env(app_env):
                    client = TestClient(create_dashboard_app())
                    response = client.get("/dev/change-test-site")
                    self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
