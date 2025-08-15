from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Any, Dict

# ---------- Projects ----------
class ProjectCreate(BaseModel):
    tenant_id: str
    name: str
    description: str = ""
    repo_url: str = ""

class ProjectRead(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str
    repo_url: str
    created_at: datetime

# NEW: partial update for Project
class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    repo_url: Optional[str] = None

# ---------- Roadmap Items ----------
Status = Literal["planned", "in_progress", "blocked", "done"]

class RoadmapItemCreate(BaseModel):
    tenant_id: str
    project_id: str
    title: str
    description: str = ""
    priority: int = 100
    target_release: str = ""

class RoadmapItemRead(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    title: str
    description: str
    status: Status
    priority: int
    target_release: str

class RoadmapItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Status] = None
    priority: Optional[int] = Field(default=None, ge=0)

# ---------- Runs ----------
class RunCreate(BaseModel):
    tenant_id: str
    project_id: str
    roadmap_item_id: str | None = None
    phase: str = "delivery"

class RunRead(BaseModel):
    id: str
    status: str
    created_at: datetime

# ---------- Discovery artifacts ----------
class PRDRead(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    roadmap_item_id: str
    version: str
    prd: Dict[str, Any]
    created_at: datetime

class DesignCheckRead(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    roadmap_item_id: str
    passes: bool
    heuristics_score: int
    a11y_notes: str
    created_at: datetime

class ResearchNoteRead(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    roadmap_item_id: str
    summary: str
    evidence: List[str]
    created_at: datetime

class KbIngest(BaseModel):
    tenant_id: str
    project_id: str
    kind: str
    ref_id: str | None = None
    text: str

class KbSearchResult(BaseModel):
    id: str
    kind: str
    ref_id: str
    text: str
    score: float

# --- Phase 13: file ingestion ---
class KbFileIngest(BaseModel):
    tenant_id: str
    project_id: str
    filename: str
    content_type: Literal["markdown", "pdf", "text"]
    content_b64: Optional[str] = None
    text: Optional[str] = None
    ref_id: Optional[str] = None

class DiscoveryStatus(BaseModel):
    dor_pass: bool
    missing: List[str]
    prd: Optional[PRDRead] = None
    design: Optional[DesignCheckRead] = None
    research: Optional[ResearchNoteRead] = None
    related: List[KbSearchResult] = []

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Literal

# ---------- Projects ----------
class ProjectCreate(BaseModel):
    tenant_id: str
    name: str
    description: str = ""
    repo_url: str = ""

class ProjectRead(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str
    repo_url: str
    created_at: datetime

# ---------- Roadmap Items ----------
Status = Literal["planned", "in_progress", "blocked", "done"]

class RoadmapItemCreate(BaseModel):
    tenant_id: str
    project_id: str
    title: str
    description: str = ""
    priority: int = 100
    target_release: str = ""

class RoadmapItemRead(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    title: str
    description: str
    status: Status
    priority: int
    target_release: str

class RoadmapItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Status] = None
    priority: Optional[int] = Field(default=None, ge=0)

# ---------- Runs ----------
class RunCreate(BaseModel):
    tenant_id: str
    project_id: str
    roadmap_item_id: str | None = None
    phase: str = "delivery"

class RunRead(BaseModel):
    id: str
    status: str
    created_at: datetime



# ---------- GitHub integration ----------
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class GithubVerify(BaseModel):
    project_id: Optional[str] = None
    repo_url: Optional[str] = None

class PRRead(BaseModel):
    id: str
    run_id: str
    project_id: str
    repo: str
    branch: str
    number: int
    url: str
    state: str
    created_at: datetime

