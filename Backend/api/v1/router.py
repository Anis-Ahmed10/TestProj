"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    application_logs,
    automation_selector,
    clients,
    database_operations,
    file_operations,
    jira,
    programmes,
    projects,
    story_approvals,
    test_case_generator,
    test_cases,
    users,
)

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(test_case_generator.router)
api_router.include_router(automation_selector.router)
api_router.include_router(clients.router)
api_router.include_router(programmes.router)
api_router.include_router(projects.router)
api_router.include_router(file_operations.router, prefix="")


api_router.include_router(test_cases.router)

api_router.include_router(jira.router)
api_router.include_router(database_operations.router)
api_router.include_router(story_approvals.router)
api_router.include_router(users.router)
api_router.include_router(application_logs.router)
