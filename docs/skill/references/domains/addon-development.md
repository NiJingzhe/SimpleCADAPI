# Task Domain: Addon Development

Author, install, and manage SimpleCADAPI addons: third-party packages that
add non-modeling capabilities — simulation, analysis, downstream tooling —
by consuming `.scadpkg` product packages.

## Use when

- Creating or publishing an addon (a repository with `sca-addon.toml` and
  a skill directory).
- Installing, updating, or removing an addon with the `sca` CLI.
- Deciding whether a capability belongs in an addon or in the SDK.

## Boundary: addon vs SDK contribution

| Capability | Belongs in |
| --- | --- |
| Geometry modeling, domain modeling operations, anything that must build BRep inside a session | SimpleCADAPI core (optionally as an extra, e.g. `simplecadapi[fem]`) |
| Verification, analysis, simulation, rendering, export to foreign ecosystems, anything that *consumes* finished geometry | An addon |

An addon has two legal integration modes with the SDK.

**Recommended default — process boundary.** The addon consumes
`.scadpkg` files (members, tags channel, occurrence graph, scene
projection; units are millimeters) and whatever host tooling it needs,
in any language. Dependency conflicts are structurally impossible and
non-Python addons are first-class.

**Allowed — in-process SDK use.** A Python addon may install
`simplecadapi` inside its own environment and import it: the builtin
exporters (STEP/STL/OBJ/MJCF, gmsh meshing) and the package readers
(`read_product_package`, `load_product_package`) exist for exactly this
kind of downstream consumer. The descriptor's `[compat] sca` range
governs which SDK releases that dependency may resolve to — declare
the SDK as a dependency of the addon environment and keep the range
honest.

What holds in both modes: the addon runs in its own environment and is
not installed into the environment that models the geometry — mixing
plugin dependencies into the modeling SDK environment is what the
separation exists to prevent.

## Repository layout

```text
<repo root>/
  sca-addon.toml      descriptor: machine-checked facts only, no prose
  skill/
    SKILL.md          everything an agent reads; installed as sca-<name>
    <supporting assets: scripts, references, templates...>
  <runtime code, binaries, docs — addon-owned>
```

One document per audience: the descriptor is read by the `sca` CLI, the
SKILL.md is read by agents. Never duplicate prose into the descriptor.

## Descriptor reference (`sca-addon.toml`)

Validation is strict: unknown tables and keys are rejected, every
failure names the field and file.

| Field | Rule |
| --- | --- |
| `[addon] name` | lowercase slug `[a-z0-9][a-z0-9-]{0,63}`; becomes the install directory and skill prefix |
| `[addon] version` | dotted numeric with optional pre-release suffix (e.g. `0.3.1`, `2.0.4b2`) |
| `[addon] license` | non-empty; must be accurate — addons are redistributed |
| `[addon] skill_path` | relative POSIX-style directory containing `SKILL.md` |
| `[compat] sca` | version range, comma-separated clauses with `== != >= <= > <`; a bare version means exact match. Ranges, never pins: SDK releases within a range must not break addons. Pre-release suffixes sort before their release (`2.0.4b2 < 2.0.4`); missing trailing components pad with zero (`2.1` == `2.1.0`) |
| `[runtime] kind` | `binary` \| `python-env` \| `docker` \| `none` |
| `[runtime] platforms` | non-empty list, required for `binary`/`python-env`, forbidden for `none`/`docker` |
| `[runtime] check_cmd` | required for `binary`/`python-env`, optional for `docker`, forbidden for `none` |
| `[runtime.check_overrides]` | optional per-platform command overrides; keys must be declared platforms |

Closed platform enum (additive across spec versions):

```text
macos-arm64 | macos-x86_64 | linux-x86_64 | linux-aarch64
| windows-x86_64 | windows-arm64
```

## `check_cmd` contract

A runtime probe must be fast but meaningful:

1. Exit code `0` means usable; any other exit or a missing command means
   not usable.
2. Execution shell is pinned by the spec: `sh -c` on Unix, `cmd /c` on
   Windows — write the command accordingly.
3. Completes in about two seconds; no network access, no license
   checkout, no GUI launch.
4. A failing probe warns loudly at install time but never blocks the
   install — the runtime can be installed afterwards. Re-run it before
   first use.

## Addon SKILL.md requirements

The skill is the addon's single agent-facing document:

- **Frontmatter `description` is the routing card.** Hosts surface it to
  agents verbatim; state the trigger condition, what the addon consumes
  from `.scadpkg` (which members, which tag patterns such as
  `interface.*`), and what it produces.
- **Pre-check the runtime.** Run the probe (the descriptor's
  `check_cmd`) before first use; on failure, name the missing runtime
  and stop — never silently skip the analysis.
- **Declare the consumption contract.** Units are millimeters; state
  coordinate-system assumptions and required tags explicitly.
- **Never modify geometry.** An addon analyzes, verifies, or transforms
  finished packages; when a task needs geometry changes, return to the
  SimpleCADAPI modeling workflows and re-capture.
- **Reference the main skill.** Describe the pipeline end to end:
  model with SimpleCADAPI → `capture` a `.scadpkg` → this addon
  consumes it.

## Installing and managing addons

```bash
sca addon init                     # once per machine: home + registry + config
sca addon add owner/repo           # install from GitHub (default branch)
sca addon add owner/repo@v1.2.0    # pin a tag or commit for reproducibility
sca addon add ./my-addon           # install a local checkout (test before publishing)
sca addon update [name]            # re-fetch one addon or all
sca addon remove name
sca addon list                     # registry contents + on-disk drift
```

- Locations resolve as flag > environment variable (`SCA_ADDON_HOME`,
  `SCA_SKILLS_DIR`) > `~/.sca/config.toml` > defaults
  (`~/.sca/addons`, `~/.agents/skills`). The CLI never writes shell
  profiles; env vars are user-side overrides.
- Skills install as `sca-<name>` inside the skills directory — copied,
  never symlinked. A non-registry directory of that name is never
  overwritten.
- GitHub sources fetch as tarballs (no git binary needed, byte-exact
  files); `--method clone` is the escape hatch for private
  repositories.

### Hard failures vs warnings

| Outcome | Behavior |
| --- | --- |
| Descriptor invalid, `[compat] sca` mismatch, platform unsupported, name collision, foreign skill directory | install aborts, naming the exact cause |
| `check_cmd` fails, update downgrades | loud warning; install/update proceeds |
| Registry vs disk drift (missing directories) | surfaced by `sca addon list` as `DRIFT` lines |

## Publishing checklist

1. `sca addon add ./repo` from a local checkout; confirm the summary
   and that the skill lands under `sca-<name>`.
2. `sca addon list` shows no drift; the runtime probe passes on every
   declared platform you can test.
3. Tag the release; users pin with `owner/repo@<tag>`.
4. Bump `[addon] version` for every published change; widen
   `[compat] sca` only after testing against the new SDK release.
