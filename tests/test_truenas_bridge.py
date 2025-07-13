from pydantic import ValidationError, SecretStr
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from truenas_bridge import TrueNASDaemon, Settings
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch


@pytest.fixture(autouse=True)
def disable_env_file():
    original_config = Settings.model_config
    Settings.model_config = dict(env_file=None)
    yield
    Settings.model_config = original_config


@pytest.fixture()
def setup_test_env(monkeypatch):
    monkeypatch.setenv("TRUENAS_HOST", "localhost")
    monkeypatch.setenv("TRUENAS_API_KEY", "api_key_value")
    monkeypatch.setenv("TRUENAS_API_USER", "api_user")


@pytest.fixture
def mock_settings():
    return Settings(
        truenas_host="localhost",
        truenas_api_key=SecretStr("api_key_value"),
        truenas_api_user="api_user",
        api_port=9999,
    )


@pytest.fixture
def daemon(mock_settings):
    daemon_instance = TrueNASDaemon(settings=mock_settings)
    daemon_instance.client = MagicMock()
    return daemon_instance


@pytest.fixture
def mock_truenas_client(disable_env_file, mock_settings):
    with patch("truenas_bridge.Client") as mock:
        client_instance = Mock()
        mock.return_value = client_instance
        client_instance.call.side_effect = [
            {"response_type": "SUCCESS"},  # First call will return this
            None,  # Second call's return value should be set in individual tests
        ]
        client_instance.ping.return_value = "pong"
        yield client_instance


@pytest.fixture
def test_app(mock_truenas_client, setup_test_env):
    from truenas_bridge import app

    client = TestClient(app)
    yield client


def test_settings_with_valid_env_variables(monkeypatch):
    monkeypatch.setenv("TRUENAS_HOST", "localhost")
    monkeypatch.setenv("TRUENAS_API_KEY", "api_key_value")
    monkeypatch.setenv("TRUENAS_API_USER", "api_user")
    monkeypatch.setenv("API_PORT", "8000")

    settings = Settings()

    assert settings.truenas_host == "localhost"
    assert settings.truenas_api_key == SecretStr("api_key_value")
    assert settings.truenas_api_user == "api_user"
    assert settings.api_port == 8000


def test_settings_with_missing_env_variables(monkeypatch):
    with pytest.raises(ValidationError):
        Settings()


def test_settings_with_invalid_api_port(monkeypatch):
    monkeypatch.setenv("TRUENAS_HOST", "localhost")
    monkeypatch.setenv("TRUENAS_API_KEY", "api_key_value")
    monkeypatch.setenv("TRUENAS_API_USER", "api_user")
    monkeypatch.setenv("API_PORT", "invalid_port")

    with pytest.raises(ValidationError):
        Settings()


def test_send_request_with_valid_method_and_params(daemon):
    """Test send_request with a valid method and parameters."""
    daemon.client.call.return_value = {"result": "success"}

    result = daemon.send_request("valid_method", ["param1", "param2"])

    daemon.client.call.assert_called_once_with("valid_method", "param1", "param2")
    assert result == {"result": "success"}


def test_send_request_when_client_not_initialized(mock_settings):
    """Test send_request when the client is not initialized."""
    daemon = TrueNASDaemon(settings=mock_settings)
    daemon.client = None

    with pytest.raises(HTTPException) as exc_info:
        daemon.send_request("some_method", [])

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "TrueNAS client not initialized"


def test_send_request_with_client_call_exception(daemon):
    """Test send_request when the client call raises an exception."""
    daemon.client.call.side_effect = Exception("Client call error")

    with pytest.raises(HTTPException) as exc_info:
        daemon.send_request("invalid_method", [])

    daemon.client.call.assert_called_once_with("invalid_method")
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Client call error"


def test_successful_connection(mock_truenas_client, test_app):
    """Test normal successful API call"""

    # Set the second response that will be returned after the auth success
    mock_truenas_client.call.side_effect = [
        {"response_type": "SUCCESS"},  # Auth response
        {"data": "test response"},  # Actual API call response
    ]

    with test_app as app:
        response = app.post(
            "/api/pool.query",
            json={"test": "data"},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 200
        assert response.json() == {"data": "test response"}


def test_connection_failure(mock_truenas_client, test_app):
    """Test connection failure scenario"""
    mock_truenas_client.call.side_effect = [
        {"response_type": "SUCCESS"},  # Auth response
        ConnectionError("Connection failed"),
    ]

    with test_app as app:
        response = app.post(
            "/api/pool.query",
            json={"test": "data"},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 500
        assert "Connection failed" in response.json()["detail"]


def test_authentication_failure(mock_truenas_client, test_app):
    """Test authentication failure"""
    mock_truenas_client.call.side_effect = [
        HTTPException(401),
        {"response_type": "FAILED"},
    ]

    with pytest.raises(HTTPException) as exc_info:
        with test_app as app:
            response = app.post(
                "/api/pool.query",
                json={"test": "data"},
                headers={"Authorization": "Basic dXNlcjpwYXNz"},
            )
            assert response.status_code == 401


def test_health_check_healthy(mock_truenas_client, test_app):
    """Test health check when connection is good"""
    mock_truenas_client.ping.return_value = "pong"

    with test_app as app:
        response = test_app.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


def test_health_check_unhealthy(mock_truenas_client, test_app):
    """Test health check when connection is bad"""
    mock_truenas_client.ping.side_effect = ConnectionError()

    with test_app as app:
        response = test_app.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"
