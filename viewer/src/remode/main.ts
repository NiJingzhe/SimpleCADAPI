// Reverse-engineering studio (re-mode): annotate a STEP target for an agent.
//
// Left: original STEP viewport with entity picking, circle/lasso region
// annotation and an intent palette. Right top: rebuilt result (v3 .scadpkg)
// plus the agent's comparison image. Right bottom: FTC source, feature tree,
// evaluation report, last submission, and the live context preview.
//
// Governance: the UI only selects and describes. It never edits geometry —
// every rebuild flows through the agent's code, and only this UI writes
// submissions.

import '../style.css';
import './remode.css';
import { MARK_COLORS, SceneView, type CameraState, type PickResult, type SelectionMode } from '../scene-view';
import { openCadPackage, type PackageFiles } from '../product-package';
import type { SceneManifest } from '../scene2';

type IntentKind = 'sketch_base' | 'revolve_axis' | 'pattern_seed' | 'fillet_group' | 'exact_copy' | 'question' | 'other';

const INTENT_LABELS: Array<{ value: IntentKind; label: string }> = [
  { value: 'sketch_base', label: 'sketch base' },
  { value: 'revolve_axis', label: 'revolve axis' },
  { value: 'pattern_seed', label: 'pattern seed' },
  { value: 'fillet_group', label: 'fillet group' },
  { value: 'exact_copy', label: 'exact-copy region' },
  { value: 'question', label: 'ask agent' },
  { value: 'other', label: 'other' },
];

type SelectionEntry = { nodeId: string; entityId: string; canonical: string; kind: string };

type Annotation = {
  annotation_id: string;
  kind: 'entity_set';
  intent: IntentKind;
  text: string;
  entries: SelectionEntry[];
  screen_polygon?: Array<[number, number]>;
  color: string;
  created_at: string;
};

type SessionPayload = {
  target: { name: string | null; path: string | null; present: boolean };
  scene: { state: string; error: string | null; face_count?: number; edge_count?: number; vertex_count?: number; body_count?: number };
  annotations: number;
  submission: { seq: number; submitted_at: string } | null;
  artifacts: Record<string, { present: boolean; mtime?: number; size?: number }>;
};

type RegionResolveResponse = { entity_ids: string[]; count: number };

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) throw new Error('re-mode root is missing');

app.innerHTML = `
  <main class="re-shell">
    <header class="re-topbar">
      <div class="re-brand"><span class="re-brand-mark">RE</span><div><strong>re-studio</strong><span id="re-target-name">no target</span></div></div>
      <div class="re-top-stats" id="re-top-stats"></div>
      <div class="re-top-actions">
        <span id="re-agent-state" class="re-agent-state">connecting</span>
        <button id="re-fit-button" class="re-quiet-button" type="button">FIT</button>
        <button id="re-submit-button" class="re-submit-button" type="button" disabled>SUBMIT</button>
      </div>
    </header>
    <section class="re-workspace">
      <section class="re-left">
        <div class="re-toolbar">
          <div class="re-tool-group"><span class="re-tool-label">SELECT</span>
            <button class="re-mode-button active" data-selection-mode="face" type="button">FACE</button>
            <button class="re-mode-button" data-selection-mode="edge" type="button">EDGE</button>
            <button class="re-mode-button" data-selection-mode="vertex" type="button">VERTEX</button>
            <button class="re-mode-button" data-selection-mode="component" type="button">BODY</button>
          </div>
          <div class="re-tool-group"><span class="re-tool-label">DRAW</span>
            <button class="re-mode-button" data-draw-mode="off" type="button">OFF</button>
            <button class="re-mode-button" data-draw-mode="circle" type="button">◯ CIRCLE</button>
            <button class="re-mode-button" data-draw-mode="lasso" type="button">～ LASSO</button>
          </div>
          <div class="re-tool-group">
            <button id="re-clear-selection" class="re-mode-button" type="button">CLEAR SEL</button>
          </div>
        </div>
        <div class="re-viewport" id="re-original-viewport">
          <canvas id="re-annotate-canvas"></canvas>
          <div id="re-original-loading" class="re-loading"><span class="spinner"></span><span id="re-original-status">loading scene</span></div>
        </div>
        <div class="re-selection-info" id="re-selection-info"><span class="re-muted">click faces / draw a region to select</span></div>
        <div class="re-composer">
          <div class="re-composer-row">
            <select id="re-intent-select" class="re-input"></select>
            <input id="re-note-input" class="re-input re-note-input" placeholder="annotation text (what is this region / how is it made)" />
            <button id="re-add-annotation" class="re-add-button" type="button" disabled>ADD</button>
          </div>
          <div class="re-round-row">
            <input id="re-round-note" class="re-input re-round-note" placeholder="round note for the agent (optional)" />
          </div>
          <div class="re-chip-list" id="re-chip-list"></div>
        </div>
      </section>
      <section class="re-right">
        <section class="re-rebuilt">
          <div class="re-tabbar">
            <button class="re-tab active" data-rebuilt-tab="model" type="button">REBUILT MODEL</button>
            <button class="re-tab" data-rebuilt-tab="comparison" type="button">COMPARISON</button>
            <span id="re-rebuilt-state" class="re-muted re-tab-state">waiting for agent</span>
          </div>
          <div class="re-rebuilt-body">
            <div class="re-viewport" id="re-rebuilt-viewport"></div>
            <img id="re-comparison-img" alt="comparison" hidden />
          </div>
        </section>
        <section class="re-bottom">
          <div class="re-tabbar">
            <button class="re-tab active" data-bottom-tab="source" type="button">SOURCE</button>
            <button class="re-tab" data-bottom-tab="features" type="button">FEATURE TREE</button>
            <button class="re-tab" data-bottom-tab="evaluation" type="button">EVALUATION</button>
            <button class="re-tab" data-bottom-tab="submission" type="button">SUBMISSION</button>
            <button class="re-tab" data-bottom-tab="context" type="button">CONTEXT PREVIEW</button>
          </div>
          <div class="re-bottom-body">
            <pre class="re-code" id="re-source" hidden></pre>
            <div class="re-feature-list" id="re-features" hidden></div>
            <pre class="re-code" id="re-evaluation" hidden></pre>
            <div class="re-code" id="re-submission" hidden></div>
            <div class="re-code" id="re-context" hidden></div>
          </div>
        </section>
      </section>
    </section>
    <footer class="re-footer"><span id="re-status">starting</span><span class="re-muted">UI selects and describes · code is the single source of truth</span></footer>
  </main>`;

const $ = <T extends HTMLElement>(selector: string): T => app!.querySelector<T>(selector)!;

const originalHost = $<HTMLDivElement>('div#re-original-viewport');
const annotateCanvas = $<HTMLCanvasElement>('canvas#re-annotate-canvas');
const originalLoading = $<HTMLDivElement>('div#re-original-loading');
const originalStatus = $<HTMLSpanElement>('span#re-original-status');
const rebuiltHost = $<HTMLDivElement>('div#re-rebuilt-viewport');
const comparisonImg = $<HTMLImageElement>('img#re-comparison-img');
const selectionInfo = $<HTMLDivElement>('div#re-selection-info');
const chipList = $<HTMLDivElement>('div#re-chip-list');
const intentSelect = $<HTMLSelectElement>('select#re-intent-select');
const noteInput = $<HTMLInputElement>('input#re-note-input');
const roundNoteInput = $<HTMLInputElement>('input#re-round-note');
const addAnnotationButton = $<HTMLButtonElement>('button#re-add-annotation');
const submitButton = $<HTMLButtonElement>('button#re-submit-button');
const agentState = $('span#re-agent-state');
const topStats = $('div#re-top-stats');
const statusLine = $('span#re-status');
const sourcePre = $<HTMLPreElement>('pre#re-source');
const featureList = $<HTMLDivElement>('div#re-features');
const evaluationPre = $<HTMLPreElement>('pre#re-evaluation');
const submissionDiv = $<HTMLDivElement>('div#re-submission');
const contextDiv = $<HTMLDivElement>('div#re-context');
const rebuiltState = $<HTMLSpanElement>('span#re-rebuilt-state');

for (const intent of INTENT_LABELS) {
  const option = document.createElement('option');
  option.value = intent.value;
  option.textContent = intent.label;
  intentSelect.append(option);
}

const originalView = new SceneView(originalHost, { selectionMode: 'face' });
const rebuiltView = new SceneView(rebuiltHost, { selectionMode: 'face' });

// -- maps between canonical ids and scene entity ids --------------------------

const canonicalBySceneId = new Map<string, string>();
const sceneIdByCanonical = new Map<string, string>();
const nodeIdBySceneId = new Map<string, string>();

function indexSidecarIds(view: SceneView): void {
  canonicalBySceneId.clear();
  sceneIdByCanonical.clear();
  nodeIdBySceneId.clear();
  for (const node of view.nodes) {
    const sidecar = view.sidecarFor(node);
    if (!sidecar) continue;
    for (const entity of sidecar.entities) {
      const canonical = typeof entity.topo_id === 'string' ? entity.topo_id : null;
      if (!canonical) continue;
      canonicalBySceneId.set(entity.entity_id, canonical);
      sceneIdByCanonical.set(canonical, entity.entity_id);
      nodeIdBySceneId.set(entity.entity_id, node.node_id);
    }
  }
}

// -- selection + annotations ----------------------------------------------------

let selection = new Map<string, SelectionEntry>(); // scene entity id -> entry
const annotations: Annotation[] = [];
let annotationCounter = 0;
let drawMode: 'off' | 'circle' | 'lasso' = 'off';
let drawPoints: Array<[number, number]> = [];
let drawing = false;
let currentPolygon: Array<[number, number]> | null = null;

function markColor(index: number): string {
  return MARK_COLORS[index % MARK_COLORS.length];
}

function setStatus(message: string): void {
  statusLine.textContent = message;
}

function addSelectionEntry(nodeId: string, entityId: string, kind: string, quiet = false): void {
  const canonical = canonicalBySceneId.get(entityId);
  if (!canonical) return;
  if (selection.has(entityId)) return;
  selection.set(entityId, { nodeId, entityId, canonical, kind });
  originalView.addMark(nodeId, entityId, '#fff04d');
  if (!quiet) {
    void fetch('/api/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'select', entity_ids: [...selection.values()].map((entry) => entry.canonical) }),
    });
  }
  refreshSelectionInfo();
}

function toggleSelectionEntry(nodeId: string, entityId: string, kind: string): void {
  if (selection.has(entityId)) {
    selection.delete(entityId);
    originalView.removeMark(`${nodeId}::${entityId}`);
    refreshSelectionInfo();
    return;
  }
  addSelectionEntry(nodeId, entityId, kind);
}

function refreshSelectionInfo(): void {
  const entries = [...selection.values()];
  if (!entries.length) {
    selectionInfo.innerHTML = '<span class="re-muted">click faces / draw a region to select</span>';
    addAnnotationButton.disabled = true;
    return;
  }
  addAnnotationButton.disabled = false;
  const kinds = new Map<string, number>();
  for (const entry of entries) kinds.set(entry.kind, (kinds.get(entry.kind) ?? 0) + 1);
  selectionInfo.innerHTML = `<strong>${entries.length} selected</strong> <span class="re-muted">${[...kinds].map(([kind, count]) => `${count} ${kind}`).join(' · ')}</span> <span class="re-id-list" title="${entries.map((entry) => entry.canonical).join(', ')}">${entries.slice(0, 6).map((entry) => entry.canonical).join(', ')}${entries.length > 6 ? ' …' : ''}</span>`;
}

function annotationColorCount(): number {
  return annotations.length;
}

function addAnnotation(): void {
  const entries = [...selection.values()];
  if (!entries.length) return;
  const color = markColor(annotationColorCount());
  const annotation: Annotation = {
    annotation_id: `a${++annotationCounter}-${Date.now().toString(36)}`,
    kind: 'entity_set',
    intent: intentSelect.value as IntentKind,
    text: noteInput.value.trim(),
    entries,
    screen_polygon: currentPolygon ?? undefined,
    color,
    created_at: new Date().toISOString(),
  };
  for (const entry of entries) {
    originalView.removeMark(`${entry.nodeId}::${entry.entityId}`);
  }
  for (const entry of entries) {
    originalView.addMark(entry.nodeId, entry.entityId, color);
  }
  annotations.push(annotation);
  selection.clear();
  currentPolygon = null;
  noteInput.value = '';
  void postAnnotation('add', annotation);
  renderChips();
  renderAnnotationsCanvas();
  renderContextPreview();
}

function removeAnnotation(annotationId: string): void {
  const index = annotations.findIndex((item) => item.annotation_id === annotationId);
  if (index < 0) return;
  const annotation = annotations[index];
  for (const entry of annotation.entries) {
    originalView.removeMark(`${entry.nodeId}::${entry.entityId}`);
  }
  annotations.splice(index, 1);
  void postAnnotation('remove', annotation);
  renderChips();
  renderAnnotationsCanvas();
  renderContextPreview();
}

async function postAnnotation(action: 'add' | 'remove', annotation: Annotation): Promise<void> {
  try {
    await fetch('/api/annotate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, annotation: serializeAnnotation(annotation) }),
    });
  } catch {
    setStatus('annotation log unreachable');
  }
}

function serializeAnnotation(annotation: Annotation): Record<string, unknown> {
  return {
    annotation_id: annotation.annotation_id,
    kind: annotation.kind,
    intent: annotation.intent,
    text: annotation.text,
    entity_ids: annotation.entries.map((entry) => entry.canonical),
    screen_polygon: annotation.screen_polygon ?? null,
    color: annotation.color,
    created_at: annotation.created_at,
  };
}

function renderChips(): void {
  chipList.replaceChildren();
  annotations.forEach((annotation) => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 're-chip';
    chip.style.setProperty('--chip-color', annotation.color);
    chip.innerHTML = `<span class="re-chip-dot"></span><strong>${annotation.intent}</strong><span class="re-chip-count">${annotation.entries.length}</span>${annotation.text ? `<span class="re-chip-text">${annotation.text}</span>` : ''}<span class="re-chip-remove" title="remove">×</span>`;
    chip.addEventListener('click', (event) => {
      if ((event.target as HTMLElement).classList.contains('re-chip-remove')) {
        removeAnnotation(annotation.annotation_id);
        return;
      }
      for (const entry of annotation.entries) originalView.addMark(entry.nodeId, entry.entityId, annotation.color);
    });
    chipList.append(chip);
  });
}

function renderContextPreview(): void {
  const payload = {
    note: roundNoteInput.value,
    annotations: annotations.map(serializeAnnotation),
    _server_adds: 'per-entity describe_entity context (geometry, bounds, adjacency), target summary, viewport snapshot',
  };
  contextDiv.innerHTML = `<pre class="re-code">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character] || character);
}

// -- annotation canvas (circle / lasso) -------------------------------------------

type CanvasContext = CanvasRenderingContext2D | null;

function canvasContext(): CanvasContext {
  return annotateCanvas.getContext('2d');
}

function sizeAnnotateCanvas(): void {
  const bounds = originalHost.getBoundingClientRect();
  const ratio = Math.min(window.devicePixelRatio, 2);
  annotateCanvas.width = Math.max(1, Math.round(bounds.width * ratio));
  annotateCanvas.height = Math.max(1, Math.round(bounds.height * ratio));
  annotateCanvas.style.width = `${bounds.width}px`;
  annotateCanvas.style.height = `${bounds.height}px`;
  canvasContext()?.setTransform(ratio, 0, 0, ratio, 0, 0);
  renderAnnotationsCanvas();
}

function ellipsePolygon(center: [number, number], radiusX: number, radiusY: number, samples = 28): Array<[number, number]> {
  const points: Array<[number, number]> = [];
  for (let index = 0; index < samples; index += 1) {
    const angle = (index / samples) * Math.PI * 2;
    points.push([center[0] + radiusX * Math.cos(angle), center[1] + radiusY * Math.sin(angle)]);
  }
  return points;
}

function renderAnnotationsCanvas(): void {
  const context = canvasContext();
  if (!context) return;
  const bounds = originalHost.getBoundingClientRect();
  context.clearRect(0, 0, bounds.width, bounds.height);
  for (const annotation of annotations) {
    if (!annotation.screen_polygon) continue;
    context.strokeStyle = annotation.color;
    context.lineWidth = 2;
    context.setLineDash([]);
    strokePolygon(context, annotation.screen_polygon);
  }
  if (drawMode !== 'off' && drawPoints.length > 1) {
    context.strokeStyle = '#fff04d';
    context.lineWidth = 2;
    context.setLineDash([6, 4]);
    strokePolygon(context, drawMode === 'circle' ? circleFromPoints(drawPoints) : drawPoints, drawMode === 'lasso');
    context.setLineDash([]);
  }
}

function strokePolygon(context: CanvasRenderingContext2D, polygon: Array<[number, number]>, open = false): void {
  context.beginPath();
  polygon.forEach(([x, y], index) => (index ? context.lineTo(x, y) : context.moveTo(x, y)));
  if (!open) context.closePath();
  context.stroke();
}

function circleFromPoints(points: Array<[number, number]>): Array<[number, number]> {
  const start = points[0];
  const end = points[points.length - 1];
  const radius = Math.max(Math.hypot(end[0] - start[0], end[1] - start[1]), 8);
  return ellipsePolygon(start, radius, radius);
}

annotateCanvas.addEventListener('pointerdown', (event) => {
  if (drawMode === 'off') return;
  drawing = true;
  annotateCanvas.setPointerCapture(event.pointerId);
  drawPoints = [canvasPoint(event)];
  renderAnnotationsCanvas();
});

annotateCanvas.addEventListener('pointermove', (event) => {
  if (!drawing) return;
  const point = canvasPoint(event);
  const last = drawPoints[drawPoints.length - 1];
  if (drawMode === 'lasso' && last && Math.hypot(point[0] - last[0], point[1] - last[1]) < 3) return;
  drawPoints.push(point);
  renderAnnotationsCanvas();
});

annotateCanvas.addEventListener('pointerup', async () => {
  if (!drawing) return;
  drawing = false;
  const polygon = drawMode === 'circle' ? circleFromPoints(drawPoints) : drawPoints;
  drawPoints = [];
  if (polygon.length < 3) {
    renderAnnotationsCanvas();
    return;
  }
  await resolveRegion(polygon);
});

async function resolveRegion(polygon: Array<[number, number]>): Promise<void> {
  try {
    const response = await fetch('/api/region/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ camera: originalView.getCameraState(), polygon }),
    });
    if (!response.ok) {
      setStatus(`region resolve failed: ${await response.text()}`);
      renderAnnotationsCanvas();
      return;
    }
    const result = (await response.json()) as RegionResolveResponse;
    let added = 0;
    for (const canonical of result.entity_ids) {
      const sceneId = sceneIdByCanonical.get(canonical);
      const nodeId = sceneId ? nodeIdBySceneId.get(sceneId) : undefined;
      if (!sceneId || !nodeId) continue;
      const entity = originalView.entityFor(nodeId, sceneId);
      addSelectionEntry(nodeId, sceneId, entity?.kind ?? 'face', true);
      added += 1;
    }
    currentPolygon = polygon;
    refreshSelectionInfo();
    setStatus(`region resolved: ${added} entities`);
  } catch {
    setStatus('region resolve unreachable');
  }
  renderAnnotationsCanvas();
}

function canvasPoint(event: PointerEvent): [number, number] {
  const bounds = annotateCanvas.getBoundingClientRect();
  return [event.clientX - bounds.left, event.clientY - bounds.top];
}

// -- wiring -------------------------------------------------------------------

originalView.onPick = (result: PickResult) => {
  if (drawMode !== 'off' || !result.entityId) return;
  toggleSelectionEntry(result.nodeId, result.entityId, result.mode === 'component' ? 'body' : result.mode);
  if (selection.has(result.entityId)) void inspectEntity(result);
};

async function inspectEntity(result: PickResult): Promise<void> {
  const entry = selection.get(result.entityId!);
  if (!entry) return;
  try {
    const response = await fetch(`/api/entity?id=${encodeURIComponent(entry.canonical)}`);
    if (!response.ok) return;
    const descriptor = await response.json();
    const adjacency = descriptor.adjacency?.direct?.slice(0, 24) ?? [];
    const rows: string[] = [];
    if (descriptor.geometry?.type) rows.push(`type ${descriptor.geometry.type}`);
    if (descriptor.geometry?.area) rows.push(`area ${Number(descriptor.geometry.area).toFixed(2)} mm²`);
    if (descriptor.geometry?.length) rows.push(`len ${Number(descriptor.geometry.length).toFixed(2)} mm`);
    selectionInfo.innerHTML = `<strong>${escapeHtml(entry.canonical)}</strong> <span class="re-muted">${rows.join(' · ') || entry.kind}</span><details class="re-details"><summary>adjacency (${adjacency.length}) + geometry</summary><pre class="re-mini-json">${escapeHtml(JSON.stringify({ geometry: descriptor.geometry, adjacency: descriptor.adjacency }, null, 1).slice(0, 4000))}</pre></details>`;
  } catch {
    /* inspector is best-effort */
  }
}

for (const button of Array.from(document.querySelectorAll<HTMLButtonElement>('.re-mode-button[data-selection-mode]'))) {
  button.addEventListener('click', () => {
    originalView.setSelectionMode(button.dataset.selectionMode as SelectionMode);
    document.querySelectorAll<HTMLButtonElement>('.re-mode-button[data-selection-mode]').forEach((item) => item.classList.toggle('active', item === button));
  });
}

for (const button of Array.from(document.querySelectorAll<HTMLButtonElement>('.re-mode-button[data-draw-mode]'))) {
  button.addEventListener('click', () => {
    drawMode = (button.dataset.drawMode as 'off' | 'circle' | 'lasso');
    document.querySelectorAll<HTMLButtonElement>('.re-mode-button[data-draw-mode]').forEach((item) => item.classList.toggle('active', item === button));
    annotateCanvas.classList.toggle('re-draw-active', drawMode !== 'off');
    originalHost.classList.toggle('re-draw-cursor', drawMode !== 'off');
    if (drawMode === 'off') {
      drawPoints = [];
      renderAnnotationsCanvas();
    }
  });
}

$('button#re-clear-selection').addEventListener('click', () => {
  for (const entry of selection.values()) originalView.removeMark(`${entry.nodeId}::${entry.entityId}`);
  selection.clear();
  currentPolygon = null;
  refreshSelectionInfo();
  renderAnnotationsCanvas();
});

$('button#re-fit-button').addEventListener('click', () => {
  originalView.frame();
  rebuiltView.frame();
});

addAnnotationButton.addEventListener('click', addAnnotation);
noteInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') addAnnotation();
});
roundNoteInput.addEventListener('input', renderContextPreview);

submitButton.addEventListener('click', async () => {
  submitButton.disabled = true;
  const snapshot = originalView.snapshotPng();
  try {
    const response = await fetch('/api/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        annotations: annotations.map(serializeAnnotation),
        note: roundNoteInput.value,
        snapshot_png: snapshot,
      }),
    });
    if (!response.ok) {
      setStatus(`submit failed: ${await response.text()}`);
      return;
    }
    const result = await response.json();
    agentState.textContent = `submitted #${result.seq} — waiting for agent`;
    agentState.classList.add('re-agent-waiting');
    setStatus(`submission #${result.seq} delivered; agent is reconstructing`);
    void loadSubmissionTab();
  } catch {
    setStatus('submit unreachable');
  } finally {
    submitButton.disabled = false;
  }
});

for (const button of Array.from(document.querySelectorAll<HTMLButtonElement>('.re-tab[data-rebuilt-tab]'))) {
  button.addEventListener('click', () => {
    const tab = button.dataset.rebuiltTab;
    document.querySelectorAll<HTMLButtonElement>('.re-tab[data-rebuilt-tab]').forEach((item) => item.classList.toggle('active', item === button));
    rebuiltHost.hidden = tab !== 'model';
    comparisonImg.hidden = tab !== 'comparison';
  });
}

for (const button of Array.from(document.querySelectorAll<HTMLButtonElement>('.re-tab[data-bottom-tab]'))) {
  button.addEventListener('click', () => {
    const tab = button.dataset.bottomTab;
    document.querySelectorAll<HTMLButtonElement>('.re-tab[data-bottom-tab]').forEach((item) => item.classList.toggle('active', item === button));
    sourcePre.hidden = tab !== 'source';
    featureList.hidden = tab !== 'features';
    evaluationPre.hidden = tab !== 'evaluation';
    submissionDiv.hidden = tab !== 'submission';
    contextDiv.hidden = tab !== 'context';
  });
}

// -- session polling + artifact loading ------------------------------------------

let lastArtifactMtimes: Record<string, number> = {};

function decodeFiles(encoded: Record<string, string>): PackageFiles {
  const files: PackageFiles = {};
  for (const [uri, base64] of Object.entries(encoded)) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    files[uri] = bytes;
  }
  return files;
}

async function loadOriginalScene(): Promise<void> {
  const response = await fetch('/api/scene/original');
  if (response.status === 503) {
    originalStatus.textContent = 'scene is building…';
    return;
  }
  if (!response.ok) {
    originalStatus.textContent = `scene failed: ${await response.text()}`;
    return;
  }
  const payload = await response.json();
  await originalView.loadScene(decodeFiles(payload.files));
  indexSidecarIds(originalView);
  originalLoading.classList.add('hidden');
  submitButton.disabled = false;
  setStatus('scene ready — select and annotate');
}

async function loadRebuilt(mtime: number): Promise<void> {
  const response = await fetch(`/api/artifacts/rebuilt.scadpkg?v=${mtime}`);
  if (!response.ok) return;
  const opened = await openCadPackage(new Uint8Array(await response.arrayBuffer()));
  await rebuiltView.loadScene(opened.files);
  rebuiltState.textContent = 'rebuilt package loaded';
  const manifest = JSON.parse(new TextDecoder().decode(opened.files['scene.json'])) as SceneManifest;
  renderFeatureTree(manifest);
}

function renderFeatureTree(manifest: SceneManifest | null): void {
  const rows: string[] = [];
  if (manifest?.feature_index?.length) {
    for (const feature of manifest.feature_index) {
      rows.push(`<button class="re-feature-row" type="button"><span class="re-feature-op">${escapeHtml(feature.op)}</span><span class="re-feature-label">${escapeHtml(feature.label ?? feature.node_id)}</span></button>`);
    }
  } else {
    const source = sourcePre.textContent ?? '';
    const headerPattern = /^#\s*----\s*feature:\s*(.+?)\s*\((.+?)\)\s*----/gm;
    let match: RegExpExecArray | null;
    while ((match = headerPattern.exec(source))) {
      rows.push(`<button class="re-feature-row" type="button"><span class="re-feature-op">${escapeHtml(match[2])}</span><span class="re-feature-label">${escapeHtml(match[1])}</span></button>`);
    }
  }
  featureList.innerHTML = rows.length ? rows.join('') : '<div class="re-muted" style="padding:8px">no feature tree yet — the agent has not produced a rebuild</div>';
}

async function loadArtifactText(name: 'rebuild.py' | 'evaluation.json', mtime: number): Promise<void> {
  const response = await fetch(`/api/artifacts/${name}?v=${mtime}`);
  if (!response.ok) return;
  const text = await response.text();
  if (name === 'rebuild.py') {
    sourcePre.textContent = text;
    renderFeatureTree(null);
  } else {
    try {
      evaluationPre.textContent = JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      evaluationPre.textContent = text;
    }
  }
}

async function loadSubmissionTab(): Promise<void> {
  const response = await fetch('/api/submission');
  if (!response.ok) {
    submissionDiv.innerHTML = '<div class="re-muted" style="padding:8px">no submission yet</div>';
    return;
  }
  const submission = await response.json();
  const annotationRows = (submission.annotations ?? []).map((annotation: Record<string, unknown>) => `
    <div class="re-submission-row">
      <span class="re-chip-dot" style="--chip-color: ${String(annotation.color ?? '#888')}"></span>
      <strong>${escapeHtml(String(annotation.intent))}</strong>
      <span>${(annotation.entity_ids as string[] | undefined)?.length ?? 0} entities</span>
      ${annotation.text ? `<span class="re-muted">${escapeHtml(String(annotation.text))}</span>` : ''}
      ${(annotation.unresolved_entity_ids as string[] | undefined)?.length ? `<span class="re-warn">unresolved: ${(annotation.unresolved_entity_ids as string[]).join(', ')}</span>` : ''}
    </div>`).join('');
  submissionDiv.innerHTML = `<div class="re-submission"><div class="re-muted">submission #${submission.submission_seq} · ${escapeHtml(String(submission.submitted_at ?? ''))}</div>${annotationRows || '<div class="re-muted">no annotations</div>'}${submission.note ? `<div class="re-note">note: ${escapeHtml(String(submission.note))}</div>` : ''}</div>`;
}

function updateSessionState(session: SessionPayload): void {
  $('span#re-target-name').textContent = session.target.name ?? 'no target';
  if (session.scene.state === 'ready') {
    topStats.textContent = `${session.scene.body_count ?? '?'} bodies · ${session.scene.face_count ?? '?'} faces · ${session.scene.edge_count ?? '?'} edges · ${annotations.length} annotations`;
  } else {
    topStats.textContent = `scene ${session.scene.state}`;
  }
  let changed = false;
  for (const [name, artifact] of Object.entries(session.artifacts)) {
    const mtime = artifact.mtime ?? 0;
    if (artifact.present && lastArtifactMtimes[name] !== mtime) {
      changed = true;
      lastArtifactMtimes[name] = mtime;
      if (name === 'rebuilt.scadpkg') void loadRebuilt(mtime);
      if (name === 'rebuild.py') void loadArtifactText('rebuild.py', mtime);
      if (name === 'evaluation.json') void loadArtifactText('evaluation.json', mtime);
      if (name === 'comparison.png') comparisonImg.src = `/api/artifacts/comparison.png?v=${mtime}`;
    }
    if (!artifact.present && lastArtifactMtimes[name]) delete lastArtifactMtimes[name];
  }
  if (changed && session.artifacts['rebuilt.scadpkg'].present) {
    agentState.textContent = 'agent artifacts updated';
    agentState.classList.remove('re-agent-waiting');
  }
}

let pollTimer: number | null = null;

function startPolling(): void {
  pollTimer = window.setInterval(async () => {
    try {
      const response = await fetch('/api/session');
      if (!response.ok) return;
      updateSessionState(await response.json());
    } catch {
      /* server restarting */
    }
  }, 1200);
}

// -- boot ----------------------------------------------------------------------

// Debug/console access for the internal tool (also used by e2e verification).
declare global {
  interface Window {
    __reDebug?: { originalView: SceneView; rebuiltView: SceneView; annotations: Annotation[] };
  }
}
window.__reDebug = { originalView, rebuiltView, annotations };

new ResizeObserver(() => sizeAnnotateCanvas()).observe(originalHost);
sizeAnnotateCanvas();
renderContextPreview();
void loadSubmissionTab();
void loadOriginalScene();
startPolling();
const retryOriginal = window.setInterval(() => {
  if (!originalLoading.classList.contains('hidden')) void loadOriginalScene();
  else window.clearInterval(retryOriginal);
}, 2500);
