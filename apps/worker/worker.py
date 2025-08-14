import os
from datetime import timedelta
from temporalio import workflow, activity
from temporalio.client import Client
from temporalio.worker import Worker
import httpx
import asyncio

TASK_QUEUE = "ai-csuite"

@activity.defn
async def act_ensure(owner: str, repo: str, branch: str, number: int | None = None) -> dict:
    base = os.getenv("ORCHESTRATOR_BASE", "http://orchestrator:8000")
    payload = {"owner": owner, "repo": repo, "branch": branch, "number": number}
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{base}/integrations/github/pr/ensure-artifacts", json=payload, timeout=60)
        r.raise_for_status()
        return r.json()

@workflow.defn
class RefreshArtifactsWorkflow:
    @workflow.run
    async def run(self, owner: str, repo: str, branch: str, number: int | None = None) -> dict:
        return await workflow.execute_activity(
            act_ensure, owner, repo, branch, number,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy={"maximum_attempts": 5}
        )

async def main():
    client = await Client.connect(os.getenv("TEMPORAL_HOSTPORT", "temporal:7233"))
    worker = Worker(client, task_queue=TASK_QUEUE, workflows=[RefreshArtifactsWorkflow], activities=[act_ensure])
    print("Worker started (Temporal)", flush=True)
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())


