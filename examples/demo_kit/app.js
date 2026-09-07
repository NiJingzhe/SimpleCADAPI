/* -*- coding: utf-8 -*- Agent CAD session replay demo. */
"use strict";

/* ================= data ================= */
const DATA = JSON.parse(document.getElementById("feed").textContent);
const MSGS = DATA.messages;
const STATS = DATA.stats;
const META = DATA.meta;
const CFG = DATA.config || {};
const N = MSGS.length;

/* stage range across role switches, e.g. "S1–S14" */
const stageRange = (() => {
  const sn = [];
  for (const m of MSGS) {
    if (m.role === "roleswitch") {
      const hit = (m.roleName + " " + (m.roleNote || "")).match(/S(\d+)/);
      if (hit) sn.push(+hit[1]);
    }
  }
  if (!sn.length) return "";
  const lo = Math.min(...sn), hi = Math.max(...sn);
  return lo === hi ? "S" + lo : "S" + lo + "–S" + hi;
})();
if (CFG.title) document.title = CFG.title + " · 会话回放 Demo";

const $ = (s, el) => (el || document).querySelector(s);
const el = (tag, cls, txt) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (txt !== undefined) n.textContent = txt;
  return n;
};
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* stage tracking: last S-number seen in role switches up to each message */
let curStage = "";
for (const m of MSGS) {
  if (m.role === "roleswitch") {
    const hit = (m.roleName + " " + (m.roleNote || "")).match(/S(\d+)/);
    if (hit) curStage = "S" + hit[1];
  }
  m.stage = curStage;
}

function roleBadge(name) {
  const n = (name || "").toLowerCase();
  if (n.includes("requirement") || n.includes("需求")) return { label: "需求确认", cls: "r-req" };
  if (n.includes("master")) return { label: "总体规划", cls: "r-plan" };
  if (n.includes("verifier planner") || n.includes("验证规划")) return { label: "验证规划", cls: "r-ver" };
  if (n.includes("builder") || n.includes("建模")) return { label: "建模执行", cls: "r-build" };
  if (n.includes("验证器")) return { label: "验证执行", cls: "r-ver" };
  return { label: name || "Agent", cls: "r-other" };
}

/* ================= mini markdown ================= */
function md(src) {
  const fences = [];
  let s = String(src == null ? "" : src);
  s = s.replace(/```(\w*)\n([\s\S]*?)(?:```|$)/g, (_, lang, code) => {
    fences.push({ lang, code });
    return "\u0000F" + (fences.length - 1) + "\u0000";
  });
  s = esc(s);
  const lines = s.split("\n");
  const out = [];
  let list = null, table = null, quote = false;
  const closeList = () => { if (list) { out.push("</" + list + ">"); list = null; } };
  const closeTable = () => {
    if (table) { out.push("</tbody></table>"); table = null; }
  };
  const closeQuote = () => { if (quote) { out.push("</blockquote>"); quote = false; } };
  const inline = t => t
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/\*([^*\n]+)\*/g, "<i>$1</i>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  for (const raw of lines) {
    const line = raw;
    const fm = line.match(/^\u0000F(\d+)\u0000\s*$/);
    if (fm) { closeList(); closeTable(); closeQuote(); out.push(fenceHtml(fences[+fm[1]])); continue; }
    if (/^\s*$/.test(line)) { closeList(); closeTable(); closeQuote(); out.push(""); continue; }
    if (/^(---+|\*\*\*+)\s*$/.test(line)) { closeList(); closeTable(); closeQuote(); out.push("<hr>"); continue; }
    const hm = line.match(/^(#{1,4})\s+(.*)$/);
    if (hm) {
      closeList(); closeTable(); closeQuote();
      const lv = Math.min(4, hm[1].length + 2);
      out.push("<h" + lv + ">" + inline(hm[2]) + "</h" + lv + ">");
      continue;
    }
    if (/^&gt;\s?/.test(line)) {
      closeList(); closeTable();
      if (!quote) { out.push("<blockquote>"); quote = true; }
      out.push("<p>" + inline(line.replace(/^&gt;\s?/, "")) + "</p>");
      continue;
    }
    closeQuote();
    if (line.includes("|") && line.trim().startsWith("|")) {
      const cells = line.split("|").slice(1, -1).map(c => c.trim());
      if (cells.every(c => /^:?-{2,}:?$/.test(c))) continue; // separator row
      if (!table) { closeList(); out.push("<table><tbody>"); table = true; }
      out.push("<tr>" + cells.map(c => "<td>" + inline(c) + "</td>").join("") + "</tr>");
      continue;
    }
    closeTable();
    const um = line.match(/^\s*[-*]\s+(.*)$/);
    const om = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (um || om) {
      const want = um ? "ul" : "ol";
      if (list !== want) { closeList(); out.push("<" + want + ">"); list = want; }
      out.push("<li>" + inline((um || om)[1]) + "</li>");
      continue;
    }
    closeList();
    out.push("<p>" + inline(line) + "</p>");
  }
  closeList(); closeTable(); closeQuote();
  return out.join("\n");
}
function fenceHtml(f) {
  return '<div class="codebox"><div class="lab"><span>' + esc(f.lang || "text") +
    "</span><span>" + f.code.split("\n").length + " 行</span></div><pre>" + esc(f.code) + "</pre></div>";
}

/* ================= tool summaries ================= */
const TOOL_META = {
  bash: ["$", "bash"], write: ["✍", "write"], edit: ["✎", "edit"], read: ["📖", "read"],
  todowrite: ["☑", "todo"], grep: ["⌕", "grep"], glob: ["[])", "glob"],
  question: ["?", "question"], task: ["☱", "task"], skill: ["⚡", "skill"],
};
function toolSummary(b) {
  let inp = null;
  try { inp = b.input ? JSON.parse(b.input) : null; } catch (e) { inp = null; }
  let s = "";
  if (b.name === "bash") s = (inp && inp.command) || b.input || "";
  else if (inp && inp.filePath) {
    const base = String(inp.filePath).split("/").pop();
    let extra = "";
    if (b.name === "write" && inp.content) extra = " · " + (inp.content.length / 1000).toFixed(1) + "KB";
    if (b.name === "edit" && inp.oldString) extra = " · " + String(inp.oldString).split("\n").length + " 行替换";
    s = base + extra;
  } else if (b.name === "todowrite" && inp && inp.todos) s = inp.todos.length + " 项";
  else s = b.input ? String(b.input).replace(/\s+/g, " ").slice(0, 90) : "(无输入)";
  return { s: s.replace(/\s+/g, " ").slice(0, 110), inp };
}

/* ================= message DOM ================= */
const chat = $("#chat");
let showThink = true, showOut = true;

function buildBlocks(m, box, animated) {
  for (const b of m.blocks) {
    if (b.t === "text") {
      const d = el("div", "blk blk-text");
      const mdEl = el("div", "md");
      mdEl.innerHTML = md(b.md);
      d.appendChild(mdEl);
      box.appendChild(d);
    } else if (b.t === "think") {
      if (!showThink) continue;
      const det = el("details", "blk blk-think");
      const sum = el("summary", null, "思考过程 · " + b.md.length + " 字（点击展开）");
      const body = el("div", "thinkbody");
      body.innerHTML = md(b.md);
      det.append(sum, body);
      box.appendChild(det);
    } else if (b.t === "skill") {
      const det = el("details", "blk blk-skill");
      const sum = el("summary", null, "Skill 加载 · " + b.name + "（SKILL.md 全文）");
      const body = el("div", "skillbody");
      body.innerHTML = md(b.md);
      det.append(sum, body);
      box.appendChild(det);
    } else if (b.t === "code") {
      const d = el("div", "blk");
      d.innerHTML = fenceHtml(b);
      box.appendChild(d);
    } else if (b.t === "patch") {
      const p = el("div", "pill-patch");
      p.appendChild(el("span", "h", "✎ " + b.hash));
      for (const f of b.files) p.appendChild(el("span", "f", f.split("/").slice(-2).join("/")));
      box.appendChild(p);
    } else if (b.t === "tool") {
      box.appendChild(toolCard(b));
    }
  }
}
function toolCard(b) {
  const card = el("div", "toolcard" + (b.status === "error" ? " st-error" : ""));
  const meta = TOOL_META[b.name] || ["▪", b.name];
  const { s } = toolSummary(b);
  const row = el("div", "trow");
  row.append(
    el("span", "tico", meta[0]), el("span", "tname", meta[1]),
    el("span", "tstat st-" + b.status, b.status === "completed" ? "✓ done" : "✗ error"),
    el("span", "tsum", s)
  );
  if (b.input) row.appendChild(el("span", "tlen", "in " + (b.input.length / 1000).toFixed(1) + "k"));
  if (b.output) row.appendChild(el("span", "tlen", "out " + (b.output.length / 1000).toFixed(1) + "k"));
  row.appendChild(el("span", "chev", "▶"));
  const body = el("div", "toolbody");
  let built = false;
  const build = () => {
    if (built) return;
    built = true;
    if (b.input) {
      const d = el("div");
      d.innerHTML = '<div class="codebox"><div class="lab"><span>input · json</span></div><pre>' +
        esc(prettyJson(b.input)) + "</pre></div>";
      body.appendChild(d);
    }
    if (b.output) {
      const d = el("div");
      d.innerHTML = '<div class="codebox"><div class="lab"><span>output</span><span>' +
        b.output.split("\n").length + " 行</span></div><pre>" + esc(b.output) + "</pre></div>";
      d.style.display = showOut ? "" : "none";
      d.className = "tool-out";
      body.appendChild(d);
    }
    if (!b.input && !b.output) body.appendChild(el("div", null, "(无输入输出)"));
  };
  row.addEventListener("click", () => { card.classList.toggle("open"); build(); });
  card.append(row, body);
  return card;
}
function prettyJson(s) {
  try { return JSON.stringify(JSON.parse(s), null, 2); } catch (e) { return s; }
}

function renderMessage(m, opts) {
  opts = opts || {};
  if (m.role === "asst" && m.blocks.length === 0) return null; // 空 assistant 消息(原会话中内容为角色切换公告)
  if (m.role === "user") {
    const d = el("div", "msg user");
    d.dataset.i = m.i;
    const who = el("div", "who");
    who.append(el("span", "turnChip", "用户 · 第 " + m.userN + " 轮"));
    if (m.ts) who.appendChild(el("span", null, m.ts.slice(5)));
    const bub = el("div", "bubble");
    const txt = m.blocks.map(b => (b.t === "text" ? b.md : "")).join("\n").trim() || "(内容见下)";
    d.append(who, bub);
    chat.appendChild(d);
    if (opts.typing) {
      const tip = el("span", "typing", "");
      tip.innerHTML = "<i></i><i></i><i></i>";
      bub.appendChild(tip);
      typeInto(bub, txt, () => {});
    } else {
      bub.textContent = txt;
    }
    return d;
  }
  if (m.role === "roleswitch") {
    const rb = roleBadge(m.roleName);
    const d = el("div", "rolebanner");
    d.dataset.i = m.i;
    const pill = el("div", "pill");
    pill.append(el("span", null, "⟳ 角色切换"), el("span", "rbadge " + rb.cls, rb.label));
    const nm = el("span", null, m.roleName);
    nm.style.color = "#dbe4f3";
    pill.appendChild(nm);
    if (m.roleNote) pill.appendChild(el("span", null, "— " + m.roleNote));
    d.appendChild(pill);
    if (m.reading || m.artifact) {
      const meta = el("div", "meta");
      if (m.reading) meta.innerHTML += "读取 " + md(m.reading).replace(/^<p>|<\/p>$/g, "") + "　";
      if (m.artifact) meta.innerHTML += "产出 " + md(m.artifact).replace(/^<p>|<\/p>$/g, "");
      d.appendChild(meta);
    }
    chat.appendChild(d);
    if (m.blocks.length) {
      const am = el("div", "msg asst");
      am.dataset.i = m.i;
      const head = asstHead(m);
      const box = el("div", null);
      am.append(head, box);
      buildBlocks(m, box);
      chat.appendChild(am);
    }
    return d;
  }
  // assistant
  const d = el("div", "msg asst");
  d.dataset.i = m.i;
  const box = el("div", null);
  d.append(asstHead(m), box);
  buildBlocks(m, box);
  chat.appendChild(d);
  return d;
}
function asstHead(m) {
  const head = el("div", "head");
  head.appendChild(el("div", "avatar", "A"));
  const rb = roleBadge(m.curRole);
  head.appendChild(el("span", "rbadge " + rb.cls, rb.label));
  head.appendChild(el("span", "aname", "Agent"));
  head.appendChild(el("span", "modeltag", m.model || ""));
  if (m.stage) head.appendChild(el("span", "modeltag", m.stage));
  if (m.ts) head.appendChild(el("span", "mtime", m.ts.slice(5)));
  return head;
}

/* typing effect */
let typeTimer = null;
function typeInto(bub, txt, done) {
  clearInterval(typeTimer);
  const caret = el("span", "caret");
  bub.textContent = "";
  bub.appendChild(caret);
  let i = 0;
  const stepChars = Math.max(1, Math.round(3 * speed));
  typeTimer = setInterval(() => {
    i += stepChars;
    if (i >= txt.length) {
      clearInterval(typeTimer);
      bub.textContent = txt;
      done();
    } else {
      bub.textContent = txt.slice(0, i);
      bub.appendChild(caret);
    }
  }, 30);
}

/* ================= playback engine ================= */
let cursor = 0, playing = false, speed = 1, mode = "replay", follow = true, advanceTimer = null;

function delayFor(m) {
  let d = 260;
  if (m.role === "user") d = 1500;
  else if (m.role === "roleswitch") d = 900;
  else {
    let tools = 0, texts = 0;
    for (const b of m.blocks) { if (b.t === "tool") tools++; else if (b.t === "text") texts++; }
    d = 320 + tools * 380 + texts * 520 + (m.blocks.length - tools - texts) * 160;
    d = Math.min(d, 3400);
  }
  return d / speed;
}
function step() {
  if (!playing) return;
  if (cursor >= N) { setPlaying(false); return; }
  const m = MSGS[cursor++];
  const isUser = m.role === "user";
  renderMessage(m, { typing: isUser && speed < 99 });
  updateScrub();
  if (cursor >= N) { setPlaying(false); updateScrub(); return; }
  const d = delayFor(m);
  advanceTimer = setTimeout(step, d);
}
function setPlaying(p) {
  playing = p;
  $("#playBtn").textContent = p ? "⏸ 暂停" : "▶ 播放";
  if (!p) { clearTimeout(advanceTimer); clearInterval(typeTimer); }
}
function play() { setPlaying(true); step(); }
$("#playBtn").addEventListener("click", () => {
  if (playing) setPlaying(false);
  else { if (cursor >= N) seek(0); play(); }
});
$("#nextBtn").addEventListener("click", () => {
  setPlaying(false);
  const next = STATS.userIdx.find(i => i >= cursor);
  seek(next === undefined ? N - 1 : next);
  setPlaying(true); step();
});

/* seek: render [0..idx] instantly */
function seek(idx) {
  setPlaying(false);
  chat.querySelectorAll(".msg, .rolebanner").forEach(n => n.remove());
  cursor = Math.min(idx + 1, N);
  for (let i = 0; i < cursor; i++) renderMessage(MSGS[i], {});
  updateScrub();
  jumpBottom(true);
}

/* ================= scrubber ================= */
const scrub = $("#scrub"), scrubFill = $("#scrubFill"), scrubTip = $("#scrubTip"), scrubStat = $("#scrubStat");
function updateScrub() {
  scrubFill.style.width = (cursor / N * 100) + "%";
  const doneUsers = STATS.userIdx.filter(i => i < cursor).length;
  const m = MSGS[Math.max(0, cursor - 1)];
  scrubStat.innerHTML = "消息 <b>" + cursor + "</b> / " + N +
    "　·　用户轮 <b>" + doneUsers + "</b> / " + STATS.userTurns +
    (m && m.stage ? "　·　" + m.stage : "");
  const chip = $("#stageChip");
  chip.textContent = m && m.stage ? m.stage : "初始化";
  document.querySelectorAll(".mark").forEach((mk, k) => {
    mk.classList.toggle("lit", STATS.userIdx[k] < cursor);
  });
}
(function buildMarks() {
  STATS.userIdx.forEach((idx, k) => {
    const mk = el("div", "mark");
    mk.style.left = (idx / N * 100) + "%";
    const m = MSGS[idx];
    const txt = m.blocks.map(b => (b.t === "text" ? b.md : "")).join(" ").replace(/\s+/g, " ").slice(0, 60);
    mk.addEventListener("mouseenter", () => {
      scrubTip.style.display = "block";
      scrubTip.style.left = mk.style.left;
      scrubTip.innerHTML = '<div class="t">第 ' + m.userN + ' 轮 · ' + (m.ts || "").slice(5) + " · 点击跳转</div>" + esc(txt);
    });
    mk.addEventListener("mouseleave", () => { scrubTip.style.display = "none"; });
    mk.addEventListener("click", e => { e.stopPropagation(); seek(idx); setPlaying(true); step(); });
    scrub.appendChild(mk);
  });
})();
function scrubPos(e) {
  const r = scrub.getBoundingClientRect();
  const frac = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
  return Math.round(frac * (N - 1));
}
scrub.addEventListener("click", e => { const i = scrubPos(e); seek(i); });
let scrubDrag = false;
scrub.addEventListener("pointerdown", e => { scrubDrag = true; scrub.setPointerCapture(e.pointerId); });
scrub.addEventListener("pointermove", e => {
  if (scrubDrag) { const i = scrubPos(e); scrubFill.style.width = (i / N * 100) + "%"; }
});
scrub.addEventListener("pointerup", e => {
  if (scrubDrag) { scrubDrag = false; seek(scrubPos(e)); }
});

/* ================= chat scroll / follow ================= */
const chatWrap = $("#chatWrap");
chatWrap.addEventListener("scroll", () => {
  const away = chatWrap.scrollHeight - chatWrap.scrollTop - chatWrap.clientHeight > 140;
  follow = !away;
  $("#followPill").style.display = away ? "block" : "none";
});
$("#followPill").addEventListener("click", () => { jumpBottom(true); follow = true; $("#followPill").style.display = "none"; });
function jumpBottom(smooth) {
  chatWrap.scrollTo({ top: chatWrap.scrollHeight, behavior: smooth ? "smooth" : "auto" });
}
const _origAppend = chat.appendChild.bind(chat);
chat.appendChild = node => { _origAppend(node); if (follow) jumpBottom(false); return node; };

/* ================= controls ================= */
$("#modeSeg").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  document.querySelectorAll("#modeSeg button").forEach(x => x.classList.toggle("on", x === b));
  mode = b.dataset.m;
  if (mode === "read") { setPlaying(false); seek(N - 1); }
});
$("#speedSeg").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  document.querySelectorAll("#speedSeg button").forEach(x => x.classList.toggle("on", x === b));
  speed = parseFloat(b.dataset.s);
});
$("#tglThink").addEventListener("click", e => {
  showThink = !showThink;
  e.currentTarget.classList.toggle("on", showThink);
  document.querySelectorAll(".blk-think, .blk-skill").forEach(n => n.style.display = showThink ? "" : "none");
});
$("#tglOut").addEventListener("click", e => {
  showOut = !showOut;
  e.currentTarget.classList.toggle("on", showOut);
  document.querySelectorAll(".tool-out").forEach(n => n.style.display = showOut ? "" : "none");
});
$("#sideToggle").addEventListener("click", () => $("#side").classList.toggle("show"));
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
  if (e.code === "Space") { e.preventDefault(); $("#playBtn").click(); }
  if (e.code === "ArrowRight" && e.shiftKey) $("#nextBtn").click();
});

/* ================= tabs ================= */
$("#tabs").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  document.querySelectorAll("#tabs button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll(".pane").forEach(p => p.classList.toggle("on", p.id === "tab-" + b.dataset.t));
  if (b.dataset.t === "3d") glResize();
});
const IMGS = {};
(CFG.imgs || []).forEach(im => { IMGS[im.key] = "data:image/png;base64," + im.b64; });
(function rendersTab() {
  const g = $("#rgrid");
  for (const im of (CFG.imgs || [])) {
    const k = im.key;
    const fig = el("figure");
    const img = new Image();
    img.src = IMGS[k];
    img.addEventListener("click", () => {
      const lb = $("#lightbox");
      lb.innerHTML = "";
      const big = new Image();
      big.src = IMGS[k];
      lb.appendChild(big);
      lb.style.display = "flex";
    });
    fig.append(img, el("figcaption", null, im.cap));
    g.appendChild(fig);
  }
})();
$("#lightbox").addEventListener("click", () => { $("#lightbox").style.display = "none"; });

/* ================= params & artifacts tabs ================= */
(function paramsTab() {
  const rows = CFG.params || [];
  const t = el("table", "ptable");
  t.innerHTML = "<tr><th>参数</th><th>终值</th><th>说明</th></tr>" +
    rows.map(r => "<tr><td class='k'>" + esc(r[0]) + "</td><td class='v'>" + esc(r[1]) + "</td><td class='c'>" + esc(r[2]) + "</td></tr>").join("");
  $("#tab-params .panebody").appendChild(t);
  if ((CFG.tags || []).length) {
    const tags = el("div");
    tags.innerHTML = '<div class="secttl">确定性命名面（QL 可索引）</div>' +
      CFG.tags.map(tg => '<span class="tagchip">' + esc(tg) + "</span>").join("") +
      (CFG.tagsNote ? '<p style="margin-top:8px;color:var(--ink-faint);font-size:11.5px">' + esc(CFG.tagsNote) + "</p>" : "");
    $("#tab-params .panebody").appendChild(tags);
  }
})();
(function outTab() {
  const A = CFG.artifacts || {};
  const files = A.files || [], vscripts = A.scripts || [], notes = A.notes || [];
  let html = "";
  if (files.length)
    html += '<div class="secttl">导出产物 · out/</div><div class="filelist">' +
      files.map(f => "<div><b>" + esc(f[0]) + "</b> <span class='sz'>" + esc(f[1]) + "</span> — " + esc(f[2]) + "</div>").join("") + "</div>";
  if (vscripts.length)
    html += '<div class="secttl">验证与探针脚本 · verify/</div><div class="filelist">' +
      vscripts.map(s => "<div>" + esc(s) + ".py</div>").join("") + "</div>";
  html += '<div class="secttl">会话统计</div><div class="filelist">' +
    "<div>工具调用 <b>" + STATS.toolTotal + "</b> 次（bash " + (STATS.tools.bash || 0) + " · edit " + (STATS.tools.edit || 0) + " · read " + (STATS.tools.read || 0) + " · write " + (STATS.tools.write || 0) + "）</div>" +
    "<div>验证器输出 ALL PASS <b>" + STATS.allPass + "</b> 次</div>" +
    notes.map(n => "<div>" + esc(n) + "</div>").join("") + "</div>";
  $("#tab-out .panebody").innerHTML = html;
})();
(function aboutTab() {
  const fmt = s => String(s)
    .replace(/\{N\}/g, N).replace(/\{tools\}/g, STATS.toolTotal).replace(/\{users\}/g, STATS.userTurns)
    .replace(/\{allPass\}/g, STATS.allPass).replace(/\{stlName\}/g, CFG.stl ? CFG.stl.name : "")
    .replace(/\{stlTris\}/g, CFG.stl ? (CFG.stl.tris || 0).toLocaleString() : "0");
  const paras = (CFG.about || []).map(p => "<p>" + fmt(p) + "</p>").join("");
  const hl = CFG.highlights ? "<p><b>看点</b>：" + fmt(CFG.highlights) + "</p>" : "";
  $("#tab-about .panebody").innerHTML =
    '<div class="about">' + paras + hl +
    '<p><b>操作</b>：<span class="kbd">空格</span> 播放/暂停 · <span class="kbd">⇧→</span> 跳到下一轮用户输入 · 点击进度条橙色刻度直达对应轮次 · 速度可调（×0.5–∞）·「阅读模式」一次渲染全部。</p>' +
    '<p style="color:var(--ink-faint);font-size:11.5px">会话 ' + esc(META.id) + " · 由 examples/demo_kit 从 transcript 自动生成本页</p></div>";
})();

/* ================= session card ================= */
(function sessionCard() {
  const dur = (() => {
    const a = new Date(META.start.replace(" ", "T")), b = new Date(META.end.replace(" ", "T"));
    const mins = Math.round((b - a) / 60000);
    return Math.floor(mins / 60) + " 小时 " + (mins % 60) + " 分";
  })();
  const extra = CFG.extraStat
    ? '<div class="stat"><b>' + esc(CFG.extraStat[0]) + "</b><span>" + esc(CFG.extraStat[1]) + "</span></div>"
    : "";
  $("#sessionCard").innerHTML =
    "<h2>" + esc(META.title) + " <span style='color:var(--accent2);font-size:12px'>" + esc(CFG.subtitle || "") + "</span></h2>" +
    "<div class='sid'>真实会话完整回放 · " + esc(META.start) + " → " + esc(META.end) + "（" + dur + "）· " + esc(META.id) + "</div>" +
    '<div class="statGrid">' +
    '<div class="stat"><b>' + N + "</b><span>消息总数</span></div>" +
    '<div class="stat"><b>' + STATS.userTurns + "</b><span>用户输入轮次</span></div>" +
    (stageRange ? '<div class="stat"><b>' + stageRange + "</b><span>建模阶段</span></div>" : "") +
    '<div class="stat"><b>' + STATS.toolTotal + "</b><span>工具调用</span></div>" +
    '<div class="stat"><b>' + STATS.allPass + "</b><span>验证 ALL PASS</span></div>" +
    '<div class="stat err"><b>' + (STATS.tools.edit || 0) + "</b><span>次编辑迭代</span></div>" +
    extra +
    "</div>";
  $("#metaLine").textContent = META.title + " · " + STATS.userTurns + " 轮用户输入 · " + STATS.toolTotal + " 次工具调用" + (stageRange ? " · " + stageRange : "");
})();

/* ================= three.js viewer ================= */
let glOK = false, renderer, scene, camera, controls, mesh, gridHelper, camTween = null;
const glCanvas = $("#gl");
function b64ToBuf(b64) {
  const bin = atob(b64);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  return buf.buffer;
}
function glInit() {
  try {
    renderer = new THREE.WebGLRenderer({ canvas: glCanvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputEncoding = THREE.sRGBEncoding;
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(38, 1, 1, 5000);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x2a3350, 0.95));
    const key = new THREE.DirectionalLight(0xffffff, 1.0);
    key.position.set(160, 240, 180);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x88aaff, 0.45);
    rim.position.set(-180, -40, -160);
    scene.add(rim);
    const geo = new THREE.STLLoader().parse(b64ToBuf(CFG.stl.b64));
    geo.computeBoundingBox();
    const bb = geo.boundingBox, size = new THREE.Vector3();
    bb.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z) || 1;
    const scale = 150 / maxDim;
    geo.center();
    geo.translate(0, size.y * scale / 2, 0);
    geo.scale(scale, scale, scale);
    geo.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({ color: 0xccd8ea, metalness: 0.32, roughness: 0.4 });
    mesh = new THREE.Mesh(geo, mat);
    scene.add(mesh);
    gridHelper = new THREE.GridHelper(420, 42, 0x33415e, 0x1a2338);
    scene.add(gridHelper);
    controls = new THREE.OrbitControls(camera, glCanvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.5;
    controls.target.set(0, 30, 0);
    setView("iso", true);
    glOK = true;
    $("#glLoad").style.display = "none";
    glResize();
    renderer.setAnimationLoop(glLoop);
  } catch (e) {
    $("#glLoad").textContent = "3D 初始化失败：" + e.message;
  }
}
const VIEWS = {
  iso: { t: 0.72, p: 1.05, d: 340 },
  front: { t: Math.PI / 2, p: Math.PI / 2 - 0.02, d: 360 },
  top: { t: 0.0001, p: 0.28, d: 380 },
};
function setView(name, instant) {
  const v = VIEWS[name];
  const pos = new THREE.Vector3().setFromSphericalCoords(v.d, v.p, v.t).add(controls.target);
  if (instant) { camera.position.copy(pos); controls.update(); camTween = null; }
  else camTween = { pos, left: 18 };
}
function glLoop() {
  if (!glOK) return;
  if (camTween) {
    camera.position.lerp(camTween.pos, 0.14);
    camTween.left--;
    if (camera.position.distanceTo(camTween.pos) < 1.5 || camTween.left <= 0) camTween = null;
  }
  controls.update();
  renderer.render(scene, camera);
}
function glResize() {
  if (!glOK) return;
  const w = glCanvas.clientWidth || 1, h = glCanvas.clientHeight || 1;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
new ResizeObserver(glResize).observe($("#glWrap"));
$("#glBar").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  const act = b.dataset.a;
  if (act === "rotate") { controls.autoRotate = !controls.autoRotate; b.classList.toggle("on", controls.autoRotate); }
  else if (act === "wire") { mesh.material.wireframe = !mesh.material.wireframe; b.classList.toggle("on", mesh.material.wireframe); }
  else if (act === "reset") { setView("iso"); $("#glBar [data-a=rotate]").classList.add("on"); controls.autoRotate = true; mesh.material.wireframe = false; }
  else setView(act);
});
glInit();
(function glCaption() {
  const c = $("#glCap");
  if (c && CFG.stl && CFG.stl.glCap) c.textContent = CFG.stl.glCap;
})();

/* ================= boot ================= */
updateScrub();
renderMessage(MSGS[0], { typing: false }); // 第一条用户需求先呈上
cursor = 1;
updateScrub();
