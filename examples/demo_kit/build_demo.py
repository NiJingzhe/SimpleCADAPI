#!/usr/bin/env python3
"""demo_kit: build a single-file session-replay demo (index.html) for one case.

Usage from a case directory (see each case's demo/build.py):

    from pathlib import Path
    import sys
    KIT = Path(__file__).resolve().parents[2] / "demo_kit"
    sys.path.insert(0, str(KIT))
    from build_demo import build_case
    build_case({...})

Or via CLI for quick rebuilds (only transcript/stl/imgs, default config):

    python3 examples/demo_kit/build_demo.py --root examples/<case>

Transcript grammar: see TRANSCRIPT_FORMAT.md in this directory.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent  # examples/demo_kit

RE_USER = re.compile(r"^## \[(\d+)\] USER\s*$")
RE_ASST = re.compile(r"^## \[ASSISTANT\] \(([^)]+)\)\s*$")
RE_ROLE = re.compile(r"^## \[(?:Role Switch|角色切换)\s*[：:]\s*([^\]]+)\]\s*(?:—\s*(.*))?\s*$")
RE_TIME = re.compile(r"^\*msg_\S+ @ (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\*\s*$")
RE_TOOL = re.compile(r"^\*\*\[tool: ([a-z_]+)\]\*\* status=(\w+)\s*$")
RE_PATCH = re.compile(r"^\*\*\[patch\]\*\* hash=([0-9a-f]+)\s*$")
RE_TEXT = re.compile(r"^\*\*\[text\]\*\*\s*$")
RE_THINK_OPEN = "<details><summary>thinking</summary>"
RE_FENCE = re.compile(r"^```(\w*)\s*$")

MARKERS = ("**[tool: ", "**[patch]**", "**[text]**")


def fence_blocks(body: list[str], i: int) -> tuple[dict | None, int]:
    m = RE_FENCE.match(body[i])
    if not m:
        return None, i
    lang = m.group(1) or "text"
    buf: list[str] = []
    i += 1
    while i < len(body) and not body[i].startswith("```"):
        buf.append(body[i])
        i += 1
    return {"t": "code", "lang": lang, "src": "\n".join(buf)}, i + 1


def parse_blocks(body: list[str]) -> list[dict]:
    blocks: list[dict] = []
    i = 0
    text_buf: list[str] = []

    def flush_text():
        nonlocal text_buf
        while text_buf and not text_buf[-1].strip():
            text_buf.pop()
        s = 0
        while s < len(text_buf) and not text_buf[s].strip():
            s += 1
        if text_buf[s:]:
            blocks.append({"t": "text", "md": "\n".join(text_buf[s:])})
        text_buf = []

    while i < len(body):
        line = body[i]
        if line.strip() == "---":
            i += 1
            continue

        if line.startswith(RE_THINK_OPEN):
            flush_text()
            buf: list[str] = []
            i += 1
            while i < len(body) and "</details>" not in body[i]:
                buf.append(re.sub(r"^> ?", "", body[i]))
                i += 1
            i += 1
            blocks.append({"t": "think", "md": "\n".join(buf).strip()})
            continue

        if line.startswith("# Skill:"):
            flush_text()
            skill = [body[i]]
            i += 1
            while i < len(body):
                if any(body[i].startswith(m) for m in MARKERS) or body[i].startswith("```"):
                    break
                skill.append(body[i])
                i += 1
            blocks.append({"t": "skill", "name": line.split(":", 1)[1].strip(), "md": "\n".join(skill).strip()})
            continue

        tm = RE_TOOL.match(line)
        if tm:
            flush_text()
            tool = {"t": "tool", "name": tm.group(1), "status": tm.group(2), "input": None, "output": None}
            i += 1
            while i < len(body):
                if any(body[i].startswith(m) for m in MARKERS) or body[i].startswith(RE_THINK_OPEN):
                    break
                fb, ni = fence_blocks(body, i)
                if fb is None:
                    if body[i].strip():
                        break
                    i = ni if ni != i else i + 1
                    continue
                if fb["lang"] == "json" and tool["input"] is None:
                    tool["input"] = fb["src"]
                elif fb["lang"] == "output" and tool["output"] is None:
                    tool["output"] = fb["src"]
                i = ni
            blocks.append(tool)
            continue

        pm = RE_PATCH.match(line)
        if pm:
            flush_text()
            files: list[str] = []
            i += 1
            while i < len(body) and body[i].lstrip().startswith("- file:"):
                files.append(body[i].lstrip()[len("- file:"):].strip())
                i += 1
            blocks.append({"t": "patch", "hash": pm.group(1)[:10], "files": files})
            continue

        if RE_TEXT.match(line):
            flush_text()
            i += 1
            continue

        fb, ni = fence_blocks(body, i)
        if fb is not None:
            flush_text()
            blocks.append(fb)
            i = ni
            continue

        text_buf.append(line)
        i += 1

    flush_text()
    return blocks


def parse_transcript(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()

    meta: dict = {}
    for ln in lines[:12]:
        if ln.startswith("- Session ID:"):
            meta["id"] = ln.split("`")[1]
        elif ln.startswith("- Title:"):
            meta["title"] = ln.split(":", 1)[1].strip()
        elif ln.startswith("- Started:"):
            meta["start"] = ln.split(":", 1)[1].strip()
        elif ln.startswith("- Updated:"):
            meta["end"] = ln.split(":", 1)[1].strip()
        elif ln.startswith("- Messages:"):
            meta["claimed"] = int(ln.split(":", 1)[1].strip())

    sections: list[dict] = []
    cur: dict | None = None
    for ln in lines:
        if RE_USER.match(ln) or RE_ASST.match(ln) or RE_ROLE.match(ln):
            cur = {"head": ln, "body": []}
            sections.append(cur)
        elif cur is not None:
            cur["body"].append(ln)

    messages: list[dict] = []
    role_state = ""
    for sec in sections:
        head, body = sec["head"], sec["body"]
        ts = None
        clean: list[str] = []
        for ln in body:
            mt = RE_TIME.match(ln)
            if mt:
                ts = mt.group(1)
            else:
                clean.append(ln)
        while clean and not clean[-1].strip():
            clean.pop()

        mu = RE_USER.match(head)
        ma = RE_ASST.match(head)
        mr = RE_ROLE.match(head)
        msg: dict = {"i": len(messages)}
        if ts:
            msg["ts"] = ts
        if mu:
            msg["role"] = "user"
            msg["userN"] = int(mu.group(1))
        elif ma:
            msg["role"] = "asst"
            msg["model"] = ma.group(1)
            msg["curRole"] = role_state
        else:
            name = mr.group(1).strip()
            note = (mr.group(2) or "").strip()
            msg["role"] = "roleswitch"
            msg["roleName"] = name
            if note:
                msg["roleNote"] = note
            reading = artifact = ""
            rest: list[str] = []
            for ln in clean:
                if ln.startswith("Reading:"):
                    reading = ln.split(":", 1)[1].strip()
                elif ln.startswith("Artifact out:"):
                    artifact = ln.split(":", 1)[1].strip()
                else:
                    rest.append(ln)
            if reading:
                msg["reading"] = reading
            if artifact:
                msg["artifact"] = artifact
            clean = rest
            role_state = name
        msg["blocks"] = parse_blocks(clean)
        messages.append(msg)

    tool_counts: dict[str, int] = {}
    n_think = n_text = n_patch = 0
    pass_count = 0
    for m in messages:
        for b in m["blocks"]:
            if b["t"] == "tool":
                tool_counts[b["name"]] = tool_counts.get(b["name"], 0) + 1
                if b.get("output") and "ALL PASS" in b["output"]:
                    pass_count += 1
            elif b["t"] == "think":
                n_think += 1
            elif b["t"] == "text":
                n_text += 1
            elif b["t"] == "patch":
                n_patch += 1
    users = [m["i"] for m in messages if m["role"] == "user"]

    return {
        "meta": meta,
        "stats": {
            "messages": len(messages),
            "userTurns": len(users),
            "asst": sum(1 for m in messages if m["role"] == "asst"),
            "roleSwitches": sum(1 for m in messages if m["role"] == "roleswitch"),
            "tools": tool_counts,
            "toolTotal": sum(tool_counts.values()),
            "think": n_think,
            "text": n_text,
            "patch": n_patch,
            "allPass": pass_count,
            "userIdx": users,
        },
        "messages": messages,
    }


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def stl_triangle_count(path: Path) -> int:
    """Binary STL: 80-byte header, then uint32 triangle count."""
    with path.open("rb") as fh:
        fh.seek(80)
        (count,) = struct.unpack("<I", fh.read(4))
        return count


def build_case(cfg: dict) -> Path:
    """Build one case's demo/index.html. See demo_kit/README.md for cfg keys."""
    root = Path(cfg["root"]).resolve()
    transcript = Path(cfg.get("transcript", root / "session_transcript.md"))
    out_html = Path(cfg.get("out", root / "demo" / "index.html"))

    data = parse_transcript(transcript)
    st = data["stats"]
    print(
        f"parsed {st['messages']} messages (claimed {data['meta'].get('claimed')}), "
        f"{st['userTurns']} user turns, {st['asst']} assistant, {st['roleSwitches']} role switches, "
        f"{st['toolTotal']} tool calls, {st['allPass']} ALL-PASS outputs"
    )

    stl_path = Path(cfg["stl"]["path"])
    tris = cfg["stl"].get("tris") or stl_triangle_count(stl_path)
    config = {
        "title": cfg.get("title", data["meta"].get("title", "")),
        "subtitle": cfg.get("subtitle", "· 从一句话需求到可制造装配"),
        "stl": {
            "name": cfg["stl"].get("name", stl_path.name),
            "note": cfg["stl"].get("note", ""),
            "glCap": cfg["stl"].get("gl_cap", f"{stl_path.name} · {tris:,} 三角面"),
            "tris": tris,
            "b64": b64(stl_path),
        },
        "imgs": [
            {"key": im["key"], "cap": im["cap"], "b64": b64(Path(im["path"]))}
            for im in cfg["imgs"]
        ],
        "params": cfg.get("params", []),
        "tags": cfg.get("tags", []),
        "tagsNote": cfg.get("tags_note", ""),
        "artifacts": cfg.get("artifacts", {"files": [], "scripts": [], "notes": []}),
        "about": cfg.get("about", []),
        "highlights": cfg.get("highlights", ""),
        "extraStat": cfg.get("extra_stat"),
    }
    data["config"] = config

    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    css = (HERE / "app.css").read_text(encoding="utf-8")
    js = (HERE / "app.js").read_text(encoding="utf-8")
    three = (HERE / "vendor" / "three.min.js").read_text(encoding="utf-8")
    orbit = (HERE / "vendor" / "OrbitControls.js").read_text(encoding="utf-8")
    stl_l = (HERE / "vendor" / "STLLoader.js").read_text(encoding="utf-8")

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")

    html = (
        tpl.replace("/*__CSS__*/", css)
        .replace("/*__JS__*/", js)
        .replace("__DATA__", payload)
        .replace("__THREE__", three)
        .replace("__ORBIT__", orbit)
        .replace("__STLL__", stl_l)
    )
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html, encoding="utf-8")
    print(f"wrote {out_html} ({out_html.stat().st_size / 1e6:.1f} MB)")
    return out_html


def _cfg_from_cli(args: argparse.Namespace) -> dict:
    imgs = []
    for spec in args.img or []:
        key, rest = spec.split("=", 1)
        path, _, cap = rest.partition(":")
        imgs.append({"key": key, "path": path, "cap": cap or key})
    return {
        "root": args.root,
        "transcript": args.transcript,
        "out": args.out,
        "stl": {"path": args.stl},
        "imgs": imgs,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, help="case root directory")
    ap.add_argument("--transcript", help="transcript md (default <root>/session_transcript.md)")
    ap.add_argument("--out", help="output html (default <root>/demo/index.html)")
    ap.add_argument("--stl", required=True, help="final body/assembly STL path")
    ap.add_argument("--img", action="append", metavar="KEY=PATH:CAP", help="render image slot (repeatable)")
    args = ap.parse_args()
    build_case(_cfg_from_cli(args))


if __name__ == "__main__":
    main()
