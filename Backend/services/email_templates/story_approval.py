"""Email template for the story approval notification."""

from __future__ import annotations

from html import escape

from app.services.email_templates.layout import render_email_layout


def build_approval_notification(
    *,
    reviewer_emails: list[str],
    requestor_name: str,
    project_name: str,
    story_count: int,
    approval_link: str,
) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body) for the approval notification.

    All reviewers are recipients on the same email, and the body lists
    everyone it was sent to so each reviewer knows who else is reviewing.
    """
    subject = f"User Story Approval Required — {project_name}"
    html_body = render_email_layout(
        _build_body_rows(
            requestor_name=requestor_name,
            project_name=project_name,
            story_count=story_count,
            approval_link=approval_link,
            reviewer_emails=reviewer_emails,
        )
    )
    text_body = _build_text_body(
        requestor_name=requestor_name,
        project_name=project_name,
        story_count=story_count,
        approval_link=approval_link,
        reviewer_emails=reviewer_emails,
    )
    return subject, html_body, text_body


def build_decision_summary_notification(
    *,
    submitter_name: str,
    project_name: str,
    approved_keys: list[str],
    rejected_keys: list[str],
    review_link: str,
) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body) for the submitter's review-complete email.

    Sent once, when every story in a submission batch has been decided — a single
    summary rather than one email per story.
    """
    approved_count = len(approved_keys)
    rejected_count = len(rejected_keys)
    total = approved_count + rejected_count
    subject = (
        f"Your {total} submitted user "
        f"{'story has' if total == 1 else 'stories have'} been reviewed — {project_name}"
    )
    html_body = render_email_layout(
        _build_decision_body_rows(
            submitter_name=submitter_name,
            project_name=project_name,
            approved_keys=approved_keys,
            rejected_keys=rejected_keys,
            review_link=review_link,
        )
    )
    text_body = _build_decision_text_body(
        submitter_name=submitter_name,
        project_name=project_name,
        approved_keys=approved_keys,
        rejected_keys=rejected_keys,
        review_link=review_link,
    )
    return subject, html_body, text_body


def _build_decision_text_body(
    *,
    submitter_name: str,
    project_name: str,
    approved_keys: list[str],
    rejected_keys: list[str],
    review_link: str,
) -> str:
    lines = [
        f"Hi {submitter_name},",
        "",
        f'Your submitted user stories in project "{project_name}" have been reviewed.',
        "",
        f"Approved ({len(approved_keys)}): "
        + (", ".join(approved_keys) if approved_keys else "none"),
        f"Rejected ({len(rejected_keys)}): "
        + (", ".join(rejected_keys) if rejected_keys else "none"),
        "",
    ]
    if rejected_keys:
        lines.append("Rejected stories can be revised and re-submitted for approval.")
        lines.append("")
    lines.append(f"Open the test generator: {review_link}")
    lines.append("")
    lines.append("Thank you.")
    return "\n".join(lines)


def _build_decision_list_html(label: str, keys: list[str], color: str) -> str:
    if not keys:
        return ""
    items = ", ".join(escape(key) for key in keys)
    return f"""\
                <p style="margin:0 0 12px; font-size:13px; line-height:1.6; color:#374151;">
                  <strong style="color:{color};">{label} ({len(keys)}):</strong> {items}
                </p>"""


def _build_decision_body_rows(
    *,
    submitter_name: str,
    project_name: str,
    approved_keys: list[str],
    rejected_keys: list[str],
    review_link: str,
) -> str:
    safe_submitter_name = escape(submitter_name)
    safe_project_name = escape(project_name)
    approved_html = _build_decision_list_html("Approved", approved_keys, "#1f7a52")
    rejected_html = _build_decision_list_html("Rejected", rejected_keys, "#b42318")
    rejected_note = (
        """
                <p style="margin:8px 0 0; font-size:12px; line-height:1.6; color:#6b7280;">
                  Rejected stories can be revised and re-submitted for approval.
                </p>"""
        if rejected_keys
        else ""
    )
    return f"""\
            <tr>
              <td style="padding:32px 28px 8px;">
                <h1 style="margin:0 0 16px; font-size:19px; font-weight:700;
                  color:#0f2623; letter-spacing:-0.3px;">
                  Your Submission Has Been Reviewed
                </h1>
                <p style="margin:0 0 20px; font-size:14px; line-height:1.6; color:#374151;">
                  Hi <strong>{safe_submitter_name}</strong>, your submitted user stories
                  in project &quot;<strong>{safe_project_name}</strong>&quot; have been
                  reviewed.
                </p>
{approved_html}
{rejected_html}
                {rejected_note}
              </td>
            </tr>
            <tr>
              <td style="padding:16px 28px 28px;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td style="border-radius:8px; background-color:#1f5c54;">
                      <a href="{review_link}" style="display:inline-block;
                        padding:11px 24px; font-size:14px; font-weight:600;
                        color:#ffffff; text-decoration:none; border-radius:8px;">
                        Open Test Generator
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>"""


def _build_text_body(
    *,
    requestor_name: str,
    project_name: str,
    story_count: int,
    approval_link: str,
    reviewer_emails: list[str],
) -> str:
    reviewers_line = ", ".join(reviewer_emails)
    return (
        f"Hi,\n\n"
        f"{requestor_name} has submitted {story_count} user "
        f"{'story' if story_count == 1 else 'stories'} for your approval "
        f'in project "{project_name}".\n\n'
        f"Assigned reviewer{'s' if len(reviewer_emails) != 1 else ''}: "
        f"{reviewers_line}\n\n"
        f"Please review and approve at: {approval_link}\n\n"
        f"Thank you."
    )


def _build_body_rows(
    *,
    requestor_name: str,
    project_name: str,
    story_count: int,
    approval_link: str,
    reviewer_emails: list[str],
) -> str:
    story_label = "story" if story_count == 1 else "stories"
    reviewer_label = "Assigned reviewer" if len(reviewer_emails) == 1 else "Assigned reviewers"
    reviewers_line = ", ".join(escape(email) for email in reviewer_emails)
    safe_requestor_name = escape(requestor_name)
    safe_project_name = escape(project_name)
    return f"""\
            <tr>
              <td style="padding:32px 28px 8px;">
                <h1 style="margin:0 0 16px; font-size:19px; font-weight:700;
                  color:#0f2623; letter-spacing:-0.3px;">
                  User Story Approval Request
                </h1>
                <p style="margin:0 0 20px; font-size:14px; line-height:1.6; color:#374151;">
                  <strong>{safe_requestor_name}</strong> has submitted
                  <strong>{story_count}</strong> user {story_label}
                  for your approval in project &quot;<strong>{safe_project_name}</strong>&quot;.
                </p>
                <p style="margin:0 0 20px; font-size:12px; line-height:1.6; color:#6b7280;">
                  {reviewer_label}: {reviewers_line}
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:4px 28px 28px;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td style="border-radius:8px; background-color:#1f5c54;">
                      <a href="{approval_link}" style="display:inline-block;
                        padding:11px 24px; font-size:14px; font-weight:600;
                        color:#ffffff; text-decoration:none; border-radius:8px;">
                        Review and Approve
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:0 28px 28px;">
                <div style="background-color:#f0f9f7; border-radius:8px;
                  padding:12px 14px; font-size:12px; color:#1f5c54;">
                  If the button above doesn't work, copy and paste this link
                  into your browser:<br />
                  <a href="{approval_link}" style="color:#1f5c54;
                    word-break:break-all;">{approval_link}</a>
                </div>
              </td>
            </tr>"""
