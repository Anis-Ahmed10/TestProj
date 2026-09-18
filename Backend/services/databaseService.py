"""Database service layer."""

from sqlalchemy.orm import Session

from app.core.exceptions import AppException, DatabaseOperationException
from app.database.crud_jira_import import (
    get_existing_story_statuses,
    save_epics_and_stories,
)
from app.database.crud_story_edit_log import bulk_insert_edit_log
from app.database.crud_test_cases import bulk_save_test_cases
from app.schemas.user_stories import StoryEditRecordSchema


class DatabaseService:

    @staticmethod
    async def save_test_cases(
        request,
        db: Session,
    ):
        normalized_test_cases = [tc.normalize().model_dump() for tc in request.test_cases]

        result = bulk_save_test_cases(
            db=db,
            test_cases=normalized_test_cases,
            user_story_id=request.userStoryId,
            format_type=request.format,
            jira_push_results=[],
            created_by="system",
        )

        return {
            "saved_count": len(result.inserted),
            "saved_test_cases": result.inserted,
            "skipped": result.skipped,
            "failed": result.failed,
        }

    @staticmethod
    def save_selected_stories(db: Session, selected_epics, project_id) -> dict:
        if db is None:
            total = sum(len(e.user_stories) for e in selected_epics)
            return {
                "imported_count": total,
                "updated_count": 0,
                "failed_count": 0,
                "renamed": [],
            }

        payload = []
        for epic in selected_epics:
            payload.append(
                {
                    "epicId": epic.epicId,
                    "epicTitle": getattr(epic, "epicTitle", epic.epicId),
                    "user_stories": [
                        {
                            "storyId": s.storyId,
                            "storyTitle": s.storyTitle,
                            "description": s.description,
                            "acceptanceCriteria": s.acceptanceCriteria or "",
                            "issue_type": s.issue_type,
                            "priority": getattr(s, "priority", None),
                        }
                        for s in epic.user_stories
                    ],
                }
            )

        try:
            summary = save_epics_and_stories(db, payload, project_id=project_id)

            return {
                "success": True,
                "inserted": summary.inserted,
                "updated": summary.updated,
                "failed": summary.failed,
                "failed_reasons": summary.failed_reasons,
                "skipped": summary.skipped,
                "renamed": summary.renamed,
            }

        except AppException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise DatabaseOperationException(str(exc))

    @staticmethod
    def get_story_statuses(db: Session, project_id, story_keys: list[str]) -> dict:
        """Return existing DB status metadata keyed by story key, scoped to project.

        Reuses the same enrichment the Jira fetch applies, so Excel/CSV imports get
        the same already-exists / approved / rejected / pending_approval signals.
        """
        return get_existing_story_statuses(db, story_keys, project_id)

    @staticmethod
    def save_story_edit_log(db: Session, edit_log: list[StoryEditRecordSchema]) -> int:
        records = [
            {
                "storyId": r.storyId,
                "epicId": r.epicId,
                "changes": [c.model_dump() for c in r.changes],
                "editedAt": r.editedAt,
            }
            for r in edit_log
        ]
        return bulk_insert_edit_log(db=db, records=records)
