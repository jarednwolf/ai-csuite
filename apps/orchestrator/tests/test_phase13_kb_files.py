from fastapi.testclient import TestClient
from orchestrator.app import app
import base64

TENANT = "00000000-0000-0000-0000-000000000000"


def _build_minimal_pdf_bytes(text: str) -> bytes:
    # Deterministic, tiny PDF with given text as a single page content.
    # This is a hand-crafted minimal PDF, valid enough for pypdf to parse.
    # It encodes the provided text using a simple text object.
    safe = text.replace("(", "[").replace(")", "]")
    pdf = f"""%PDF-1.4\n1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>> endobj\n4 0 obj <</Length 67>> stream\nBT /F1 12 Tf 50 150 Td ({safe}) Tj ET\nendstream endobj\n5 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\nxref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000114 00000 n \n0000000225 00000 n \n0000000332 00000 n \ntrailer <</Size 6/Root 1 0 R>>\nstartxref\n412\n%%EOF\n""".encode("utf-8")
    return pdf


def test_kb_ingest_markdown_and_search():
    c = TestClient(app)
    # Create project
    p = c.post("/projects", json={"tenant_id": TENANT, "name": "KB Files", "description": "", "repo_url": ""})
    assert p.status_code == 200, p.text
    proj_id = p.json()["id"]

    unique = "mxk-unique-markdown-token-12345"
    md_text = f"""
    # Guide
    This is a guide about usage. It includes a special keyword {unique} in the body.
    ```
    code block should be ignored
    ```
    """.strip()

    ing = c.post("/kb/ingest-file", json={
        "tenant_id": TENANT,
        "project_id": proj_id,
        "filename": "guide.md",
        "content_type": "markdown",
        "text": md_text,
    })
    assert ing.status_code == 200, ing.text
    assert ing.json()["chunks"] > 0
    assert ing.json()["kind"] == "file-md"

    srch = c.get("/kb/search", params={"tenant_id": TENANT, "project_id": proj_id, "q": unique, "k": 5})
    assert srch.status_code == 200, srch.text
    hits = srch.json()
    assert len(hits) >= 1
    assert any(h["ref_id"] == "guide.md" or h["kind"] == "file-md" for h in hits)


def test_kb_ingest_pdf_and_search():
    c = TestClient(app)
    # Create project
    p = c.post("/projects", json={"tenant_id": TENANT, "name": "KB PDFs", "description": "", "repo_url": ""})
    assert p.status_code == 200, p.text
    proj_id = p.json()["id"]

    phrase = "pz-unique-pdf-phrase-67890"
    pdf_bytes = _build_minimal_pdf_bytes(f"Spec includes {phrase} for testing.")
    content_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    ing = c.post("/kb/ingest-file", json={
        "tenant_id": TENANT,
        "project_id": proj_id,
        "filename": "spec.pdf",
        "content_type": "pdf",
        "content_b64": content_b64,
    })
    assert ing.status_code == 200, ing.text
    assert ing.json()["chunks"] > 0
    assert ing.json()["kind"] == "file-pdf"

    srch = c.get("/kb/search", params={"tenant_id": TENANT, "project_id": proj_id, "q": phrase, "k": 5})
    assert srch.status_code == 200, srch.text
    hits = srch.json()
    assert len(hits) >= 1
    assert any(h["kind"] == "file-pdf" for h in hits)


