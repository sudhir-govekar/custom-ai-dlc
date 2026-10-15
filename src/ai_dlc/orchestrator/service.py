from ai_dlc.inception.generator import generate_story
from ai_dlc.inception.schemas import RequirementRequest
from ai_dlc.persistence_audit.repository import (
    create_workflow,
    get_workflow,
    record_decision,
    mark_construction_started,
    save_construction_result,
    mark_construction_failed
)
from ai_dlc.construction.generator import generate_construction_plan
import logging
import json

logger = logging.getLogger(__name__)
def submit_requirement(request: RequirementRequest) -> dict:
    story = generate_story(request)

    if not story.acceptance_criteria:
        raise ValueError(
            "Story generation returned no acceptance criteria."
        )

    return create_workflow(
        request,
        story.model_dump(mode="json"),
    )


# def decide_workflow(
#     workflow_id: str,
#     decision: str,
#     reviewer: str,
#     comment: str = "",
# ) -> dict:
#     workflow = get_workflow(workflow_id)

#     if workflow is None:
#         raise LookupError("Workflow not found.")

#     if workflow["status"] != "pending_approval":
#         raise ValueError("Workflow has already been decided.")

#     if (
#         decision == "approve"
#         and workflow["artifacts"]["open_questions"]
#     ):
#         raise ValueError(
#             "Resolve open questions before approving."
#         )

#     updated = record_decision(
#         workflow_id, decision, reviewer, comment
#     )

#     if updated is None:
#         raise ValueError(
#             "Workflow status changed. Reload and try again."
#         )

#     return updated


# def decide_workflow(workflow_id: str, decision):
#     workflow = get_workflow(workflow_id)

#     if not workflow:
#         raise ValueError("Workflow not found")

#     if workflow["status"] != "pending_approval":
#         raise ValueError("Workflow is not pending approval")

#     # Do not block approval merely because open questions exist.
#     record_decision(workflow_id, decision)

#     if decision.decision == "reject":
#         # Keep your existing rejection behavior.
#         return get_workflow(workflow_id)

#     # Approval is already recorded. Construction is a separate stage.
#     started = mark_construction_started(workflow_id)

#     if not started:
#         return get_workflow(workflow_id)

#     try:
#         approved_workflow = get_workflow(workflow_id)

#         # Adjust this field if your repository exposes artifacts
#         # under a different key.
#         artifacts = approved_workflow.get("artifacts")

#         if not artifacts:
#             import json
#             artifacts = json.loads(
#                 approved_workflow.get("artifacts_json") or "{}"
#             )

#         plan = generate_construction_plan(
#             project=approved_workflow["project"],
#             service=approved_workflow["service"],
#             requirement=approved_workflow["requirement"],
#             approved_story=artifacts,
#             reviewer=decision.reviewer,
#             review_comment=decision.comment,
#         )

#         save_construction_result(workflow_id, plan)

#     except Exception:
#         import logging
#         logger = logging.getLogger(__name__)
#         logger.exception(
#             "Construction generation failed for workflow %s",
#             workflow_id,
#         )

#         mark_construction_failed(
#             workflow_id,
#             "Construction plan generation failed. "
#             "Check server logs for details.",
#         )

#         # Do not undo a valid approval because a later stage failed.

#     return get_workflow(workflow_id)




def decide_workflow(
    workflow_id: str,
    decision: str,
    reviewer: str,
    comment: str = "",
):
    workflow = get_workflow(workflow_id)

    if not workflow:
        raise ValueError("Workflow not found")

    if workflow["status"] != "pending_approval":
        raise ValueError("Workflow is not pending approval")

    # Save the human decision first.
    record_decision(
        workflow_id,
        decision,
        reviewer,
        comment,
    )

    if decision == "reject":
        return get_workflow(workflow_id)

    if decision != "approve":
        raise ValueError("Decision must be approve or reject")

    # Start Construction only after approval is recorded.
    started = mark_construction_started(workflow_id)

    if not started:
        return get_workflow(workflow_id)

    try:
        approved_workflow = get_workflow(workflow_id)

        artifacts = approved_workflow.get("artifacts")

        if not artifacts:
            import json
            artifacts = json.loads(
                approved_workflow.get("artifacts_json") or "{}"
            )

        plan = generate_construction_plan(
            project=approved_workflow["project"],
            service=approved_workflow["service"],
            requirement=approved_workflow["requirement"],
            approved_story=artifacts,
            reviewer=reviewer,
            review_comment=comment,
        )

        save_construction_result(workflow_id, plan)

    except Exception:
        logger.exception(
            "Construction generation failed for workflow %s",
            workflow_id,
        )
        mark_construction_failed(
            workflow_id,
            "Construction plan generation failed. "
            "Check server logs for details.",
        )

    return get_workflow(workflow_id)

def retry_construction(workflow_id: str):
    """Retry Construction for an approved workflow."""

    workflow = get_workflow(workflow_id)

    if not workflow:
        raise ValueError("Workflow not found")

    if workflow["status"] != "approved":
        raise ValueError(
            "Construction can only be retried for approved workflows"
        )

    construction_status = workflow.get(
        "construction_status", "not_started"
    )

    if construction_status not in {"failed", "not_started"}:
        raise ValueError(
            f"Cannot retry Construction when status is "
            f"'{construction_status}'"
        )

    # Atomically claim the workflow before calling the LLM.
    started = mark_construction_started(workflow_id)

    if not started:
        raise ValueError(
            "Construction could not be started. "
            "It may already be running or completed."
        )

    try:
        # Reload the approved workflow after claiming it.
        workflow = get_workflow(workflow_id)

        artifacts = workflow.get("artifacts")

        if not artifacts:
            artifacts = json.loads(
                workflow.get("artifacts_json") or "{}"
            )

        plan = generate_construction_plan(
            project=workflow["project"],
            service=workflow["service"],
            requirement=workflow["requirement"],
            approved_story=artifacts,
            reviewer=workflow.get("reviewer") or "Unknown",
            review_comment=workflow.get("decision_comment") or "",
        )

        save_construction_result(workflow_id, plan)

        return get_workflow(workflow_id)

    except Exception:
        logger.exception(
            "Construction retry failed for workflow %s",
            workflow_id,
        )

        mark_construction_failed(
            workflow_id,
            "Construction generation failed. Check server logs.",
        )

        # Preserve the original approval and allow another retry.
        return get_workflow(workflow_id)


