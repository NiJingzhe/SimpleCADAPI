from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "docs/guides/reconstruction-agent-test-prompt.md"
PROMPT_MIRROR = (
    ROOT
    / "skills/simplecadapi/references/docs/guides/reconstruction-agent-test-prompt.md"
)
STRATEGY = ROOT / "docs/guides/reconstruction-agent-strategy.md"
STRATEGY_MIRROR = (
    ROOT / "skills/simplecadapi/references/docs/guides/reconstruction-agent-strategy.md"
)
GUIDE_INDEX = ROOT / "docs/guides/README.md"
GUIDE_INDEX_MIRROR = ROOT / "skills/simplecadapi/references/docs/guides/README.md"


def test_reconstruction_prompt_is_a_compact_versioned_contract() -> None:
    text = PROMPT.read_text(encoding="utf-8")

    assert len(text.splitlines()) <= 350
    assert "Contract ID:" in text
    assert "Contract version: `2.1`" in text
    assert "## Precedence" in text
    assert "OBJECTIVE =" in text
    assert "TARGET_KIND =" in text
    assert "ENTRYPOINT =" in text
    assert "CANDIDATE_PATH =" in text
    assert "CASE_MANIFEST =" in text
    assert "ALLOWED_INPUTS =" in text
    assert "TARGET_PATH =" in text
    assert "TOTAL_TIMEOUT_SECONDS =" in text
    assert "Section IDs must be unique" in text
    assert "samples_per_edge >= 4" in text
    assert "reconstruction-agent-strategy.md" in text
    assert "cannot waive a normative rule" in text
    assert "validate_step_roundtrip_rdescriptor" not in text
    assert "may restrict that list but cannot add to it" in text
    assert "STRICT_MATERIAL_TOLERANCE_MM3 = {positive number}" in text
    assert "add/modify SDK operations" in text
    assert "Participant replay may execute only `ENTRYPOINT`" in text
    assert "not a boolean" in text
    assert "`require_nonempty` must be a" in text


def test_reconstruction_prompt_requires_actual_strict_material_proof() -> None:
    text = PROMPT.read_text(encoding="utf-8")

    for requirement in (
        "include_components=True",
        "boolean_tolerance=None",
        "method=bidirectional_cut",
        "strict_equality_supported=true",
        "boolean_result_valid=true",
        "volume_balance.valid=true",
    ):
        assert requirement in text
    assert "include_components=False" not in text


def test_reconstruction_prompt_has_monotonic_and_open_shell_classification() -> None:
    text = PROMPT.read_text(encoding="utf-8")

    assert "Higher-tier failure never erases a proven lower tier" in text
    assert "open_shell_equivalence_unproved" in text
    assert "fabricated_solid_for_open_shell" in text
    assert "material timeout" in text.lower()


def test_reconstruction_prompt_documents_evaluator_schemas_units_and_trust() -> None:
    text = PROMPT.read_text(encoding="utf-8")

    assert "### Evaluator Stage Schema And Units" in text
    assert "`elapsed_seconds`" in text
    assert "`checks.hard_gate=true`" in text
    assert "volume in mm3" in text
    assert "area in mm2" in text
    assert "diagnostic only" in text
    assert "unmodified process-local results" in text
    assert "serialized or rebuilt" in text
    assert "SHA-256 bindings" in text
    assert "participant-declared kind or validity is not evidence" in text
    assert "zero solids, at least one shell explicitly reported open" in text
    assert "claimed" in text.lower()
    assert "strict stage status cannot establish it" in text.lower()


def test_prompt_and_strategy_skill_mirrors_are_exact() -> None:
    assert PROMPT.read_bytes() == PROMPT_MIRROR.read_bytes()
    assert STRATEGY.is_file()
    assert STRATEGY.read_bytes() == STRATEGY_MIRROR.read_bytes()
    assert GUIDE_INDEX.read_bytes() == GUIDE_INDEX_MIRROR.read_bytes()
