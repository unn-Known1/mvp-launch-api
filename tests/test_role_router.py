"""
Tests for role_router.py - Role management endpoints.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from role_router import (
    RoleCreateRequest,
    RoleUpdateRequest,
    RoleResponse,
    UserRoleUpdateRequest,
    UserPermissionResponse,
    create_role,
    list_roles,
    get_role,
    update_role,
    delete_role,
    update_user_role,
    get_user_permissions,
)
from models import Role, User


class TestCreateRole:
    """Tests for POST /api/v1/roles"""

    def test_create_role_success(self):
        """Test successful role creation."""
        mock_role = MagicMock(spec=Role)
        mock_role.id = "role-id-123"
        mock_role.name = "analyst"
        mock_role.description = "Data analyst role"
        mock_role.permissions = ["datasets:read", "ml:forecast"]
        mock_role.created_at = datetime.now(timezone.utc)
        mock_role.updated_at = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        req = RoleCreateRequest(
            name="analyst",
            description="Data analyst role",
            permissions=["datasets:read", "ml:forecast"]
        )

        with patch("role_router.require_permissions", return_value=lambda: MagicMock()):
            with patch("role_router.get_current_user", return_value=MagicMock()):
                with patch("role_router.get_db", return_value=mock_db):
                    # Mock the role after add
                    mock_db.add = MagicMock()
                    mock_db.commit = MagicMock()
                    mock_db.refresh = MagicMock(side_effect=lambda r: setattr(r, 'id', mock_role.id) or setattr(r, 'created_at', mock_role.created_at))

                    response = create_role(req, mock_db, _=MagicMock())

        assert response.name == "analyst"
        assert response.description == "Data analyst role"
        assert "datasets:read" in response.permissions

    def test_create_role_duplicate_name(self):
        """Test role creation fails with existing role name."""
        existing_role = MagicMock(spec=Role)
        existing_role.name = "admin"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_role

        req = RoleCreateRequest(name="admin", description="Admin role")

        with patch("role_router.require_permissions", return_value=lambda: MagicMock()):
            with pytest.raises(HTTPException) as exc_info:
                create_role(req, mock_db, _=MagicMock())

        assert exc_info.value.status_code == 400
        assert "already exists" in exc_info.value.detail


class TestListRoles:
    """Tests for GET /api/v1/roles"""

    def test_list_roles_success(self):
        """Test successful role listing."""
        mock_viewer_role = MagicMock(spec=Role)
        mock_viewer_role.id = "role-1"
        mock_viewer_role.name = "viewer"
        mock_viewer_role.description = "Read-only access"
        mock_viewer_role.permissions = ["datasets:read"]
        mock_viewer_role.created_at = datetime.now(timezone.utc)
        mock_viewer_role.updated_at = None

        mock_analyst_role = MagicMock(spec=Role)
        mock_analyst_role.id = "role-2"
        mock_analyst_role.name = "analyst"
        mock_analyst_role.description = "Data analyst"
        mock_analyst_role.permissions = ["datasets:read", "ml:forecast"]
        mock_analyst_role.created_at = datetime.now(timezone.utc)
        mock_analyst_role.updated_at = None

        mock_db = MagicMock()
        mock_db.query.return_value.order_by.return_value.all.return_value = [mock_viewer_role, mock_analyst_role]

        with patch("role_router.seed_default_roles"):
            response = list_roles(mock_db, _=MagicMock())

        assert len(response) == 2
        assert response[0].name == "analyst"  # Ordered by name
        assert response[1].name == "viewer"

    def test_list_roles_empty(self):
        """Test listing when no roles exist."""
        mock_db = MagicMock()
        mock_db.query.return_value.order_by.return_value.all.return_value = []

        with patch("role_router.seed_default_roles"):
            response = list_roles(mock_db, _=MagicMock())

        assert len(response) == 0


class TestGetRole:
    """Tests for GET /api/v1/roles/{role_id}"""

    def test_get_role_success(self):
        """Test successful role retrieval."""
        mock_role = MagicMock(spec=Role)
        mock_role.id = "role-123"
        mock_role.name = "admin"
        mock_role.description = "Full access"
        mock_role.permissions = ["users:read", "users:write", "admin:access"]
        mock_role.created_at = datetime.now(timezone.utc)
        mock_role.updated_at = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_role

        response = get_role("role-123", mock_db, _=MagicMock())

        assert response.name == "admin"
        assert "admin:access" in response.permissions

    def test_get_role_not_found(self):
        """Test role retrieval for non-existent role."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_role("non-existent-id", mock_db, _=MagicMock())

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail


class TestUpdateRole:
    """Tests for PUT /api/v1/roles/{role_id}"""

    def test_update_role_description(self):
        """Test updating role description."""
        mock_role = MagicMock(spec=Role)
        mock_role.id = "role-123"
        mock_role.name = "analyst"
        mock_role.description = "Old description"
        mock_role.permissions = ["datasets:read"]
        mock_role.created_at = datetime.now(timezone.utc)
        mock_role.updated_at = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_role

        req = RoleUpdateRequest(description="New description")

        with patch("role_router.require_permissions", return_value=lambda: MagicMock()):
            response = update_role("role-123", req, mock_db, _=MagicMock())

        assert response.description == "New description"
        mock_db.commit.assert_called_once()

    def test_update_role_permissions(self):
        """Test updating role permissions."""
        mock_role = MagicMock(spec=Role)
        mock_role.id = "role-123"
        mock_role.name = "analyst"
        mock_role.description = "Analyst role"
        mock_role.permissions = ["datasets:read"]
        mock_role.created_at = datetime.now(timezone.utc)
        mock_role.updated_at = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_role

        req = RoleUpdateRequest(permissions=["datasets:read", "datasets:write", "ml:forecast"])

        with patch("role_router.require_permissions", return_value=lambda: MagicMock()):
            response = update_role("role-123", req, mock_db, _=MagicMock())

        assert len(response.permissions) == 3
        assert "datasets:write" in response.permissions

    def test_update_role_not_found(self):
        """Test updating non-existent role."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        req = RoleUpdateRequest(description="New description")

        with patch("role_router.require_permissions", return_value=lambda: MagicMock()):
            with pytest.raises(HTTPException) as exc_info:
                update_role("non-existent-id", req, mock_db, _=MagicMock())

        assert exc_info.value.status_code == 404


class TestDeleteRole:
    """Tests for DELETE /api/v1/roles/{role_id}"""

    def test_delete_role_success(self):
        """Test successful role deletion."""
        mock_role = MagicMock(spec=Role)
        mock_role.id = "role-to-delete"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_role
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        with patch("role_router.require_permissions", return_value=lambda: MagicMock()):
            response = delete_role("role-to-delete", mock_db, _=MagicMock())

        assert response is None  # 204 No Content
        mock_db.delete.assert_called_once_with(mock_role)
        mock_db.commit.assert_called_once()

    def test_delete_role_with_active_users(self):
        """Test deleting role that has active users fails."""
        mock_role = MagicMock(spec=Role)
        mock_role.id = "role-with-users"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_role
        # Simulate users with this role
        mock_db.query.return_value.filter.return_value.count.return_value = 5

        with patch("role_router.require_permissions", return_value=lambda: MagicMock()):
            with pytest.raises(HTTPException) as exc_info:
                delete_role("role-with-users", mock_db, _=MagicMock())

        assert exc_info.value.status_code == 400
        assert "active user(s)" in exc_info.value.detail

    def test_delete_role_not_found(self):
        """Test deleting non-existent role."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("role_router.require_permissions", return_value=lambda: MagicMock()):
            with pytest.raises(HTTPException) as exc_info:
                delete_role("non-existent-id", mock_db, _=MagicMock())

        assert exc_info.value.status_code == 404


class TestUpdateUserRole:
    """Tests for PATCH /api/v1/roles/users/{user_id}/role"""

    def test_update_user_role_success(self):
        """Test successful user role update."""
        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"
        mock_user.email = "user@example.com"
        mock_user.name = "Test User"
        mock_user.role_id = "old-role-id"
        mock_user.is_active = True

        mock_new_role = MagicMock(spec=Role)
        mock_new_role.id = "new-role-id"
        mock_new_role.name = "analyst"
        mock_new_role.permissions = ["datasets:read", "ml:forecast"]

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_user, mock_new_role]

        req = UserRoleUpdateRequest(role_name="analyst")

        with patch("role_router.require_permissions", return_value=lambda: MagicMock()):
            response = update_user_role("user-123", req, mock_db, _=MagicMock())

        assert response.role == "analyst"
        assert response.permissions == ["datasets:read", "ml:forecast"]

    def test_update_user_role_user_not_found(self):
        """Test role update for non-existent user."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        req = UserRoleUpdateRequest(role_name="analyst")

        with patch("role_router.require_permissions", return_value=lambda: MagicMock()):
            with pytest.raises(HTTPException) as exc_info:
                update_user_role("non-existent-user", req, mock_db, _=MagicMock())

        assert exc_info.value.status_code == 404
        assert "User not found" in exc_info.value.detail

    def test_update_user_role_role_not_found(self):
        """Test role update with non-existent role name."""
        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_user, None]

        req = UserRoleUpdateRequest(role_name="nonexistent_role")

        with patch("role_router.require_permissions", return_value=lambda: MagicMock()):
            with pytest.raises(HTTPException) as exc_info:
                update_user_role("user-123", req, mock_db, _=MagicMock())

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail


class TestGetUserPermissions:
    """Tests for GET /api/v1/roles/users/{user_id}/permissions"""

    def test_get_own_permissions(self):
        """Test user can view their own permissions."""
        mock_role = MagicMock(spec=Role)
        mock_role.name = "analyst"
        mock_role.permissions = ["datasets:read", "ml:forecast"]

        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"
        mock_user.email = "user@example.com"
        mock_user.name = "Test User"
        mock_user.role = mock_role
        mock_user.is_active = True

        mock_current_user = MagicMock(spec=User)
        mock_current_user.id = "user-123"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        response = get_user_permissions("user-123", mock_db, current_user=mock_current_user)

        assert response.role == "analyst"
        assert "ml:forecast" in response.permissions

    def test_admin_can_view_other_user_permissions(self):
        """Test admin can view other user's permissions."""
        mock_role = MagicMock(spec=Role)
        mock_role.name = "viewer"
        mock_role.permissions = ["datasets:read"]

        mock_user = MagicMock(spec=User)
        mock_user.id = "other-user"
        mock_user.email = "other@example.com"
        mock_user.name = "Other User"
        mock_user.role = mock_role
        mock_user.is_active = True

        mock_admin = MagicMock(spec=User)
        mock_admin.id = "admin-user"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("role_router.require_permissions", return_value=lambda: MagicMock()) as mock_perms:
            response = get_user_permissions("other-user", mock_db, current_user=mock_admin)

        assert response.role == "viewer"
        mock_perms.assert_called()

    def test_get_permissions_user_not_found(self):
        """Test getting permissions for non-existent user."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_current_user = MagicMock(spec=User)
        mock_current_user.id = "admin-user"

        with pytest.raises(HTTPException) as exc_info:
            get_user_permissions("non-existent-user", mock_db, current_user=mock_current_user)

        assert exc_info.value.status_code == 404


class TestRoleResponseModel:
    """Tests for RoleResponse model."""

    def test_role_response_from_attributes(self):
        """Test RoleResponse can be created from SQLAlchemy model."""
        mock_role = MagicMock(spec=Role)
        mock_role.id = "role-123"
        mock_role.name = "admin"
        mock_role.description = "Full access"
        mock_role.permissions = ["admin:access"]
        mock_role.created_at = datetime.now(timezone.utc)
        mock_role.updated_at = None

        response = RoleResponse.model_validate(mock_role)

        assert response.id == "role-123"
        assert response.name == "admin"
        assert response.permissions == ["admin:access"]

    def test_role_response_with_optional_fields(self):
        """Test RoleResponse handles optional fields properly."""
        response = RoleResponse(
            id="role-456",
            name="minimal_role",
            description=None,
            permissions=[],
            created_at=None,
            updated_at=None
        )

        assert response.description is None
        assert response.permissions == []