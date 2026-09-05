# Session Transcript Format (demo_kit)

`build_demo.py` parses a case's `session_transcript.md` into the replay demo.
The grammar below is exactly what the parser accepts; anything else is ignored.

## File header

```markdown
# OpenCode Session Transcript

- Session ID: `ses_<random>`
- Title: <case title, Chinese ok>
- Directory: /Users/lildino/Project/ocws/SCAD-Open
- Started: YYYY-MM-DD HH:MM:SS
- Updated: YYYY-MM-DD HH:MM:SS
- Messages: <count of USER+ASSISTANT sections, roleswitch excluded>

---
```

## Sections

Three section kinds, separated by `---` lines. Every section starts with a
timestamp line `*msg_<random22> @ YYYY-MM-DD HH:MM:SS*` as its first body line.

### USER turn (numbered, real user wording)

```markdown
## [1] USER
*msg_abc... @ 2026-09-05 18:30:12*

<verbatim user text>

---
```

### ASSISTANT turn

```markdown
## [ASSISTANT] (glm-5.3)
*msg_def... @ 2026-09-05 18:30:40*

<details><summary>thinking</summary>

> Real reasoning summary, one `> `-prefixed line per line.

</details>

Prose reply.

**[tool: bash]** status=ok
```json
{"command": "uv run python examples/flange_plate/model.py"}
```
```output
<real output, may elide with "... (N lines)" — numbers and verdicts stay real>
```

**[patch]** hash=1a2b3c4d5e
- file: examples/flange_plate/model.py

**[text]**

More prose.

---
```

Tool names are lowercase: `bash read write edit todowrite glob grep question
task skill`. One ```json fence = tool input, one ```output fence = tool output
(only the first of each is captured). A `**[patch]**` block follows each
write/edit; hash = first 10 hex of md5 of the resulting file content.

### Role switch

```markdown
## [Role Switch: <Role Name>]
*msg_ghi... @ 2026-09-05 18:35:00*

Reading: <role-owned files>
Artifact out: <path>

---
```

`— note` may follow the role name inside the bracket. Optional `# Skill:`
blocks (skill loads) render as a special chip.

## Fidelity rules

- Tool calls/outputs must be the real actions that produced the artifacts —
  outputs may be trimmed, never edited or invented.
- Thinking blocks are the real reasoning of the moment, summarized honestly.
- USER turns are verbatim; role-switch blocks follow the workflow's protocol.
- Timestamps are real wall-clock times; `Messages:` equals the final section
  count (excluding role switches).
