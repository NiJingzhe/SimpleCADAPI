# Archived stage scripts (not runnable contracts)

These scripts are historical evidence from abandoned or superseded design
stages. They are kept for provenance and must not be run as verification
contracts — the live verifier set is the `s*_verify.py` / `s5_render_check.py`
files in the parent directory.

| Script | Why archived |
| --- | --- |
| `s9_verify.py` | Verifier of the S9 "boss 柱 + 盖子 (cover)" design. The S10 user-directed pivot ("弃方形腔 → 75% 剖分两件 + 轮廓贴合 shell", see `../../session_transcript.md` S10 section) explicitly retired `cover.py`, which this script imports; `cover.py` was never committed, so this import fails by design. The design it verified was replaced by `shell.py` and `s10_verify.py` / `s12_verify.py`. |
| `s9_hypothesis.py` | S9-stage hypothesis probes (boss/hole/rib/chamfer checks against the S9 body). Self-contained and may still run, but it asserts the abandoned S9 geometry contract (boss_z layout, cavity_h band) that no longer matches `u_link.py`. |
| `s10_hypothesis.py` | S10-stage hypothesis probes. References `u_link._u_path_edges`, which was replaced in feat/ftc by the constrained-sketch `_u_path_wire` (open-chain wire promotion); the transcribed path helper no longer exists. |

Archived 2026-08-31 on branch `feat/ftc`.
