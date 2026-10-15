
import json
import os

import requests
import streamlit as st
from dotenv import load_dotenv


# ============================================================
# Configuration
# ============================================================

load_dotenv()

API_URL = os.getenv(
    "AI_DLC_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

REQUEST_TIMEOUT = 120

st.set_page_config(
    page_title="Custom AI-DLC",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# API helpers
# ============================================================

def api_get(path):
    """GET data from FastAPI without caching stale workflow status."""
    try:
        response = requests.get(
            f"{API_URL}{path}",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    except requests.Timeout:
        st.error("The API request timed out.")
    except requests.RequestException as exc:
        st.error(f"API request failed: {exc}")
    except ValueError:
        st.error("The API returned invalid JSON.")

    return None


def api_post(path, payload):
    """POST data to FastAPI and show meaningful errors."""
    try:
        response = requests.post(
            f"{API_URL}{path}",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if not response.ok:
            try:
                body = response.json()
                detail = body.get("detail", body)
            except ValueError:
                detail = response.text

            st.error(
                f"Request failed (HTTP {response.status_code}): "
                f"{detail}"
            )
            return None

        if not response.content:
            return {}

        return response.json()

    except requests.Timeout:
        st.warning(
            "The request timed out. The server may still be processing "
            "it. Refresh the workflow before submitting another action."
        )
    except requests.RequestException as exc:
        st.error(f"Cannot connect to {API_URL}: {exc}")
    except ValueError:
        st.error("The API returned invalid JSON.")

    return None


def load_workflows():
    result = api_get("/api/workflows")

    if result is None:
        return None

    if isinstance(result, list):
        return result

    if isinstance(result, dict):
        items = result.get("workflows", [])
        if isinstance(items, list):
            return items

    st.error("Unexpected response from GET /api/workflows.")
    return None


def load_workflow_details(workflow_id):
    result = api_get(f"/api/workflows/{workflow_id}")

    if result is None:
        return None

    if isinstance(result, dict) and isinstance(
        result.get("workflow"), dict
    ):
        return result["workflow"]

    return result if isinstance(result, dict) else None


# ============================================================
# Data helpers
# ============================================================

def workflow_id_of(workflow):
    value = workflow.get("id")
    return str(value) if value is not None else ""


def workflow_status(workflow):
    return str(workflow.get("status") or "unknown").lower()


def construction_status(workflow):
    return str(
        workflow.get("construction_status") or "not_started"
    ).lower()


def parse_object(value):
    """Accept a dictionary or JSON-encoded string."""
    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}

    return {}


def get_artifacts(workflow):
    return parse_object(
        workflow.get("artifacts")
        or workflow.get("artifacts_json")
    )


def get_construction_plan(workflow):
    return parse_object(
        workflow.get("construction")
        or workflow.get("construction_json")
    )


def refresh_dashboard():
    st.session_state["dashboard_refresh"] = (
        st.session_state.get("dashboard_refresh", 0) + 1
    )
    st.rerun()


def workflow_label(workflow):
    return (
        f"{workflow.get('project', 'Project')} | "
        f"{workflow.get('service', 'Service')} | "
        f"{workflow_status(workflow)} | "
        f"ID {workflow_id_of(workflow)}"
    )


# ============================================================
# Status display
# ============================================================

def show_workflow_status(workflow):
    status = workflow_status(workflow)

    if status == "approved":
        st.success("Workflow: Approved")
    elif status == "rejected":
        st.error("Workflow: Rejected")
    elif status == "pending_approval":
        st.warning("Workflow: Pending approval")
    elif status == "revision_requested":
        st.warning("Workflow: Revision requested")
    else:
        st.info(f"Workflow: {status.replace('_', ' ').title()}")


def show_construction_status(workflow):
    status = construction_status(workflow)

    if status == "completed":
        st.success("Construction: Completed")
    elif status == "in_progress":
        st.info("Construction: In progress")
    elif status == "failed":
        st.error("Construction: Failed")
        if workflow.get("construction_error"):
            st.caption(workflow["construction_error"])
    else:
        st.info("Construction: Not started")

    return status


# ============================================================
# Inception rendering
# ============================================================

def render_story(artifacts):
    if not artifacts:
        st.info("No generated story is available.")
        return

    st.markdown("#### User story")
    st.markdown(f"**{artifacts.get('title', 'Untitled story')}**")
    st.write(artifacts.get("user_story", "Not provided"))

    if artifacts.get("business_value"):
        st.markdown("#### Business value")
        st.write(artifacts["business_value"])

    if artifacts.get("priority"):
        st.caption(f"Priority: {artifacts['priority']}")

    requirements = artifacts.get("functional_requirements", [])

    if requirements:
        st.markdown("#### Functional requirements")
        for requirement in requirements:
            st.markdown(f"- {requirement}")

    st.markdown("#### Acceptance criteria")

    criteria = artifacts.get("acceptance_criteria", [])

    if not criteria:
        st.info("No acceptance criteria available.")

    for index, criterion in enumerate(criteria, start=1):
        if not isinstance(criterion, dict):
            st.write(criterion)
            continue

        criterion_id = criterion.get("id", f"AC-{index}")
        title = criterion.get("title", "Acceptance criterion")

        with st.expander(f"{criterion_id} — {title}"):
            for key in ("given", "when", "then"):
                if criterion.get(key):
                    st.markdown(f"**{key.title()}**")
                    st.write(criterion[key])

    st.markdown("#### Open questions")

    questions = artifacts.get("open_questions", [])

    if questions:
        st.caption(
            "Open questions are displayed for review. Approval is "
            "controlled by the backend and does not have to be blocked "
            "by unresolved questions."
        )
        for question in questions:
            st.markdown(f"- {question}")
    else:
        st.write("No open questions.")


# ============================================================
# Construction rendering
# ============================================================

def render_construction_plan(plan):
    if not plan:
        st.info("No Construction plan is stored.")
        return

    st.markdown("#### Technical design")
    st.write(plan.get("technical_design", "Not provided"))

    sections = [
        ("Architecture decisions", "architecture_decisions"),
        ("Affected components", "affected_components"),
        ("Assumptions", "assumptions"),
        ("Risks", "risks"),
    ]

    for title, key in sections:
        st.markdown(f"#### {title}")
        values = plan.get(key, [])

        if values:
            for value in values:
                st.markdown(f"- {value}")
        else:
            st.write("None recorded.")

    st.markdown("#### Implementation tasks")
    tasks = plan.get("tasks", [])

    if not tasks:
        st.info("The plan contains no implementation tasks.")

    for task in tasks:
        if not isinstance(task, dict):
            st.write(task)
            continue

        task_id = task.get("task_id", "TASK")
        title = task.get("title", "Untitled task")

        with st.expander(f"{task_id} — {title}"):
            st.markdown("**Description**")
            st.write(task.get("description", "Not provided"))

            st.markdown("**Target service**")
            st.write(task.get("service", "Not specified"))

            st.markdown("**Dependencies**")
            st.write(task.get("dependencies", []))

            st.markdown("**Acceptance criteria covered**")
            st.write(task.get("acceptance_criteria_ids", []))

            st.markdown("**Test plan**")
            tests = task.get("test_plan", [])

            if tests:
                for test in tests:
                    st.markdown(f"- {test}")
            else:
                st.write("No test plan provided.")

    st.markdown("#### Implementation order")
    st.write(plan.get("implementation_order", []))

    st.markdown("#### Overall test strategy")
    st.write(plan.get("overall_test_strategy", "Not provided"))

    st.caption(
        "This is an AI-generated Construction plan. It does not mean "
        "that code changes or tests have been executed."
    )


# ============================================================
# Complete workflow details
# ============================================================

def render_workflow_details(workflow):
    st.markdown("### Workflow details")

    first, second, third = st.columns(3)

    first.metric("Workflow ID", workflow_id_of(workflow) or "Unknown")
    second.metric("Workflow status", workflow_status(workflow))
    third.metric(
        "Construction status",
        construction_status(workflow),
    )

    details = [
        ("Project", "project"),
        ("Service", "service"),
        ("Original requirement", "requirement"),
        ("Reviewer", "reviewer"),
        ("Decision comment", "decision_comment"),
        ("Created at", "created_at"),
        ("Updated at", "updated_at"),
    ]

    for label, key in details:
        st.markdown(f"**{label}**")
        st.write(workflow.get(key) or "Not available")

    with st.expander("Inception artifacts", expanded=True):
        render_story(get_artifacts(workflow))

    with st.expander("Construction artifacts", expanded=True):
        status = show_construction_status(workflow)
        plan = get_construction_plan(workflow)

        if status == "completed" and not plan:
            st.warning(
                "The backend reports Construction as completed, but "
                "no plan was returned. Check construction_json in the "
                "same SQLite database used by FastAPI."
            )
        else:
            render_construction_plan(plan)

        if status == "failed":
            st.error(
                workflow.get("construction_error")
                or "Construction generation failed. Check server logs."
            )

    with st.expander("Complete stored workflow record"):
        st.json(workflow, expanded=True)


# ============================================================
# Tables and workflow selection
# ============================================================

def render_workflow_table(workflows):
    rows = [
        {
            "ID": workflow_id_of(w),
            "Project": w.get("project", ""),
            "Service": w.get("service", ""),
            "Workflow status": workflow_status(w),
            "Construction status": construction_status(w),
            "Created": w.get("created_at", ""),
            "Updated": w.get("updated_at", ""),
        }
        for w in workflows
    ]

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )


def render_workflow_selector(workflows, key_prefix):
    if not workflows:
        st.info("No workflows available in this section.")
        return

    options = {
        workflow_label(w): workflow_id_of(w)
        for w in workflows
        if workflow_id_of(w)
    }

    if not options:
        st.info("No workflows have valid IDs.")
        return

    labels = list(options.keys())

    selected_label = st.selectbox(
        "Select a workflow",
        labels,
        key=f"{key_prefix}_selector",
    )

    selected_id = options[selected_label]

    if st.button(
        "Show more",
        key=f"{key_prefix}_show_more",
    ):
        st.session_state[f"{key_prefix}_details_id"] = selected_id

    details_id = st.session_state.get(f"{key_prefix}_details_id")

    # Show details only if the selected record belongs to this section.
    valid_ids = set(options.values())

    if details_id and str(details_id) in valid_ids:
        st.divider()

        details = load_workflow_details(details_id)

        if details:
            render_workflow_details(details)


# ============================================================
# Header and sidebar
# ============================================================

st.title("🚀 Custom AI-DLC")
st.caption(
    "Requirement intake · Human approval · Construction planning · "
    "Workflow history"
)

with st.sidebar:
    st.subheader("Framework")
    st.caption(f"FastAPI: {API_URL}")

    if st.button("Refresh dashboard", use_container_width=True):
        refresh_dashboard()

    if st.button("Check API health", use_container_width=True):
        health = api_get("/health")

        if health is not None:
            st.success("FastAPI is reachable.")
            st.json(health)


# ============================================================
# Separate lifecycle tabs
# ============================================================

inception_tab, construction_tab, verification_tab, operations_tab, history_tab = (
    st.tabs(
        [
            "1. Inception",
            "2. Construction",
            "3. Verification",
            "4. Operations",
            "5. Workflow History",
        ]
    )
)


# ============================================================
# TAB 1: INCEPTION
# ============================================================

with inception_tab:
    st.header("Inception")
    st.caption(
        "Submit a requirement, generate a story, review it, and "
        "approve or reject it."
    )

    with st.form("requirement_form", clear_on_submit=False):
        project = st.text_input(
            "Project",
            placeholder="Healthcare Platform",
        )

        service = st.text_input(
            "Service",
            placeholder="member-service",
        )

        requirement = st.text_area(
            "Requirement",
            height=160,
            placeholder=(
                "Describe the feature, business rules, authorization, "
                "error handling, and testing requirements."
            ),
        )

        submit_requirement = st.form_submit_button(
            "Generate user story",
            type="primary",
        )

    if submit_requirement:
        if not project.strip() or not service.strip():
            st.error("Project and service are required.")
        elif len(requirement.strip()) < 20:
            st.error("Requirement must contain at least 20 characters.")
        else:
            with st.spinner("Generating user story..."):
                result = api_post(
                    "/api/requirements",
                    {
                        "project": project.strip(),
                        "service": service.strip(),
                        "requirement": requirement.strip(),
                    },
                )

            if result is not None:
                workflow = result.get("workflow", result)
                workflow_id = workflow.get("id")

                if workflow_id is not None:
                    st.session_state["latest_workflow_id"] = str(
                        workflow_id
                    )

                st.success("Requirement submitted.")

                if workflow_id is not None:
                    st.caption(f"Workflow ID: {workflow_id}")

                render_story(get_artifacts(workflow))

    st.divider()
    st.subheader("Pending approval")

    workflows = load_workflows()

    if workflows is not None:
        pending = [
            w for w in workflows
            if workflow_status(w) == "pending_approval"
        ]

        if not pending:
            st.info("No stories are awaiting approval.")
        else:
            render_workflow_table(pending)

            pending_options = {
                workflow_label(w): workflow_id_of(w)
                for w in pending
                if workflow_id_of(w)
            }

            if pending_options:
                selected_label = st.selectbox(
                    "Select a story to review",
                    list(pending_options.keys()),
                    key="inception_review_selector",
                )

                workflow_id = pending_options[selected_label]
                details = load_workflow_details(workflow_id)

                if details:
                    show_workflow_status(details)
                    render_story(get_artifacts(details))

                    reviewer = st.text_input(
                        "Reviewer",
                        key="inception_reviewer",
                        placeholder="Reviewer name",
                    )

                    comment = st.text_area(
                        "Review comments",
                        key="inception_review_comment",
                        placeholder=(
                            "Add feedback, assumptions, or rejection reason."
                        ),
                    )

                    approve_col, reject_col = st.columns(2)

                    with approve_col:
                        if st.button(
                            "Approve and start Construction",
                            type="primary",
                            use_container_width=True,
                            key="approve_story",
                        ):
                            if len(reviewer.strip()) < 2:
                                st.error("Enter a reviewer name.")
                            else:
                                with st.spinner(
                                    "Saving approval and generating "
                                    "the Construction plan..."
                                ):
                                    result = api_post(
                                        f"/api/workflows/{workflow_id}/decision",
                                        {
                                            "decision": "approve",
                                            "reviewer": reviewer.strip(),
                                            "comment": comment.strip(),
                                        },
                                    )

                                if result is not None:
                                    st.success("Approval request processed.")
                                    st.rerun()

                    with reject_col:
                        if st.button(
                            "Reject story",
                            use_container_width=True,
                            key="reject_story",
                        ):
                            if len(reviewer.strip()) < 2:
                                st.error("Enter a reviewer name.")
                            elif not comment.strip():
                                st.error("Provide a rejection reason.")
                            else:
                                result = api_post(
                                    f"/api/workflows/{workflow_id}/decision",
                                    {
                                        "decision": "reject",
                                        "reviewer": reviewer.strip(),
                                        "comment": comment.strip(),
                                    },
                                )

                                if result is not None:
                                    st.success("Story rejected.")
                                    st.rerun()


# ============================================================
# TAB 2: CONSTRUCTION
# ============================================================

with construction_tab:
    st.header("Construction")
    st.caption(
        "Review the technical design, implementation tasks, "
        "dependencies, and test strategy generated after approval."
    )

    workflows = load_workflows()

    if workflows is not None:
        approved = [
            w for w in workflows
            if workflow_status(w) == "approved"
        ]

        if not approved:
            st.info(
                "No approved workflows yet. Approve a story in Inception "
                "to begin Construction."
            )
        else:
            render_workflow_table(approved)

            construction_options = {
                workflow_label(w): workflow_id_of(w)
                for w in approved
                if workflow_id_of(w)
            }

            if construction_options:
                selected_label = st.selectbox(
                    "Select an approved workflow",
                    list(construction_options.keys()),
                    key="construction_selector",
                )

                workflow_id = construction_options[selected_label]

                # Always fetch fresh details rather than relying on the
                # older workflow list's status.
                details = load_workflow_details(workflow_id)

                if details:
                    st.divider()
                    show_workflow_status(details)

                    status = show_construction_status(details)
                    plan = get_construction_plan(details)

                    if status == "completed":
                        if plan:
                            st.success(
                                "Construction plan is completed and "
                                "the API returned a saved plan."
                            )
                            render_construction_plan(plan)
                        else:
                            st.warning(
                                "The backend reports completed, but the "
                                "plan is missing from the API response. "
                                "Check construction_json and confirm that "
                                "GET /api/workflows/{id} returns it. "
                                "Retry is disabled because the backend "
                                "already considers this workflow completed."
                            )

                    elif status == "in_progress":
                        st.info(
                            "Construction generation is in progress. "
                            "Refresh the dashboard to see the latest status."
                        )

                    elif status in {"failed", "not_started"}:
                        if status == "failed":
                            st.error(
                                details.get("construction_error")
                                or "Construction generation failed."
                            )
                            if plan:
                                st.markdown("#### Last saved plan")
                                render_construction_plan(plan)
                        else:
                            st.info(
                                "Construction has not started. If the story "
                                "was just approved, refresh to check the "
                                "latest status."
                            )

                        if st.button(
                            "Retry Construction",
                            type="primary",
                            key=f"retry_construction_{workflow_id}",
                        ):
                            with st.spinner(
                                "Generating and saving Construction plan..."
                            ):
                                result = api_post(
                                    f"/api/workflows/{workflow_id}/construction/retry",
                                    {},
                                )

                            if result is not None:
                                # Reload from GET, rather than assuming
                                # the POST response has the latest fields.
                                fresh = load_workflow_details(workflow_id)

                                if fresh:
                                    fresh_status = construction_status(fresh)

                                    if fresh_status == "completed":
                                        if get_construction_plan(fresh):
                                            st.success(
                                                "Construction completed "
                                                "and the plan was returned."
                                            )
                                        else:
                                            st.warning(
                                                "Status is completed, but "
                                                "the plan was not returned "
                                                "by the API."
                                            )
                                    elif fresh_status == "failed":
                                        st.error(
                                            fresh.get("construction_error")
                                            or "Construction retry failed."
                                        )
                                    else:
                                        st.info(
                                            "Latest Construction status: "
                                            f"{fresh_status}"
                                        )

                                st.rerun()

                    else:
                        st.warning(
                            f"Unexpected Construction status: {status}"
                        )


# ============================================================
# TAB 3: VERIFICATION
# ============================================================

with verification_tab:
    st.header("Verification & Review")

    st.info(
        "This stage is not implemented yet. Construction currently "
        "generates a plan; it does not execute code or tests."
    )

    st.markdown(
        """
        Planned capabilities:

        - Run configured tests and lint checks.
        - Map verification results to acceptance criteria.
        - Record test output and verification evidence.
        - Flag missing test coverage.
        - Require review before the next lifecycle transition.
        """
    )


# ============================================================
# TAB 4: OPERATIONS
# ============================================================

with operations_tab:
    st.header("Operations")

    st.info(
        "This stage is not implemented yet. No deployment or automated "
        "remediation is performed by the current workflow."
    )

    st.markdown(
        """
        Planned capabilities:

        - Deployment readiness checks.
        - Service health and error monitoring.
        - Cost and operational risk analysis.
        - Human approval for sensitive remediation.
        - Auditable operational actions.
        """
    )


# ============================================================
# TAB 5: WORKFLOW HISTORY
# ============================================================

with history_tab:
    st.header("Workflow History")
    st.caption(
        "Browse previous workflows, reviewer decisions, and saved "
        "Inception and Construction results."
    )

    workflows = load_workflows()

    if workflows is not None:
        if not workflows:
            st.info("No workflows have been saved yet.")
        else:
            statuses = sorted({
                workflow_status(w)
                for w in workflows
            })

            selected_statuses = st.multiselect(
                "Filter by workflow status",
                options=statuses,
                default=statuses,
                key="history_status_filter",
            )

            filtered = [
                w for w in workflows
                if workflow_status(w) in selected_statuses
            ]

            st.caption(f"{len(filtered)} workflow(s) found.")

            if filtered:
                render_workflow_table(filtered)
                render_workflow_selector(filtered, "history")
            else:
                st.info("No workflows match the selected filters.")
