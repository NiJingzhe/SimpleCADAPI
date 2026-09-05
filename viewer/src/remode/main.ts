// Reverse-engineering studio (re-mode): annotate a STEP target for an agent.
//
// Left: original STEP viewport with entity picking, circle/lasso region
// annotation and a free-form composer — picked entities and operation tips
// appear as inline colored chips, peers of plain text. Right top: rebuilt
// result (v3 .scadpkg) plus the agent's comparison image. Right bottom:
// FTC source (CodeMirror, syntax highlighted), feature DAG tree, evaluation
// report, last submission, and the live context preview.
//
// Governance: the UI only selects and describes. It never edits geometry —
// every rebuild flows through the agent's code, and only this UI writes
// submissions.

import '../style.css';
import './remode.css';
import { Box, ClipboardCheck, Columns2, Dot, Eraser, Eye, Inbox, Lasso, Maximize2, MousePointer2, Plus, Send, Slash, Square, SquareCode, Workflow, createIcons } from 'lucide';
import { PythonEditor } from '../components/source-dock';
import { openCadPackage, type PackageFiles } from '../product-package';
import { buildFederatedFeatureModel, type ModelDocument, type SceneManifest } from '../scene2';
import { MARK_COLORS, SceneView, type CameraState, type PickResult, type SelectionMode } from '../scene-view';
import { TokenComposer, type ComposerTokenKind } from './composer';
import { reStudioEditorTheme } from './code-theme';
import { FeatureTreeView } from './feature-tree';
import { OpSuggest, type SuggestOperation } from './op-suggest';
import { opCategoryResolver, renderMarkup } from './markup';

const lucideIcons = { Box, ClipboardCheck, Columns2, Dot, Eraser, Eye, Inbox, Lasso, Maximize2, MousePointer2, Plus, Send, Slash, Square, SquareCode, Workflow };

function iconMarkup(name: keyof typeof lucideIcons, className = 'ui-icon'): string {
  const iconName = name.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
  return `<i data-lucide="${iconName}" class="${className}" aria-hidden="true"></i>`;
}

/** Transient (pre-ADD) viewport highlight + live lasso stroke; must read
 *  against both pale models and the dark chrome, and stay clear of the
 *  committed-annotation MARK_COLORS palette. */
const DRAFT_COLOR = '#00c8ff';

type DraftEntry = { nodeId: string; entityId: string; canonical: string; kind: string };

type Annotation = {
  annotation_id: string;
  kind: 'free';
  intent: 'free';
  text: string;
  entries: DraftEntry[];
  operations: string[];
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

type RegionResolveResponse = { entity_ids: string[]; count: string | number };

type OperationTip = {
  op_id: string;
  label: string;
  category: string;
  api: string[];
  reads: string[];
  doc_refs: string[];
  hint: string;
};

type OperationsPayload = {
  categories: Array<{ id: string; label: string; description: string }>;
  operations: OperationTip[];
  errors: string[];
};

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) throw new Error('re-mode root is missing');

app.innerHTML = `
  <main class="re-shell">
    <header class="re-topbar">
      <div class="re-brand"><span class="re-brand-mark">RE</span><div><strong>re-studio</strong><span id="re-target-name">no target</span></div></div>
      <div class="re-top-stats" id="re-top-stats"></div>
      <div class="re-top-actions">
        <span id="re-agent-state" class="re-agent-state">connecting</span>
        <button id="re-fit-button" class="re-quiet-button" type="button" title="fit both viewports">${iconMarkup('Maximize2')}<span>FIT</span></button>
        <button id="re-submit-button" class="re-submit-button" type="button" disabled>${iconMarkup('Send')}<span>SUBMIT</span></button>
      </div>
    </header>
    <section class="re-workspace" id="re-workspace">
      <section class="re-left" id="re-left">
        <div class="re-toolbar">
          <div class="re-tool-group"><span class="re-tool-label">SELECT</span>
            <button class="re-mode-button active" data-selection-mode="face" type="button">${iconMarkup('Square')}FACE</button>
            <button class="re-mode-button" data-selection-mode="edge" type="button">${iconMarkup('Slash')}EDGE</button>
            <button class="re-mode-button" data-selection-mode="vertex" type="button">${iconMarkup('Dot')}VERTEX</button>
          </div>
          <div class="re-tool-group"><span class="re-tool-label">DRAW</span>
            <button class="re-mode-button active" data-draw-mode="off" type="button">${iconMarkup('MousePointer2')}OFF</button>
            <button class="re-mode-button" data-draw-mode="lasso" type="button">${iconMarkup('Lasso')}LASSO</button>
          </div>
          <div class="re-tool-group">
            <button id="re-clear-selection" class="re-mode-button" type="button" title="clear draft picks">${iconMarkup('Eraser')}CLEAR</button>
          </div>
        </div>
        <div class="re-viewport" id="re-original-viewport">
          <canvas id="re-annotate-canvas"></canvas>
          <div id="re-original-loading" class="re-loading"><span class="spinner"></span><span id="re-original-status">loading scene</span></div>
        </div>
        <div class="re-selection-info" id="re-selection-info"><span class="re-muted">click faces / draw a lasso to select</span></div>
        <div class="re-composer">
          <div class="re-capsule-list" id="re-capsule-list"></div>
          <div class="re-composer-box" id="re-composer-box">
            <button id="re-add-annotation" class="re-add-button" type="button" disabled title="add annotation">${iconMarkup('Plus')}</button>
          </div>
        </div>
      </section>
      <div class="re-col-resizer" id="re-col-resizer" title="drag to resize"></div>
      <section class="re-right" id="re-right">
        <section class="re-rebuilt" id="re-rebuilt">
          <div class="re-tabbar">
            <button class="re-tab active" data-rebuilt-tab="model" type="button">${iconMarkup('Box')}REBUILT MODEL</button>
            <button class="re-tab" data-rebuilt-tab="comparison" type="button">${iconMarkup('Columns2')}COMPARISON</button>
            <span id="re-rebuilt-state" class="re-muted re-tab-state">waiting for agent</span>
          </div>
          <div class="re-rebuilt-body">
            <div class="re-viewport" id="re-rebuilt-viewport"></div>
            <img id="re-comparison-img" alt="comparison" hidden />
          </div>
        </section>
        <div class="re-row-resizer" id="re-row-resizer" title="drag to resize"></div>
        <section class="re-bottom" id="re-bottom">
          <div class="re-tabbar">
            <button class="re-tab active" data-bottom-tab="source" type="button">${iconMarkup('SquareCode')}SOURCE</button>
            <button class="re-tab" data-bottom-tab="features" type="button">${iconMarkup('Workflow')}FEATURE</button>
            <button class="re-tab" data-bottom-tab="evaluation" type="button">${iconMarkup('ClipboardCheck')}EVALUATION</button>
            <button class="re-tab" data-bottom-tab="submission" type="button">${iconMarkup('Inbox')}SUBMISSION</button>
            <button class="re-tab" data-bottom-tab="context" type="button">${iconMarkup('Eye')}CONTEXT PREVIEW</button>
          </div>
          <div class="re-bottom-body">
            <div class="re-source-panel" id="re-source-panel">
              <div class="re-source-tabs" id="re-source-tabs"></div>
              <div class="re-source-editor" id="re-source-editor"></div>
            </div>
            <div class="tree feature-tree re-feature-tree" id="re-features" hidden></div>
            <div class="re-feature-list re-feature-fallback" id="re-features-fallback" hidden></div>
            <pre class="re-code" id="re-evaluation" hidden></pre>
            <div class="re-code" id="re-submission" hidden></div>
            <div class="re-code" id="re-context" hidden></div>
          </div>
        </section>
      </section>
    </section>
    <footer class="re-footer"><span id="re-status">starting</span><span>UI selects and describes · code is the single source of truth</span></footer>
  </main>`;

renderMarkupIcons();
function renderMarkupIcons(): void {
  createIcons({ icons: lucideIcons, attrs: { 'stroke-width': 1.8 }, root: app! });
}

const $ = <T extends HTMLElement>(selector: string): T => app!.querySelector<T>(selector)!;

const originalHost = $<HTMLDivElement>('div#re-original-viewport');
const annotateCanvas = $<HTMLCanvasElement>('canvas#re-annotate-canvas');
const originalLoading = $<HTMLDivElement>('div#re-original-loading');
const originalStatus = $<HTMLSpanElement>('span#re-original-status');
const rebuiltHost = $<HTMLDivElement>('div#re-rebuilt-viewport');
const comparisonImg = $<HTMLImageElement>('img#re-comparison-img');
const selectionInfo = $<HTMLDivElement>('div#re-selection-info');
const capsuleList = $<HTMLDivElement>('div#re-capsule-list');
const composerBox = $<HTMLDivElement>('div#re-composer-box');
const addAnnotationButton = $<HTMLButtonElement>('button#re-add-annotation');
const submitButton = $<HTMLButtonElement>('button#re-submit-button');
const agentState = $('span#re-agent-state');
const topStats = $('div#re-top-stats');
const statusLine = $('span#re-status');
const workspaceEl = $<HTMLDivElement>('section#re-workspace');
const leftSection = $<HTMLElement>('section#re-left');
const rebuiltSection = $<HTMLElement>('section#re-rebuilt');
const rightSection = $<HTMLElement>('section#re-right');
const colResizer = $<HTMLDivElement>('div#re-col-resizer');
const rowResizer = $<HTMLDivElement>('div#re-row-resizer');
const sourcePanel = $<HTMLDivElement>('div#re-source-panel');
const sourceTabs = $<HTMLDivElement>('div#re-source-tabs');
const sourceEditorHost = $<HTMLDivElement>('div#re-source-editor');
const featureList = $<HTMLDivElement>('div#re-features');
const featureListFallback = $<HTMLDivElement>('div#re-features-fallback');
const evaluationPre = $<HTMLPreElement>('pre#re-evaluation');
const submissionDiv = $<HTMLDivElement>('div#re-submission');
const contextDiv = $<HTMLDivElement>('div#re-context');
const rebuiltState = $<HTMLSpanElement>('span#re-rebuilt-state');

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

// -- free-form composer (entity + operation chips inline with text) -----------

const draft = new Map<string, DraftEntry>(); // canonical id -> picked entry

function markColor(index: number): string {
  return MARK_COLORS[index % MARK_COLORS.length];
}

function setStatus(message: string): void {
  statusLine.textContent = message;
}

function composerKind(kind: string): ComposerTokenKind {
  if (kind === 'edge' || kind === 'vertex' || kind === 'face') return kind;
  return 'face';
}

function postSelectEvent(): void {
  void fetch('/api/event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: 'select', entity_ids: [...draft.keys()] }),
  });
}

function addSelectionEntry(nodeId: string, entityId: string, kind: string, quiet = false): void {
  const canonical = canonicalBySceneId.get(entityId);
  if (!canonical || draft.has(canonical)) return;
  draft.set(canonical, { nodeId, entityId, canonical, kind });
  originalView.addMark(nodeId, entityId, DRAFT_COLOR);
  composer.insertToken({ token: canonical, label: canonical, kind: composerKind(kind) });
  if (!quiet) void postSelectEvent();
  refreshSelectionInfo();
}

function toggleSelectionEntry(nodeId: string, entityId: string, kind: string): void {
  const canonical = canonicalBySceneId.get(entityId);
  if (canonical && draft.has(canonical)) {
    draft.delete(canonical);
    originalView.removeMark(`${nodeId}::${entityId}`);
    composer.removeToken(canonical);
    refreshSelectionInfo();
    return;
  }
  addSelectionEntry(nodeId, entityId, kind);
}

function refreshSelectionInfo(): void {
  const entries = [...draft.values()];
  addAnnotationButton.disabled = composer.isEmpty();
  if (!entries.length) {
    selectionInfo.innerHTML = '<span class="re-muted">click faces / draw a lasso to select — picks become tags in the composer</span>';
    return;
  }
  const kinds = new Map<string, number>();
  for (const entry of entries) kinds.set(entry.kind, (kinds.get(entry.kind) ?? 0) + 1);
  selectionInfo.innerHTML = `<strong>${entries.length} tagged</strong> <span class="re-muted">${[...kinds].map(([kind, count]) => `${count} ${kind}`).join(' · ')}</span> <span class="re-id-list" title="${entries.map((entry) => entry.canonical).join(', ')}">${entries.slice(0, 6).map((entry) => entry.canonical).join(', ')}${entries.length > 6 ? ' …' : ''}</span>`;
}

const composer: TokenComposer = new TokenComposer({
  placeholder: 'whats your idea to rebuild ?',
  onChange: () => refreshSelectionInfo(),
  onCommit: () => addAnnotation(),
  onKeydown: (event): boolean => opSuggest.handleKeydown(event),
});
composerBox.append(composer.host);
const opSuggest: OpSuggest = new OpSuggest(composer);
composerBox.prepend(opSuggest.popup);

// -- annotations ---------------------------------------------------------------

const annotations: Annotation[] = [];
let annotationCounter = 0;
let drawMode: 'off' | 'lasso' = 'off';
let drawPoints: Array<[number, number]> = [];
let drawing = false;
let currentPolygon: Array<[number, number]> | null = null;

function addAnnotation(): void {
  const text = composer.value().trim();
  const tokens = composer.listTokens();
  const entityTokens = tokens.filter((token) => token.kind !== 'op');
  if (!text && !entityTokens.length) return;
  const entries = entityTokens
    .map((token) => draft.get(token.token))
    .filter((entry): entry is DraftEntry => Boolean(entry));
  const operations = [...new Set(tokens.filter((token) => token.kind === 'op').map((token) => token.token.replace(/^op:/, '')))];
  const color = markColor(annotations.length);
  const annotation: Annotation = {
    annotation_id: `a${++annotationCounter}-${Date.now().toString(36)}`,
    kind: 'free',
    intent: 'free',
    text,
    entries,
    operations,
    screen_polygon: currentPolygon ?? undefined,
    color,
    created_at: new Date().toISOString(),
  };
  for (const entry of entries) {
    originalView.removeMark(`${entry.nodeId}::${entry.entityId}`);
    originalView.addMark(entry.nodeId, entry.entityId, color);
  }
  annotations.push(annotation);
  draft.clear();
  composer.clear();
  currentPolygon = null;
  void postAnnotation('add', annotation);
  renderCapsules();
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
  renderCapsules();
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
    operations: annotation.operations,
    screen_polygon: annotation.screen_polygon ?? null,
    color: annotation.color,
    created_at: annotation.created_at,
  };
}

function renderCapsules(): void {
  capsuleList.replaceChildren();
  annotations.forEach((annotation) => {
    const capsule = document.createElement('div');
    capsule.className = 're-capsule';
    capsule.style.setProperty('--chip-color', annotation.color);
    const content = document.createElement('span');
    content.className = 're-capsule-content';
    content.append(renderMarkup(annotation.text, opCategory()));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 're-capsule-remove';
    remove.title = 'remove annotation';
    remove.textContent = '×';
    remove.addEventListener('click', (event) => {
      event.stopPropagation();
      removeAnnotation(annotation.annotation_id);
    });
    const bubble = document.createElement('div');
    bubble.className = 're-capsule-bubble';
    bubble.append(renderMarkup(annotation.text, opCategory()));
    capsule.addEventListener('click', () => {
      // re-highlight this annotation's entities in the viewport
      for (const entry of annotation.entries) originalView.addMark(entry.nodeId, entry.entityId, annotation.color);
    });
    capsule.append(content, remove, bubble);
    capsuleList.append(capsule);
  });
}

let operationsPayload: OperationsPayload | null = null;

function opCategory(): (opId: string) => string | undefined {
  return opCategoryResolver(operationsPayload?.operations ?? []);
}

function renderContextPreview(): void {
  const payload = {
    annotations: annotations.map(serializeAnnotation),
    _server_adds: 'per-entity one-level neighborhood cards (entity geometry, edges with adjacent faces, vertices), operation tips (api, reads, doc_refs, hint), target summary, viewport snapshot',
  };
  contextDiv.innerHTML = `<pre class="re-code">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character] || character);
}

// -- slash operation suggest (server registry, content lives in md files) ------

async function loadOperations(): Promise<void> {
  try {
    const response = await fetch('/api/operations');
    if (!response.ok) {
      setStatus('operation registry unavailable — slash suggest offline');
      return;
    }
    const payload = (await response.json()) as OperationsPayload;
    operationsPayload = payload;
    opSuggest.setOperations(payload.operations as SuggestOperation[]);
    if (payload.errors.length) setStatus(`operation registry: ${payload.errors.join('; ')}`);
  } catch {
    setStatus('operation registry unreachable — slash suggest offline');
  }
}

// -- annotation canvas (lasso) -----------------------------------------------------

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
    context.strokeStyle = DRAFT_COLOR;
    context.lineWidth = 2;
    context.setLineDash([6, 4]);
    strokePolygon(context, drawPoints, true);
    context.setLineDash([]);
  }
}

function strokePolygon(context: CanvasRenderingContext2D, polygon: Array<[number, number]>, open = false): void {
  context.beginPath();
  polygon.forEach(([x, y], index) => (index ? context.lineTo(x, y) : context.moveTo(x, y)));
  if (!open) context.closePath();
  context.stroke();
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
  const polygon = drawPoints;
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
    const wantedKind = originalView.selectionMode === 'vertex' ? 'vertex' : 'face';
    let added = 0;
    for (const canonical of result.entity_ids) {
      const sceneId = sceneIdByCanonical.get(canonical);
      const nodeId = sceneId ? nodeIdBySceneId.get(sceneId) : undefined;
      if (!sceneId || !nodeId) continue;
      const entity = originalView.entityFor(nodeId, sceneId);
      const kind = entity?.kind ?? 'face';
      if (kind !== wantedKind) continue;
      addSelectionEntry(nodeId, sceneId, kind, true);
      added += 1;
    }
    currentPolygon = polygon;
    refreshSelectionInfo();
    setStatus(`region resolved: ${added} entities tagged`);
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
  const kind = result.mode;
  toggleSelectionEntry(result.nodeId, result.entityId, kind);
  if (result.entityId && draft.has(canonicalBySceneId.get(result.entityId) ?? '')) void inspectEntity(result);
};

async function inspectEntity(result: PickResult): Promise<void> {
  const canonical = canonicalBySceneId.get(result.entityId!);
  const entry = canonical ? draft.get(canonical) : undefined;
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
    drawMode = (button.dataset.drawMode as 'off' | 'lasso');
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
  for (const entry of draft.values()) originalView.removeMark(`${entry.nodeId}::${entry.entityId}`);
  draft.clear();
  composer.clear();
  currentPolygon = null;
  refreshSelectionInfo();
  renderAnnotationsCanvas();
});

$('button#re-fit-button').addEventListener('click', () => {
  originalView.frame();
  rebuiltView.frame();
});

// -- drag resizers (left/right columns, rebuilt/dock split) --------------------

function bindResizerDrag(
  handle: HTMLElement,
  bodyClass: string,
  onMove: (event: PointerEvent) => void,
): void {
  handle.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    handle.classList.add('dragging');
    document.body.classList.add(bodyClass);
    handle.setPointerCapture(event.pointerId);
    const move = (moveEvent: PointerEvent): void => onMove(moveEvent);
    const finish = (): void => {
      handle.classList.remove('dragging');
      document.body.classList.remove(bodyClass);
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', finish);
      handle.removeEventListener('pointercancel', finish);
    };
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', finish);
    handle.addEventListener('pointercancel', finish);
  });
}

const LEFT_MIN_WIDTH = 340;
const REBUILT_MIN_HEIGHT = 140;

bindResizerDrag(colResizer, 'resizing-panels', (event) => {
  const startX = Number(colResizer.dataset.startX ?? event.clientX);
  const startWidth = Number(colResizer.dataset.startWidth ?? leftSection.getBoundingClientRect().width);
  const maxWidth = workspaceEl.clientWidth - 380;
  const width = Math.round(Math.min(Math.max(startWidth + (event.clientX - startX), LEFT_MIN_WIDTH), Math.max(maxWidth, LEFT_MIN_WIDTH)));
  workspaceEl.style.setProperty('--re-left-width', `${width}px`);
});
colResizer.addEventListener('pointerdown', (event) => {
  colResizer.dataset.startX = String(event.clientX);
  colResizer.dataset.startWidth = String(leftSection.getBoundingClientRect().width);
});

bindResizerDrag(rowResizer, 'resizing-dock', (event) => {
  const startY = Number(rowResizer.dataset.startY ?? event.clientY);
  const startHeight = Number(rowResizer.dataset.startHeight ?? rebuiltSection.getBoundingClientRect().height);
  const maxHeight = rightSection.clientHeight - 220;
  const height = Math.round(Math.min(Math.max(startHeight + (event.clientY - startY), REBUILT_MIN_HEIGHT), Math.max(maxHeight, REBUILT_MIN_HEIGHT)));
  rightSection.style.setProperty('--re-rebuilt-height', `${height}px`);
});
rowResizer.addEventListener('pointerdown', (event) => {
  rowResizer.dataset.startY = String(event.clientY);
  rowResizer.dataset.startHeight = String(rebuiltSection.getBoundingClientRect().height);
});

addAnnotationButton.addEventListener('click', addAnnotation);

submitButton.addEventListener('click', async () => {
  submitButton.disabled = true;
  const snapshot = originalView.snapshotPng();
  try {
    const response = await fetch('/api/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        annotations: annotations.map(serializeAnnotation),
        note: '',
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

// -- source panel (CodeMirror) + feature DAG tree ------------------------------

const sourceEditor = new PythonEditor({ parent: sourceEditorHost, theme: reStudioEditorTheme });
const sourceFiles = new Map<string, string>();
let currentSourcePath: string | null = null;
let packageModel: ModelDocument | null = null;

const featureTree = new FeatureTreeView(featureList, {});

function showSourceFile(path: string, reveal?: { line: number; endLine: number }): void {
  const content = sourceFiles.get(path);
  if (content === undefined) return;
  if (path !== currentSourcePath) {
    currentSourcePath = path;
    sourceEditor.setContent(content);
    renderSourceTabs();
  }
  if (reveal) sourceEditor.revealLines(reveal.line, reveal.endLine);
  else sourceEditor.clearHighlight();
}

function setSourceFile(path: string, content: string, prefer = false): void {
  sourceFiles.set(path, content);
  if (prefer || currentSourcePath === null) showSourceFile(path);
  renderSourceTabs();
}

function renderSourceTabs(): void {
  sourceTabs.replaceChildren();
  if (sourceFiles.size <= 1) return;
  for (const path of sourceFiles.keys()) {
    const tab = document.createElement('button');
    tab.type = 'button';
    tab.className = `re-source-tab${path === currentSourcePath ? ' active' : ''}`;
    tab.textContent = path;
    tab.addEventListener('click', () => showSourceFile(path));
    sourceTabs.append(tab);
  }
}

function updateFeatureVisibility(): void {
  featureList.hidden = !packageModel;
  featureListFallback.hidden = packageModel !== null;
}

/** FTC header fallback before the agent captures a package with a real DAG. */

function renderFallbackFeatureTree(source: string): void {
  if (packageModel) return;
  updateFeatureVisibility();
  featureListFallback.replaceChildren();
  const headerPattern = /^#\s*----\s*feature:\s*(.+?)\s*\((.+?)\)\s*----/gm;
  let match: RegExpExecArray | null;
  let found = false;
  while ((match = headerPattern.exec(source))) {
    found = true;
    const row = document.createElement('div');
    row.className = 're-feature-row';
    row.innerHTML = `<span class="re-feature-op">${escapeHtml(match[2])}</span><span class="re-feature-label">${escapeHtml(match[1])}</span>`;
    featureListFallback.append(row);
  }
  if (!found) featureListFallback.innerHTML = '<div class="re-muted" style="padding:8px">no feature headers found in rebuild.py</div>';
}

function selectBottomTab(tab: string): void {
  for (const item of Array.from(document.querySelectorAll<HTMLButtonElement>('.re-tab[data-bottom-tab]'))) {
    item.classList.toggle('active', item.dataset.bottomTab === tab);
  }
  sourcePanel.hidden = tab !== 'source';
  if (tab === 'features') updateFeatureVisibility();
  else {
    featureList.hidden = true;
    featureListFallback.hidden = true;
  }
  evaluationPre.hidden = tab !== 'evaluation';
  submissionDiv.hidden = tab !== 'submission';
  contextDiv.hidden = tab !== 'context';
  if (tab === 'source') sourceEditor.requestMeasure();
}

for (const button of Array.from(document.querySelectorAll<HTMLButtonElement>('.re-tab[data-bottom-tab]'))) {
  button.addEventListener('click', () => selectBottomTab(button.dataset.bottomTab ?? 'source'));
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
  const federated = buildFederatedFeatureModel(manifest, opened.files);
  packageModel = federated.model;
  for (const [path, content] of federated.sources) {
    const duplicate = [...sourceFiles.entries()].some(([, text]) => text === content);
    if (!duplicate) setSourceFile(path, content);
  }
  featureTree.setModel(packageModel);
  updateFeatureVisibility();
}

async function loadArtifactText(name: 'rebuild.py' | 'evaluation.json', mtime: number): Promise<void> {
  const response = await fetch(`/api/artifacts/${name}?v=${mtime}`);
  if (!response.ok) return;
  const text = await response.text();
  if (name === 'rebuild.py') {
    setSourceFile('rebuild.py', text, true);
    renderFallbackFeatureTree(text);
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
      ${(annotation.operations as string[] | undefined)?.length ? `<span>${(annotation.operations as string[]).length} ops</span>` : ''}
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
    __reDebug?: { originalView: SceneView; rebuiltView: SceneView; annotations: Annotation[]; composer: TokenComposer };
  }
}
window.__reDebug = { originalView, rebuiltView, annotations, composer };

new ResizeObserver(() => sizeAnnotateCanvas()).observe(originalHost);
sizeAnnotateCanvas();
renderContextPreview();
refreshSelectionInfo();
void loadSubmissionTab();
void loadOperations();
void loadOriginalScene();
startPolling();
const retryOriginal = window.setInterval(() => {
  if (!originalLoading.classList.contains('hidden')) void loadOriginalScene();
  else window.clearInterval(retryOriginal);
}, 2500);
