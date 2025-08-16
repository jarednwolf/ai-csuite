from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, validator


AllowedStep = Literal[
    "init_repo_or_branch",
    "create_backend_service",
    "create_frontend_app",
    "db_migrations_and_seed",
    "wire_ci_cd_and_iac",
    "add_e2e_tests",
    "open_pr_and_request_gates",
]


class StackBackend(BaseModel):
    runtime: str = Field(examples=["python3.12"])  # e.g., python3.12
    framework: str = Field(examples=["fastapi"])  # e.g., fastapi
    db: str = Field(examples=["postgres"])        # e.g., postgres


class StackFrontend(BaseModel):
    framework: str = Field(examples=["react"])    # e.g., react


class StackInfra(BaseModel):
    containers: bool = Field(examples=[True])
    iac: str = Field(examples=["terraform"])     # e.g., terraform
    preview_envs: bool = Field(examples=[True])


class Stack(BaseModel):
    backend: StackBackend
    frontend: StackFrontend
    infra: StackInfra


class QualityGates(BaseModel):
    a11y_min: int = Field(ge=0, le=100, examples=[80])
    e2e_cov_min: float = Field(ge=0.0, le=1.0, examples=[0.7])
    perf_budget_ms: int = Field(ge=1, examples=[1500])


class ScaffoldStep(BaseModel):
    step: AllowedStep


class BlueprintManifest(BaseModel):
    id: str = Field(description="Stable identifier", examples=["web-crud-fastapi-postgres-react"])
    version: str = Field(description="Semver string", examples=["1.0.0"])
    name: str = Field(description="Human readable name")
    description: str = Field(description="Short description")
    stack: Stack
    capabilities: List[str]
    quality_gates: QualityGates
    scaffold: List[ScaffoldStep]
    deploy_targets: List[Literal["preview", "staging", "prod"]]

    @validator("id")
    def _validate_id(cls, v: str) -> str:
        if not v or " " in v:
            raise ValueError("id must be non-empty and contain no spaces")
        return v

    @validator("version")
    def _validate_version(cls, v: str) -> str:
        parts = v.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValueError("version must be semver-like: MAJOR.MINOR.PATCH")
        return v


class BlueprintSummary(BaseModel):
    id: str
    name: str
    version: str
    description: str
    capabilities: List[str]
    quality_gates: QualityGates


def summarize(manifest: BlueprintManifest) -> BlueprintSummary:
    return BlueprintSummary(
        id=manifest.id,
        name=manifest.name,
        version=manifest.version,
        description=manifest.description,
        capabilities=list(manifest.capabilities or []),
        quality_gates=manifest.quality_gates,
    )


