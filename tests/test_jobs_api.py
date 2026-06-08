from __future__ import annotations

from fastapi.testclient import TestClient


def test_crawl_due_route_is_not_captured_by_job_id(client: TestClient) -> None:
    response = client.post("/jobs/crawl-due")

    assert response.status_code == 200
    assert response.json() == {"jobs_started": 0, "job_ids": []}

