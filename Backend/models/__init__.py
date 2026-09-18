"""SQLAlchemy model imports — ensures all tables are registered with Base.metadata."""

from app.models.document_models import Document  # noqa: F401
from app.models.rbac_models import (  # noqa: F401
    PermissionModel,
    RoleModel,
    role_permissions,
)
from app.models.story_approval_model import StoryApprovalRequest  # noqa: F401
from app.models.story_edit_log_model import StoryEditLog  # noqa: F401
from app.models.test_cases_model import TestCase  # noqa: F401
from app.models.users_models import User  # noqa: F401
