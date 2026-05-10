"""
Tests for auth_router.py - Authentication endpoints (login, logout, refresh, register).
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from auth_router import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
    login,
    logout,
    refresh_token,
    register_user,
    list_users,
)
from models import User, Role
from auth import create_access_token, create_refresh_token


class TestLoginEndpoint:
    """Tests for POST /api/v1/auth/login"""

    def test_login_success(self):
        """Test successful login with valid credentials."""
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user-id"
        mock_user.email = "test@example.com"
        mock_user.password_hash = "$2b$12$validhash"
        mock_user.is_active = True
        mock_user.last_login_at = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        req = LoginRequest(email="test@example.com", password="password123")

        with patch("auth_router.verify_password", return_value=True), \
             patch("auth_router.create_access_token", return_value="access_token_123"), \
             patch("auth_router.create_refresh_token", return_value="refresh_token_123"):
            response = login(req, mock_db)

        assert response.access_token == "access_token_123"
        assert response.refresh_token == "refresh_token_123"
        assert response.expires_in == 15 * 60
        mock_db.commit.assert_called_once()

    def test_login_user_not_found(self):
        """Test login fails when user doesn't exist."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        req = LoginRequest(email="nonexistent@example.com", password="password123")

        with pytest.raises(HTTPException) as exc_info:
            login(req, mock_db)

        assert exc_info.value.status_code == 401
        assert "Invalid email or password" in exc_info.value.detail

    def test_login_wrong_password(self):
        """Test login fails with wrong password."""
        mock_user = MagicMock(spec=User)
        mock_user.email = "test@example.com"
        mock_user.is_active = True

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        req = LoginRequest(email="test@example.com", password="wrongpassword")

        with patch("auth_router.verify_password", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                login(req, mock_db)

        assert exc_info.value.status_code == 401

    def test_login_inactive_user(self):
        """Test login fails for inactive user."""
        mock_user = MagicMock(spec=User)
        mock_user.email = "test@example.com"
        mock_user.is_active = False

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        req = LoginRequest(email="test@example.com", password="password123")

        with patch("auth_router.verify_password", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                login(req, mock_db)

        assert exc_info.value.status_code == 401
        assert "deactivated" in exc_info.value.detail


class TestLogoutEndpoint:
    """Tests for POST /api/v1/auth/logout"""

    def test_logout_success(self):
        """Test successful logout with valid token."""
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user-id"

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer valid_token_123"}

        mock_db = MagicMock()

        with patch("auth_router.decode_token", return_value={"jti": "token_jti", "exp": 9999999999}), \
             patch("auth_router.blacklist_token") as mock_blacklist:
            response = logout(mock_request, mock_user, mock_db)

        assert response == {"message": "Logout successful"}
        mock_blacklist.assert_called_once()

    def test_logout_no_auth_header(self):
        """Test logout without Authorization header."""
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user-id"

        mock_request = MagicMock()
        mock_request.headers = {}

        mock_db = MagicMock()

        response = logout(mock_request, mock_user, mock_db)

        assert response == {"message": "Logout successful"}
        mock_db.commit.assert_not_called()

    def test_logout_non_bearer_token(self):
        """Test logout with non-Bearer token format."""
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user-id"

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Basic some_credentials"}

        mock_db = MagicMock()

        response = logout(mock_request, mock_user, mock_db)

        assert response == {"message": "Logout successful"}
        mock_db.commit.assert_not_called()

    def test_logout_with_invalid_token_decode(self):
        """Test logout handles decode exceptions gracefully."""
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user-id"

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer invalid_token"}

        mock_db = MagicMock()

        with patch("auth_router.decode_token", side_effect=HTTPException(status_code=401, detail="Invalid token")):
            response = logout(mock_request, mock_user, mock_db)

        assert response == {"message": "Logout successful"}


class TestRefreshTokenEndpoint:
    """Tests for POST /api/v1/auth/refresh"""

    def test_refresh_token_success(self):
        """Test successful token refresh with valid refresh token."""
        mock_user = MagicMock(spec=User)
        mock_user.id = "test-user-id"
        mock_user.is_active = True

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        req = RefreshRequest(refresh_token="valid_refresh_token")

        with patch("auth_router.decode_token", return_value={
            "type": "refresh",
            "sub": "test-user-id"
        }), \
             patch("auth_router.create_access_token", return_value="new_access_token"), \
             patch("auth_router.create_refresh_token", return_value="new_refresh_token"):
            response = refresh_token(req, mock_db)

        assert response.access_token == "new_access_token"
        assert response.refresh_token == "new_refresh_token"
        assert response.expires_in == 15 * 60

    def test_refresh_token_invalid_type(self):
        """Test refresh fails with access token instead of refresh token."""
        mock_db = MagicMock()

        req = RefreshRequest(refresh_token="access_token_as_refresh")

        with patch("auth_router.decode_token", return_value={
            "type": "access",
            "sub": "test-user-id"
        }):
            with pytest.raises(HTTPException) as exc_info:
                refresh_token(req, mock_db)

        assert exc_info.value.status_code == 401
        assert "Invalid refresh token type" in exc_info.value.detail

    def test_refresh_token_expired(self):
        """Test refresh fails with expired token."""
        mock_db = MagicMock()

        req = RefreshRequest(refresh_token="expired_refresh_token")

        with patch("auth_router.decode_token", side_effect=HTTPException(status_code=401, detail="Token expired")):
            with pytest.raises(HTTPException) as exc_info:
                refresh_token(req, mock_db)

        assert exc_info.value.status_code == 401

    def test_refresh_token_user_not_found(self):
        """Test refresh fails when user no longer exists."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        req = RefreshRequest(refresh_token="valid_but_user_gone")

        with patch("auth_router.decode_token", return_value={
            "type": "refresh",
            "sub": "deleted-user-id"
        }):
            with pytest.raises(HTTPException) as exc_info:
                refresh_token(req, mock_db)

        assert exc_info.value.status_code == 401
        assert "User not found or inactive" in exc_info.value.detail


class TestRegisterUserEndpoint:
    """Tests for POST /api/v1/auth/users"""

    def test_register_user_success(self):
        """Test successful user registration."""
        mock_role = MagicMock(spec=Role)
        mock_role.id = "role-id"
        mock_role.name = "viewer"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.side_effect = [None, mock_role]

        req = UserCreateRequest(
            email="newuser@example.com",
            password="password123",
            name="New User",
            role_name="viewer"
        )

        with patch("auth_router.seed_default_roles"), \
             patch("auth_router.hash_password", return_value="hashed_password"), \
             patch("auth_router.create_access_token", return_value="access_token"), \
             patch("auth_router.create_refresh_token", return_value="refresh_token"):
            response = register_user(req, mock_db)

        assert response.email == "newuser@example.com"
        assert response.name == "New User"
        assert response.role == "viewer"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_register_user_duplicate_email(self):
        """Test registration fails with existing email."""
        existing_user = MagicMock(spec=User)
        existing_user.email = "existing@example.com"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_user

        req = UserCreateRequest(
            email="existing@example.com",
            password="password123",
            name="Duplicate User"
        )

        with patch("auth_router.seed_default_roles"):
            with pytest.raises(HTTPException) as exc_info:
                register_user(req, mock_db)

        assert exc_info.value.status_code == 400
        assert "already registered" in exc_info.value.detail

    def test_register_user_with_invalid_role_falls_back_to_viewer(self):
        """Test registration falls back to viewer role if specified role doesn't exist."""
        mock_viewer_role = MagicMock(spec=Role)
        mock_viewer_role.id = "viewer-role-id"
        mock_viewer_role.name = "viewer"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.side_effect = [None, None, mock_viewer_role]

        req = UserCreateRequest(
            email="newuser@example.com",
            password="password123",
            name="New User",
            role_name="nonexistent_role"
        )

        with patch("auth_router.seed_default_roles"), \
             patch("auth_router.hash_password", return_value="hashed_password"):
            response = register_user(req, mock_db)

        assert response.role == "viewer"


class TestListUsersEndpoint:
    """Tests for GET /api/v1/auth/users"""

    def test_list_users_success(self):
        """Test successful user listing."""
        mock_role = MagicMock(spec=Role)
        mock_role.name = "admin"

        mock_user1 = MagicMock(spec=User)
        mock_user1.id = "user-1"
        mock_user1.email = "user1@example.com"
        mock_user1.name = "User One"
        mock_user1.role = mock_role
        mock_user1.is_active = True
        mock_user1.created_at = datetime.now(timezone.utc)

        mock_user2 = MagicMock(spec=User)
        mock_user2.id = "user-2"
        mock_user2.email = "user2@example.com"
        mock_user2.name = "User Two"
        mock_user2.role = mock_role
        mock_user2.is_active = True
        mock_user2.created_at = datetime.now(timezone.utc)

        mock_db = MagicMock()
        mock_db.query.return_value.offset.return_value.limit.return_value.all.return_value = [mock_user1, mock_user2]

        mock_current_user = MagicMock(spec=User)
        mock_current_user.id = "admin-user"

        with patch("auth_router.require_permissions", return_value=lambda: mock_current_user):
            response = list_users(skip=0, limit=100, db=mock_db, current_user=mock_current_user)

        assert len(response) == 2
        assert response[0].email == "user1@example.com"
        assert response[1].email == "user2@example.com"

    def test_list_users_excludes_system_accounts(self):
        """Test that system@ email accounts are excluded from listing."""
        mock_role = MagicMock(spec=Role)
        mock_role.name = "admin"

        mock_regular_user = MagicMock(spec=User)
        mock_regular_user.id = "user-1"
        mock_regular_user.email = "user@example.com"
        mock_regular_user.name = "Regular User"
        mock_regular_user.role = mock_role
        mock_regular_user.is_active = True
        mock_regular_user.created_at = datetime.now(timezone.utc)

        mock_system_user = MagicMock(spec=User)
        mock_system_user.id = "system-1"
        mock_system_user.email = "system@internal"
        mock_system_user.name = "System Account"
        mock_system_user.role = mock_role
        mock_system_user.is_active = True
        mock_system_user.created_at = datetime.now(timezone.utc)

        mock_db = MagicMock()
        mock_db.query.return_value.offset.return_value.limit.return_value.all.return_value = [mock_regular_user, mock_system_user]

        mock_current_user = MagicMock(spec=User)
        mock_current_user.id = "admin-user"

        with patch("auth_router.require_permissions", return_value=lambda: mock_current_user):
            response = list_users(skip=0, limit=100, db=mock_db, current_user=mock_current_user)

        # System account should be filtered out
        assert len(response) == 1
        assert response[0].email == "user@example.com"

    def test_list_users_pagination(self):
        """Test user listing respects skip and limit parameters."""
        mock_db = MagicMock()
        mock_db.query.return_value.offset.return_value.limit.return_value.all.return_value = []

        mock_current_user = MagicMock(spec=User)
        mock_current_user.id = "admin-user"

        with patch("auth_router.require_permissions", return_value=lambda: mock_current_user):
            list_users(skip=50, limit=25, db=mock_db, current_user=mock_current_user)

        mock_db.query.return_value.offset.assert_called_once_with(50)
        mock_db.query.return_value.offset.return_value.limit.assert_called_once_with(25)


class TestTokenResponseModel:
    """Tests for TokenResponse model."""

    def test_token_response_fields(self):
        """Test TokenResponse contains all required fields."""
        response = TokenResponse(
            access_token="access_123",
            refresh_token="refresh_456",
            expires_in=900
        )

        assert response.access_token == "access_123"
        assert response.refresh_token == "refresh_456"
        assert response.expires_in == 900


class TestUserResponseModel:
    """Tests for UserResponse model."""

    def test_user_response_from_attributes(self):
        """Test UserResponse can be created from SQLAlchemy model."""
        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        mock_user.is_active = True
        mock_user.created_at = datetime.now(timezone.utc)

        response = UserResponse.model_validate(mock_user)

        assert response.id == "user-123"
        assert response.email == "test@example.com"
        assert response.name == "Test User"
        assert response.is_active is True