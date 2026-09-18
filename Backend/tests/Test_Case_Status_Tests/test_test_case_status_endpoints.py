from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_request_authorizer
from app.components.authorizer import (
    ROLE_PERMISSIONS,
    AuthenticatedUser,
    Permission,
    Role,
    parse_role,
)
from app.main import app
from app.schemas.test_cases import TestCaseStatus


class _AllowAllAuthorizer:
    """Test authorizer that grants every permission; authz is not under test here."""

    def has_permission(self, user, permission) -> bool:
        return True

    def permissions_for(self, user) -> frozenset:
        return frozenset()


@pytest.fixture()
def client(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Test User",
        email="test.user@example.com",
        role=Role.TEST_LEAD.value,
        is_active=True,
    )
    app.dependency_overrides[get_request_authorizer] = lambda: _AllowAllAuthorizer()
    monkeypatch.setattr(
        "app.api.dependencies.get_visible_project_ids",
        lambda db, user_id: None,
    )
    monkeypatch.setattr(
        "app.api.dependencies.get_project_ids_for_test_case_ids",
        lambda db, ids: set(),
    )
    monkeypatch.setattr(
        "app.database.users_db.get_user_by_id",
        lambda db, user_id: AuthenticatedUser(
            id=user_id,
            name="Test User",
            email="test.user@example.com",
            role=Role.TEST_LEAD.value,
            is_active=True,
        ),
    )
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_request_authorizer, None)


def test_update_status_by_ids_endpoint_success(monkeypatch, client: TestClient):
    expected = {
        "found_count": 1,
        "updated_count": 1,
        "results": [
            {
                "id": str(uuid.uuid4()),
                "status": TestCaseStatus.approved,
                "success": True,
                "error": None,
            }
        ],
    }

    # Make assertion deterministic by controlling UUID.
    fixed_id = expected["results"][0]["id"]
    project_id = uuid.uuid4()

    def _mock_service(
        _db, *, test_case_ids: list[str], new_status: TestCaseStatus, project_id: uuid.UUID
    ) -> dict[str, Any]:
        assert test_case_ids == [fixed_id]
        assert new_status == TestCaseStatus.approved
        return expected

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.bulk_update_status_by_ids",
        _mock_service,
    )

    resp = client.patch(
        "/api/v1/test-cases/status",
        json={
            "ids": [fixed_id],
            "status": TestCaseStatus.approved.value,
            "projectId": str(project_id),
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "Test case status update completed: 1 updated to 'approved'"
    assert body["data"]["found_count"] == expected["found_count"]
    assert body["data"]["updated_count"] == expected["updated_count"]
    assert body["data"]["results"][0]["id"] == fixed_id
    assert body["data"]["results"][0]["status"] == "approved"
    assert body["data"]["results"][0]["success"] is True
    assert "error" not in body["data"]["results"][0] or body["data"]["results"][0]["error"] is None


def test_update_status_by_ids_endpoint_clean_message_does_not_echo_ids(
    monkeypatch, client: TestClient
):
    many_ids = [str(uuid.uuid4()) for _ in range(35)]
    project_id = uuid.uuid4()

    def _mock_service(_db, *, test_case_ids, new_status, project_id, **_kwargs):
        return {
            "found_count": len(test_case_ids),
            "updated_count": len(test_case_ids),
            "results": [],
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.bulk_update_status_by_ids",
        _mock_service,
    )

    resp = client.patch(
        "/api/v1/test-cases/status",
        json={
            "ids": many_ids,
            "status": TestCaseStatus.approved.value,
            "projectId": str(project_id),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    expected_msg = f"Test case status update completed: {len(many_ids)} updated to 'approved'"
    assert body["message"] == expected_msg
    assert all(id_str not in body["message"] for id_str in many_ids)


def test_update_status_by_ids_endpoint_validation_error_missing_status(client: TestClient):
    resp = client.patch(
        "/api/v1/test-cases/status",
        json={"ids": [str(uuid.uuid4())], "projectId": str(uuid.uuid4())},
    )
    assert resp.status_code == 422


def test_update_status_by_ids_endpoint_validation_error_missing_project_id(client: TestClient):
    resp = client.patch(
        "/api/v1/test-cases/status",
        json={"ids": [str(uuid.uuid4())], "status": TestCaseStatus.approved.value},
    )
    assert resp.status_code == 422


def test_update_status_by_ids_endpoint_service_exception_triggers_500(
    monkeypatch, client: TestClient
):
    def _mock_service(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.bulk_update_status_by_ids",
        _mock_service,
    )

    resp = client.patch(
        "/api/v1/test-cases/status",
        json={
            "ids": [str(uuid.uuid4())],
            "status": TestCaseStatus.approved.value,
            "projectId": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "TEST_CASE_STATUS_UPDATE_FAILED"
    assert body["error"]["message"] == "Failed to update test case statuses"


class _PolicyBasedAuthorizer:
    def has_permission(self, user: AuthenticatedUser, permission: Permission) -> bool:
        canonical_role = parse_role(user.role)
        if not canonical_role:
            return False
        return permission in ROLE_PERMISSIONS.get(canonical_role, frozenset())

    def permissions_for(self, user: AuthenticatedUser) -> frozenset[str]:
        canonical_role = parse_role(user.role)
        if not canonical_role:
            return frozenset()
        return frozenset(p.value for p in ROLE_PERMISSIONS.get(canonical_role, frozenset()))


@pytest.mark.parametrize(
    "role_enum",
    [Role.TEST_LEAD, Role.TEST_MANAGER, Role.TEST_ENGINEER],
)
def test_update_status_endpoint_allowed_for_authorized_roles(monkeypatch, role_enum):
    target_id = str(uuid.uuid4())
    project_id = uuid.uuid4()
    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.bulk_update_status_by_ids",
        lambda _db, *, test_case_ids, new_status, project_id: {
            "found_count": 1,
            "updated_count": 1,
            "results": [{"id": target_id, "status": new_status, "success": True, "error": None}],
        },
    )
    monkeypatch.setattr(
        "app.api.dependencies.get_visible_project_ids",
        lambda db, user_id: None,
    )
    monkeypatch.setattr(
        "app.api.dependencies.get_project_ids_for_test_case_ids",
        lambda db, ids: set(),
    )
    monkeypatch.setattr(
        "app.database.users_db.get_user_by_id",
        lambda db, user_id: AuthenticatedUser(
            id=user_id,
            name=f"User {role_enum.value}",
            email=f"{role_enum.name.lower()}@example.com",
            role=role_enum.value,
            is_active=True,
        ),
    )

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=uuid.uuid4(),
        name=f"User {role_enum.value}",
        email=f"{role_enum.name.lower()}@example.com",
        role=role_enum.value,
        is_active=True,
    )
    app.dependency_overrides[get_request_authorizer] = lambda: _PolicyBasedAuthorizer()

    try:
        test_client = TestClient(app)
        resp = test_client.patch(
            "/api/v1/test-cases/status",
            json={
                "ids": [target_id],
                "status": TestCaseStatus.approved.value,
                "projectId": str(project_id),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["updated_count"] == 1
        assert body["data"]["results"][0]["id"] == target_id
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_request_authorizer, None)


@pytest.mark.parametrize("unauthorized_role", ["Viewer", "Guest", "UnknownRole", ""])
def test_update_status_endpoint_forbidden_for_unauthorized_roles(monkeypatch, unauthorized_role):
    monkeypatch.setattr(
        "app.api.dependencies.get_visible_project_ids",
        lambda db, user_id: None,
    )
    monkeypatch.setattr(
        "app.database.users_db.get_user_by_id",
        lambda db, user_id: AuthenticatedUser(
            id=user_id,
            name="Unauthorized User",
            email="unauthorized@example.com",
            role=unauthorized_role,
            is_active=True,
        ),
    )
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=uuid.uuid4(),
        name="Unauthorized User",
        email="unauthorized@example.com",
        role=unauthorized_role,
        is_active=True,
    )
    app.dependency_overrides[get_request_authorizer] = lambda: _PolicyBasedAuthorizer()

    try:
        test_client = TestClient(app)
        resp = test_client.patch(
            "/api/v1/test-cases/status",
            json={
                "ids": [str(uuid.uuid4())],
                "status": TestCaseStatus.approved.value,
                "projectId": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_request_authorizer, None)


def test_update_status_endpoint_single_test_case_approval(monkeypatch, client: TestClient):
    single_id = str(uuid.uuid4())
    project_id = uuid.uuid4()
    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.bulk_update_status_by_ids",
        lambda _db, *, test_case_ids, new_status, project_id: {
            "found_count": 1,
            "updated_count": 1,
            "results": [{"id": single_id, "status": new_status, "success": True, "error": None}],
        },
    )

    resp = client.patch(
        "/api/v1/test-cases/status",
        json={
            "ids": [single_id],
            "status": TestCaseStatus.approved.value,
            "projectId": str(project_id),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["found_count"] == 1
    assert body["data"]["updated_count"] == 1
    assert body["data"]["results"][0]["id"] == single_id
    assert body["message"] == "Test case status update completed: 1 updated to 'approved'"


def test_update_status_endpoint_with_project_id_forwards_to_service(
    monkeypatch, client: TestClient
):
    target_id = str(uuid.uuid4())
    project_id = uuid.uuid4()
    captured = {}
    visibility_calls = []

    def _mock_visible_ids(_db, user_id):
        visibility_calls.append(user_id)
        return {project_id}

    monkeypatch.setattr(
        "app.api.dependencies.get_visible_project_ids",
        _mock_visible_ids,
    )

    def _mock_service(_db, *, test_case_ids, new_status, project_id):
        captured["test_case_ids"] = test_case_ids
        captured["new_status"] = new_status
        captured["project_id"] = project_id
        return {
            "found_count": 1,
            "updated_count": 1,
            "results": [{"id": target_id, "status": new_status, "success": True, "error": None}],
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.bulk_update_status_by_ids",
        _mock_service,
    )

    resp = client.patch(
        "/api/v1/test-cases/status",
        json={
            "ids": [target_id],
            "status": TestCaseStatus.approved.value,
            "projectId": str(project_id),
        },
    )
    assert resp.status_code == 200
    assert captured["project_id"] == project_id


def test_update_status_endpoint_bulk_approval_multiple_test_cases(monkeypatch, client: TestClient):
    ids = [str(uuid.uuid4()) for _ in range(5)]
    project_id = uuid.uuid4()
    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.bulk_update_status_by_ids",
        lambda _db, *, test_case_ids, new_status, project_id: {
            "found_count": len(ids),
            "updated_count": len(ids),
            "results": [
                {"id": cid, "status": new_status, "success": True, "error": None} for cid in ids
            ],
        },
    )

    resp = client.patch(
        "/api/v1/test-cases/status",
        json={"ids": ids, "status": TestCaseStatus.approved.value, "projectId": str(project_id)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["found_count"] == 5
    assert body["data"]["updated_count"] == 5
    assert len(body["data"]["results"]) == 5


def test_update_status_endpoint_bulk_approval_partial_failure(monkeypatch, client: TestClient):
    id_success = str(uuid.uuid4())
    id_failed = str(uuid.uuid4())
    project_id = uuid.uuid4()

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.bulk_update_status_by_ids",
        lambda _db, *, test_case_ids, new_status, project_id: {
            "found_count": 2,
            "updated_count": 1,
            "results": [
                {"id": id_success, "status": new_status, "success": True, "error": None},
                {
                    "id": id_failed,
                    "status": None,
                    "success": False,
                    "error": "transition rejected",
                },
            ],
        },
    )

    resp = client.patch(
        "/api/v1/test-cases/status",
        json={
            "ids": [id_success, id_failed],
            "status": TestCaseStatus.approved.value,
            "projectId": str(project_id),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["found_count"] == 2
    assert body["data"]["updated_count"] == 1
    assert body["data"]["results"][0]["success"] is True
    assert body["data"]["results"][1]["success"] is False
    assert body["data"]["results"][1]["error"] == "transition rejected"


def test_update_status_endpoint_forbidden_for_project_outside_visibility(
    monkeypatch, client: TestClient
):
    payload_project_id = uuid.uuid4()
    other_visible_project_id = uuid.uuid4()

    monkeypatch.setattr(
        "app.api.dependencies.get_visible_project_ids",
        lambda _db, _user_id: {other_visible_project_id},
    )

    def _mock_service(*_args, **_kwargs):
        raise AssertionError("service should not be called for an out-of-scope project_id")

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.bulk_update_status_by_ids",
        _mock_service,
    )

    resp = client.patch(
        "/api/v1/test-cases/status",
        json={
            "ids": [str(uuid.uuid4())],
            "status": TestCaseStatus.approved.value,
            "projectId": str(payload_project_id),
        },
    )
    assert resp.status_code == 403


def test_update_status_endpoint_forbidden_when_ids_belong_to_a_different_project(
    monkeypatch, client: TestClient
):
    declared_project_id = uuid.uuid4()
    foreign_project_id = uuid.uuid4()
    mixed_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    monkeypatch.setattr(
        "app.api.dependencies.get_visible_project_ids",
        lambda _db, _user_id: {declared_project_id, foreign_project_id},
    )
    monkeypatch.setattr(
        "app.api.dependencies.get_project_ids_for_test_case_ids",
        lambda _db, _ids: {declared_project_id, foreign_project_id},
    )

    def _mock_service(*_args, **_kwargs):
        raise AssertionError(
            "service should not be called when any id is out of the declared project"
        )

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.bulk_update_status_by_ids",
        _mock_service,
    )

    resp = client.patch(
        "/api/v1/test-cases/status",
        json={
            "ids": mixed_ids,
            "status": TestCaseStatus.approved.value,
            "projectId": str(declared_project_id),
        },
    )
    assert resp.status_code == 403


def test_update_status_endpoint_allowed_when_ids_all_belong_to_declared_project(
    monkeypatch, client: TestClient
):
    declared_project_id = uuid.uuid4()
    in_scope_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    monkeypatch.setattr(
        "app.api.dependencies.get_visible_project_ids",
        lambda _db, _user_id: {declared_project_id},
    )
    monkeypatch.setattr(
        "app.api.dependencies.get_project_ids_for_test_case_ids",
        lambda _db, _ids: {declared_project_id},
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.bulk_update_status_by_ids",
        lambda _db, *, test_case_ids, new_status, project_id: {
            "found_count": len(in_scope_ids),
            "updated_count": len(in_scope_ids),
            "results": [
                {"id": cid, "status": new_status, "success": True, "error": None}
                for cid in in_scope_ids
            ],
        },
    )

    resp = client.patch(
        "/api/v1/test-cases/status",
        json={
            "ids": in_scope_ids,
            "status": TestCaseStatus.approved.value,
            "projectId": str(declared_project_id),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["updated_count"] == len(in_scope_ids)


# ── get_project_test_case_summary ───────────────────────────────────────────


def test_get_project_test_case_summary_success(monkeypatch, client: TestClient):
    project_id = uuid.uuid4()
    expected_summary = {
        "total": 10,
        "approved": 6,
        "pending": 3,
        "archived": 1,
        "pass_rate": 60.0,
    }

    def _mock_count(_db, pid):
        assert pid == project_id
        return expected_summary

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.count_test_cases_by_project",
        _mock_count,
    )

    resp = client.get(f"/api/v1/test-cases/project/{project_id}/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "Test case summary retrieved successfully"
    assert body["data"]["total"] == 10
    assert body["data"]["approved"] == 6
    assert body["data"]["pending"] == 3
    assert body["data"]["archived"] == 1
    assert body["data"]["pass_rate"] == 60.0


def test_get_project_test_case_summary_invalid_project_id_returns_422(client: TestClient):
    resp = client.get("/api/v1/test-cases/project/not-a-uuid/summary")
    assert resp.status_code == 422


def test_get_project_test_case_summary_service_exception_propagates(
    monkeypatch, client: TestClient
):
    project_id = uuid.uuid4()

    def _mock_count(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.count_test_cases_by_project",
        _mock_count,
    )

    with pytest.raises(RuntimeError):
        client.get(f"/api/v1/test-cases/project/{project_id}/summary")


def test_get_project_test_case_summary_forbidden_for_project_outside_visibility(
    monkeypatch, client: TestClient
):
    project_id = uuid.uuid4()
    other_visible_project_id = uuid.uuid4()

    monkeypatch.setattr(
        "app.api.dependencies.get_visible_project_ids",
        lambda _db, _user_id: {other_visible_project_id},
    )

    def _mock_count(*_args, **_kwargs):
        raise AssertionError("service should not be called for an out-of-scope project_id")

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.count_test_cases_by_project",
        _mock_count,
    )

    resp = client.get(f"/api/v1/test-cases/project/{project_id}/summary")
    assert resp.status_code == 403
