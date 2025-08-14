from orchestrator.integrations.github import build_pr_summary_md


def test_build_pr_summary_md_contains_marker_and_links():
    md = build_pr_summary_md(
        project_name="Demo",
        item_title="Feature A",
        branch="feature/1234abcd-feature-a",
        dor_pass=False,
        missing=["prd", "design"],
        owner="o",
        repo="r",
        base_dir="docs/roadmap/1234abcd-feature-a",
    )
    assert "Definition of Ready" in md
    assert "❌ Blocked" in md
    assert "<!-- ai-csuite:summary:feature/1234abcd-feature-a -->" in md
    assert "blob/feature/1234abcd-feature-a/docs/roadmap/1234abcd-feature-a/prd.json" in md


