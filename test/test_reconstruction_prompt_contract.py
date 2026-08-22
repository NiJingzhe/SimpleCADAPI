from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "docs/skill/references/docs/guides"
PROMPT = GUIDES / "reconstruction-agent-test-prompt.md"
STRATEGY = GUIDES / "reconstruction-agent-strategy.md"
GUIDE_INDEX = GUIDES / "README.md"


def _configuration_keys(text: str) -> set[str]:
    match = re.search(
        r"^Configuration:\n(?P<body>.*?)\n\nConfiguration selects options",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    return {
        line.split("=", 1)[0].strip()
        for line in match.group("body").splitlines()
        if "=" in line
    }


def test_reconstruction_prompt_is_a_compact_versioned_contract() -> None:
    text = PROMPT.read_text(encoding="utf-8")

    assert "Contract ID:" in text
    assert "Contract version: `2.2`" in text
    assert "PROMPT_VERSION = 2.2" in text
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


def test_prompt_configuration_has_diagnostic_controls_and_proof_gates() -> None:
    keys = _configuration_keys(PROMPT.read_text(encoding="utf-8"))

    expected = {
        "SIMPLECADAPI_ROOT",
        "TARGET_DIR",
        "OUTPUT_DIR",
        "CASE_NAME",
        "CASE_MANIFEST",
        "ALLOWED_INPUTS",
        "PROMPT_VERSION",
        "OBJECTIVE",
        "TARGET_PATH",
        "TARGET_KIND",
        "BENCHMARK_MODE",
        "ENTRYPOINT",
        "CANDIDATE_PATH",
        "MAX_ITERATIONS",
        "MAX_FAILED_ATTEMPTS",
        "TOTAL_TIMEOUT_SECONDS",
        "STAGE_TIMEOUT_SECONDS",
        "MATERIAL_TIMEOUT_SECONDS",
        "BOUNDARY_LINEAR_DEFLECTION_MM",
        "BOUNDARY_MAX_SAMPLES",
        "SECTIONS",
        "STRICT_TOPOLOGY",
        "PARAMETER_REPRESENTATION_REQUIRED",
        "STRICT_MATERIAL_TOLERANCE_MM3",
        "STRICT_GEOMETRIC_TOLERANCE_MM",
    }
    assert keys == expected
    assert keys.isdisjoint(
        {
            "GLOBAL_MAX_BBOX_DELTA_MM",
            "GLOBAL_MAX_CENTROID_DISTANCE_MM",
            "GLOBAL_MAX_RELATIVE_VOLUME_ERROR",
            "GLOBAL_MAX_RELATIVE_AREA_ERROR",
            "BOUNDARY_MAX_HAUSDORFF_MM",
            "BOUNDARY_MAX_P95_MM",
        }
    )


def test_reconstruction_prompt_section_schema_has_no_acceptance_thresholds() -> None:
    text = PROMPT.read_text(encoding="utf-8")
    match = re.search(
        r"Each `SECTIONS` item has this closed schema:\n\n```json\n(?P<body>.*?)\n```",
        text,
        flags=re.DOTALL,
    )
    assert match is not None
    schema = match.group("body")

    for key in ('"id"', '"origin"', '"normal"', '"tolerance"', '"samples_per_edge"'):
        assert key in schema
    for removed in (
        '"require_nonempty"',
        '"max_hausdorff"',
        '"max_relative_area_error"',
    ):
        assert removed not in schema


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
    assert "non-fuzzy bidirectional Cut residual volumes" in text
    assert "tolerance-bounded material equivalence" in text
    assert "not aggregate mass-property comparisons" in " ".join(text.split())
    assert "do not prove topology, representation, or literal boundary" in text


def test_reconstruction_prompt_has_monotonic_and_open_shell_classification() -> None:
    text = PROMPT.read_text(encoding="utf-8")

    assert "Higher-tier failure never erases a proven lower tier" in text
    assert "open_shell_equivalence_unproved" in text
    assert "fabricated_solid_for_open_shell" in text
    assert "material timeout" in text.lower()
    assert "exactness under the evaluator's declared tolerance and evidence schema" in text
    assert "does not recover or prove original CAD feature history" in text
    assert "must be defined by the trusted case manifest" in text


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
    assert "aggregate volume" in text
    assert "total surface area" in text
    assert "bounding box" in text
    assert "centroid" in text
    assert "sampled distance" in text
    assert "section area" in text
    assert "falsification and localization only" in text
    assert "They never affect classification" in text
    assert "status=completed" in text
    assert "gate_passed=null" in text


def test_prompt_separates_persistence_metrics_from_target_similarity() -> None:
    text = PROMPT.read_text(encoding="utf-8")

    assert (
        "candidate-before/after measurements are serialization integrity checks" in text
    )
    assert "not candidate-to-target similarity metrics" in text
    for metric in (
        "volume",
        "total surface area",
        "centroid",
        "material bounds",
        "root bounds",
    ):
        assert metric in text


