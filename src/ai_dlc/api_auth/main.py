from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException

from ai_dlc.inception.schemas import (
    RequirementRequest,
    DecisionRequest,
)
from ai_dlc.orchestrator.service import (
    submit_requirement,
    decide_workflow,
    retry_construction
)
from ai_dlc.persistence_audit.repository import (
    initialize,
    get_workflow,
    list_workflows,
    ensure_construction_columns
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Step 1: Create the original tables if they do not exist.
    initialize()

    # Step 2: Add Construction columns to the workflows table.
    ensure_construction_columns()

    # Step 3: Start serving API requests.
    yield
    yield


app = FastAPI(
    title="Custom AI-DLC Inception API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/requirements", status_code=201)
def create_requirement(request: RequirementRequest):
    try:
        return submit_requirement(request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        # Log the actual exception server-side in a production app.
        logger.exception("Story generation failed")
        raise HTTPException(
            status_code=502,
            detail="Story generation failed. Check server configuration and logs."
        )


@app.get("/api/workflows/{workflow_id}")
def read_workflow(workflow_id: str):
    workflow = get_workflow(workflow_id)

    if workflow is None:
        raise HTTPException(404, "Workflow not found.")

    return workflow

@app.get("/api/workflows")
def get_workflows():
    return list_workflows()


@app.post("/api/workflows/{workflow_id}/decision")
def make_decision(
    workflow_id: str,
    request: DecisionRequest,
):
    try:
        return decide_workflow(
            workflow_id,
            request.decision,
            request.reviewer,
            request.comment,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc



@app.post("/api/workflows/{workflow_id}/construction/retry")
def retry_construction_endpoint(workflow_id: str):
    try:
        return retry_construction(workflow_id)

    except ValueError as exc:
        message = str(exc)

        if message == "Workflow not found":
            raise HTTPException(status_code=404, detail=message) from exc

        raise HTTPException(status_code=409, detail=message) from exc
