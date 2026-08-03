import './style.css';

import { unzipSync, strFromU8 } from 'fflate';
import {
  Box,
  Boxes,
  Combine,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Copy,
  CopyCheck,
  Eye,
  EyeOff,
  GitBranch,
  Link,
  Layers,
  LayoutDashboard,
  Maximize2,
  PackageOpen,
  Plus,
  Rotate3d,
  ScanFace,
  Scissors,
  Spline,
  Workflow,
  createIcons,
} from 'lucide';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { bindClickSelection } from './components/click-selection';
import { bindResizablePanels } from './components/panel-resizer';
import { SourceDock } from './components/source-dock';

type Vec3 = [number, number, number];
type Bounds = { min: Vec3; max: Vec3 };
type Transform = { origin: Vec3; x_axis: Vec3; y_axis: Vec3; z_axis: Vec3 };
type Appearance = { appearance_id: string; name: string | null; base_color: [number, number, number, 1]; metallic: number; roughness: number; alpha_mode: 'opaque' | 'mask' | 'blend'; double_sided: boolean; edge_color: [number, number, number, 1] };
type SourceRecord = Record<string, unknown> & { kind: string; root_id?: string; graph_id?: string; node_id?: string; output_slot?: number; component_path?: string[] };
type Definition = { definition_id: string; kind: string; name: string | null; source: SourceRecord; sdk_metadata: Record<string, unknown>; geometry_asset_id?: string; edge_asset_id?: string; entity_asset_id?: string; appearance_id?: string };
type SceneNode = { node_id: string; parent_node_id: string | null; order: number; definition_id: string; name: string | null; transform: Transform; visible: boolean; selectable: boolean; source: SourceRecord; sdk_metadata: Record<string, unknown> };
type Asset = { asset_id: string; uri: string; byte_length: number; content_hash: string; scene_local_bounds: Bounds; asset_to_scene: number[] };
type Entity = { entity_id: string; kind: 'solid' | 'face' | 'edge' | 'vertex'; parent_entity_ids: string[]; child_entity_ids: string[]; source: SourceRecord; properties: Record<string, unknown>; geometry: Record<string, unknown>; sdk_connector_frame: Transform | null; render_status: string; connector_binding_status: string; semantic_binding_ids: string[]; evaluated_tags: string[]; sdk_metadata: Record<string, unknown> };
type EntityAsset = { entity_asset_id: string; uri: string; byte_length: number; content_hash: string };
type FaceGroup = { entity_id: string; first_index: number; index_count: number };
type SourceFile = { path: string; uri: string; media_type: string; byte_length: number; content_hash: string };
type EmbeddedSource = { artifact_hash?: string; embedded_artifact_uri?: string; embedded_artifact_byte_length?: number; source_files?: SourceFile[] };
type SceneManifest = { schema_version: string; scene_id: string; revision: string; generator: { profile: string; simplecadapi_version: string; ocp_version: string }; source: EmbeddedSource; presentation_source?: EmbeddedSource; coordinate_system: { length_unit: string; up_axis: string }; definitions: Definition[]; nodes: SceneNode[]; geometry_assets: Asset[]; edge_assets: Asset[]; appearances: Appearance[]; entity_assets: EntityAsset[]; connectors: Array<{ connector_snapshot_id: string; owner_definition_id: string; name: string | null; anchor_kind: string; target?: { entity_asset_id: string; entity_id: string } }> };
type PackageFiles = Record<string, Uint8Array>;
type EntitySidecar = { entities: Entity[]; face_groups: FaceGroup[]; edge_groups?: FaceGroup[] };
type PackageRecord = { uri: string; byte_length: number; content_hash: string };
type OperationSource = { path?: string | null; line: number; column: number; end_line: number; end_column: number; call_text: string; callsite_id: string; assignment_targets: string[] };
type ModelNode = { node_id: string; op: string; params: Record<string, unknown>; inputs: string[]; output_count?: number; tags?: string[]; display?: { label?: string; category?: string; summary?: string }; source?: OperationSource };
type ModelDocument = { graph: { graph_id: string; nodes: ModelNode[] }; leaf_ids?: string[] };
type SelectionMode = 'component' | 'solid' | 'face' | 'edge' | 'vertex';

const MAX_PACKAGE_BYTES = 256 * 1024 * 1024;
const MAX_PACKAGE_MEMBERS = 10_000;
const MAX_UNPACKED_BYTES = 512 * 1024 * 1024;
const MAX_MEMBER_BYTES = 256 * 1024 * 1024;
const MAX_SCENE_JSON_BYTES = 8 * 1024 * 1024;
const MAX_COMPRESSION_RATIO = 100;

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) throw new Error('viewer root is missing');

const lucideIcons = {
  Box,
  Boxes,
  Combine,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Copy,
  CopyCheck,
  Eye,
  EyeOff,
  GitBranch,
  Link,
  Layers,
  LayoutDashboard,
  Maximize2,
  PackageOpen,
  Plus,
  Rotate3d,
  ScanFace,
  Scissors,
  Spline,
  Workflow,
};

function iconMarkup(name: keyof typeof lucideIcons, className = 'ui-icon'): string {
  const iconName = name.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
  return `<i data-lucide="${iconName}" class="${className}" aria-hidden="true"></i>`;
}

function renderIcons(root: Element): void {
  createIcons({
    icons: lucideIcons,
    attrs: { 'stroke-width': 1.8 },
    root,
  });
}

app.innerHTML = `
  <main class="shell">
    <header class="topbar">
      <div class="brand"><span class="brand-mark">SC</span><div><strong>SimpleCAD</strong><span>evaluated scene viewer</span></div></div>
       <div class="top-actions"><button id="open-button" class="quiet-button">${iconMarkup('PackageOpen')}<span>Open .scene.zip</span></button><input id="file-input" type="file" accept=".zip,.scene.zip,application/zip" hidden /></div>
    </header>
    <section class="workspace">
       <aside id="navigator-panel" class="panel tree-panel"><div class="panel-heading"><div><span class="eyebrow">MODEL NAVIGATOR</span><h1 id="scene-title">Loading scene</h1></div></div><div class="navigator-tabs" role="tablist" aria-label="Model navigator views"><button id="components-tab" class="navigator-tab active" role="tab" aria-selected="true" aria-controls="components-view"><span>${iconMarkup('Boxes', 'tab-icon')}</span><span>Components</span><span id="node-count" class="count">0</span></button><button id="features-tab" class="navigator-tab" role="tab" aria-selected="false" aria-controls="features-view"><span>${iconMarkup('Workflow', 'tab-icon')}</span><span>Features</span><span id="feature-count" class="count">0</span></button></div><div id="components-view" class="navigator-view active" role="tabpanel" aria-labelledby="components-tab"><div id="tree" class="tree"></div></div><div id="features-view" class="navigator-view" role="tabpanel" aria-labelledby="features-tab" hidden><div id="feature-tree" class="tree feature-tree"><div class="tree-empty">Open a model-backed scene to inspect its operations.</div></div></div></aside>
       <div id="navigator-resizer" class="panel-resizer" role="separator" aria-label="Resize model navigator" aria-orientation="vertical" tabindex="0"></div>
       <section id="viewport-column" class="viewport-wrap">
          <div class="viewport-stage"><div id="viewport" class="viewport"><div id="loading" class="loading"><span class="spinner"></span><span>Loading evaluated package</span></div><div id="hud" class="hud"><span id="status-dot" class="status-dot"></span><span id="status">Waiting for package</span></div><div class="viewport-tools"><div class="selection-tools" aria-label="Selection intent"><span class="tool-label">SELECT</span><button class="selection-mode active" data-selection-mode="component" title="Select components">${iconMarkup('Boxes')}<span>COMPONENT</span></button><button class="selection-mode" data-selection-mode="solid" title="Select solids">${iconMarkup('Box')}<span>SOLID</span></button><button class="selection-mode" data-selection-mode="face" title="Select faces">${iconMarkup('ScanFace')}<span>FACE</span></button><button class="selection-mode" data-selection-mode="edge" title="Select edges">${iconMarkup('Spline')}<span>EDGE</span></button><button class="selection-mode" data-selection-mode="vertex" title="Select vertices">${iconMarkup('CircleDot')}<span>VERTEX</span></button></div><button id="fit-button" title="Fit all">${iconMarkup('Maximize2')}<span>FIT</span></button></div></div></div>
       </section>
       <div id="inspector-resizer" class="panel-resizer" role="separator" aria-label="Resize Inspector" aria-orientation="vertical" tabindex="0"></div>
        <aside id="inspector-panel" class="panel details-panel"><div class="panel-heading"><span class="eyebrow">INSPECTOR</span><span id="selection-kind" class="tag">SCENE</span></div><div id="details" class="details"><div class="empty-state"><span class="empty-cross">${iconMarkup('Box', 'empty-state-icon')}</span><strong>Select an occurrence</strong><span>Choose a node or face in the viewport to inspect evaluated data.</span></div></div></aside>
       <div id="source-dock-resizer" class="source-dock-resizer" role="separator" aria-label="Resize source code panel" aria-orientation="horizontal" tabindex="0" hidden></div>
       <section id="source-dock" class="source-dock" aria-label="Embedded source code" hidden>
         <aside class="source-files-panel">
           <div class="source-dock-heading"><span class="eyebrow">SOURCE FILES</span><span id="source-file-count" class="count">0</span></div>
           <div id="source-file-list" class="source-file-list" role="listbox" aria-label="Embedded source files"></div>
         </aside>
         <div id="source-files-resizer" class="source-files-resizer" role="separator" aria-label="Resize source file list" aria-orientation="vertical" tabindex="0"></div>
         <section class="source-editor-panel">
           <div class="source-editor-heading"><span id="source-active-path">No source file selected</span><button id="source-close-button" class="source-close-button" type="button" aria-label="Close source code panel">×</button></div>
           <div id="source-editor" class="source-editor"></div>
           <div id="source-empty-state" class="source-empty-state">Open a model package with embedded source files.</div>
         </section>
       </section>
    </section>
     <footer class="footer"><span id="package-meta">No package loaded</span><span class="footer-actions"><button id="source-toggle-button" class="footer-button" type="button" aria-expanded="false" disabled>Source</button><span class="footer-note">CAD-local precision retained · GLB transport assets</span></span></footer>
  </main>`;

renderIcons(app);

const viewport = document.querySelector<HTMLDivElement>('#viewport')!;
const loading = document.querySelector<HTMLDivElement>('#loading')!;
const sceneTitle = document.querySelector<HTMLHeadingElement>('#scene-title')!;
const tree = document.querySelector<HTMLDivElement>('#tree')!;
const details = document.querySelector<HTMLDivElement>('#details')!;
const selectionKind = document.querySelector<HTMLSpanElement>('#selection-kind')!;
const nodeCount = document.querySelector<HTMLSpanElement>('#node-count')!;
const status = document.querySelector<HTMLSpanElement>('#status')!;
const statusDot = document.querySelector<HTMLSpanElement>('#status-dot')!;
const packageMeta = document.querySelector<HTMLSpanElement>('#package-meta')!;
const workspace = document.querySelector<HTMLElement>('.workspace')!;
const navigatorPanel = document.querySelector<HTMLElement>('#navigator-panel')!;
const inspectorPanel = document.querySelector<HTMLElement>('#inspector-panel')!;
const navigatorResizer = document.querySelector<HTMLElement>('#navigator-resizer')!;
const inspectorResizer = document.querySelector<HTMLElement>('#inspector-resizer')!;
const featureTree = document.querySelector<HTMLDivElement>('#feature-tree')!;
const featureCount = document.querySelector<HTMLSpanElement>('#feature-count')!;
const componentsTab = document.querySelector<HTMLButtonElement>('#components-tab')!;
const featuresTab = document.querySelector<HTMLButtonElement>('#features-tab')!;
const componentsView = document.querySelector<HTMLDivElement>('#components-view')!;
const featuresView = document.querySelector<HTMLDivElement>('#features-view')!;
const sourceDock = new SourceDock({
  dock: document.querySelector<HTMLElement>('#source-dock')!,
  resizer: document.querySelector<HTMLElement>('#source-dock-resizer')!,
  fileListResizer: document.querySelector<HTMLElement>('#source-files-resizer')!,
  fileList: document.querySelector<HTMLElement>('#source-file-list')!,
  fileCount: document.querySelector<HTMLElement>('#source-file-count')!,
  activePath: document.querySelector<HTMLElement>('#source-active-path')!,
  editorHost: document.querySelector<HTMLElement>('#source-editor')!,
  emptyState: document.querySelector<HTMLElement>('#source-empty-state')!,
  toggleButton: document.querySelector<HTMLButtonElement>('#source-toggle-button')!,
  closeButton: document.querySelector<HTMLButtonElement>('#source-close-button')!,
  workspace,
});


bindResizablePanels({ workspace, navigatorPanel, inspectorPanel, navigatorResizer, inspectorResizer });

const threeScene = new THREE.Scene();
threeScene.background = new THREE.Color('#0b0e12');
const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 1000);
camera.up.set(0, 0, 1);
camera.position.set(2.4, 2.1, 3.0);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;
viewport.append(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 0.01;
controls.maxDistance = 1000;

threeScene.add(new THREE.HemisphereLight('#d9e9ff', '#10141b', 1.7));
const keyLight = new THREE.DirectionalLight('#fff8e9', 3.1);
keyLight.position.set(4, 7, 5);
threeScene.add(keyLight);
threeScene.add(keyLight.target);
const fillLight = new THREE.DirectionalLight('#8db4ff', 1.1);
fillLight.position.set(-5, -6, 7);
threeScene.add(fillLight);
threeScene.add(fillLight.target);

const modelRoot = new THREE.Group();
modelRoot.name = 'scene-package';
threeScene.add(modelRoot);
const loader = new GLTFLoader();
const geometryCache = new Map<string, THREE.Object3D>();
const edgeCache = new Map<string, THREE.Object3D>();
const entityCache = new Map<string, EntitySidecar>();
const nodeObjects = new Map<string, THREE.Group>();
const nodeRows = new Map<string, HTMLButtonElement>();
const manifestByDefinition = new Map<string, Definition>();
const appearanceById = new Map<string, Appearance>();
let currentManifest: SceneManifest | null = null;
let currentFiles: PackageFiles | null = null;
let currentModel: ModelDocument | null = null;
const sourceFiles = new Map<string, string>();
let selectedNodeId: string | null = null;
let selectedFeatureId: string | null = null;
let selectedOverlays: THREE.Object3D[] = [];
const featureRows = new Map<string, HTMLButtonElement[]>();
let selectionMode: SelectionMode = 'component';

function setStatus(message: string, ready = false): void {
  status.textContent = message;
  statusDot.classList.toggle('ready', ready);
}

function bytesFor(files: PackageFiles, uri: string): Uint8Array {
  const value = files[uri];
  if (!value) throw new Error(`package member is missing: ${uri}`);
  return value;
}

function validateMemberName(name: string): void {
  if (!/^[A-Za-z0-9][A-Za-z0-9._/-]{0,1023}$/.test(name) || name.split('/').some((segment) => !segment || segment === '.' || segment === '..')) {
    throw new Error(`invalid scene package member: ${name}`);
  }
}

function packageRecords(manifest: SceneManifest): PackageRecord[] {
  const records: PackageRecord[] = [];
  const addAsset = (asset: Asset, kind: 'geometry' | 'edges'): void => {
    if (asset.asset_id !== asset.content_hash) throw new Error(`${kind} asset ID differs from its content hash`);
    const digest = /^sha256:([0-9a-f]{64})$/.exec(asset.content_hash)?.[1];
    if (!digest || asset.uri !== `${kind}/sha256-${digest}.glb`) throw new Error(`invalid content-addressed ${kind} asset URI`);
    records.push(asset);
  };
  for (const asset of manifest.geometry_assets) addAsset(asset, 'geometry');
  for (const asset of manifest.edge_assets) addAsset(asset, 'edges');
  for (const asset of manifest.entity_assets) {
    if (asset.entity_asset_id !== asset.content_hash) throw new Error('entity asset ID differs from its content hash');
    const digest = /^sha256:([0-9a-f]{64})$/.exec(asset.content_hash)?.[1];
    if (!digest || asset.uri !== `entities/sha256-${digest}.json`) throw new Error('invalid content-addressed entity asset URI');
    records.push(asset);
  }
  for (const source of [manifest.source, manifest.presentation_source]) {
    if (!source?.embedded_artifact_uri) continue;
    if (typeof source.embedded_artifact_byte_length !== 'number' || typeof source.artifact_hash !== 'string') throw new Error('embedded artifact integrity metadata is missing');
    records.push({ uri: source.embedded_artifact_uri, byte_length: source.embedded_artifact_byte_length, content_hash: source.artifact_hash });
    for (const sourceFile of source.source_files ?? []) records.push(sourceFile);
  }
  return records;
}

async function validatePackageMembers(files: PackageFiles, manifest: SceneManifest): Promise<void> {
  const records = packageRecords(manifest);
  const referenced = new Set<string>(['scene.json']);
  for (const record of records) {
    validateMemberName(record.uri);
    if (referenced.has(record.uri)) throw new Error(`duplicate scene package reference: ${record.uri}`);
    referenced.add(record.uri);
  }
  const names = Object.keys(files);
  for (const name of names) {
    validateMemberName(name);
  }
  if (names.length !== referenced.size || names.some((name) => !referenced.has(name))) {
    throw new Error('scene package members do not match scene.json references');
  }
  for (const record of records) {
    const payload = bytesFor(files, record.uri);
    if (!Number.isSafeInteger(record.byte_length) || record.byte_length < 0 || payload.byteLength !== record.byte_length) {
      throw new Error(`package member length differs from scene.json: ${record.uri}`);
    }
    const expected = /^sha256:([0-9a-f]{64})$/.exec(record.content_hash)?.[1];
    if (!expected) throw new Error(`invalid package member hash: ${record.uri}`);
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', payload)), (byte) => byte.toString(16).padStart(2, '0')).join('');
    if (digest !== expected) throw new Error(`package member hash differs from scene.json: ${record.uri}`);
  }
}

async function loadGlb(files: PackageFiles, uri: string): Promise<THREE.Object3D> {
  const bytes = bytesFor(files, uri);
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  const gltf = await loader.parseAsync(buffer, '');
  return gltf.scene;
}

function applyAssetTransform(object: THREE.Object3D, matrix: number[]): void {
  if (matrix.length !== 16) throw new Error('asset_to_scene must contain 16 values');
  // The contract stores row-major CAD-to-scene values. Three.js uses metres.
  object.applyMatrix4(new THREE.Matrix4().set(
    matrix[0] / 1000, matrix[1] / 1000, matrix[2] / 1000, matrix[3] / 1000,
    matrix[4] / 1000, matrix[5] / 1000, matrix[6] / 1000, matrix[7] / 1000,
    matrix[8] / 1000, matrix[9] / 1000, matrix[10] / 1000, matrix[11] / 1000,
    matrix[12], matrix[13], matrix[14], matrix[15],
  ));
}

function placementMatrix(transform: Transform): THREE.Matrix4 {
  const { origin, x_axis, y_axis, z_axis } = transform;
  return new THREE.Matrix4().set(
    x_axis[0], y_axis[0], z_axis[0], origin[0] / 1000,
    x_axis[1], y_axis[1], z_axis[1], origin[1] / 1000,
    x_axis[2], y_axis[2], z_axis[2], origin[2] / 1000,
    0, 0, 0, 1,
  );
}

function materialFor(definition: Definition): THREE.MeshStandardMaterial {
  const appearance = definition.appearance_id ? appearanceById.get(definition.appearance_id) : undefined;
  const color = appearance?.base_color ?? [0.72, 0.75, 0.78, 1];
  return new THREE.MeshStandardMaterial({ color: new THREE.Color(color[0], color[1], color[2]), metalness: appearance?.metallic ?? 0, roughness: appearance?.roughness ?? 0.55, side: appearance?.double_sided ? THREE.DoubleSide : THREE.FrontSide, transparent: appearance?.alpha_mode === 'blend', opacity: color[3] });
}

async function instantiateDefinition(definition: Definition): Promise<THREE.Group> {
  if (!currentManifest || !currentFiles) throw new Error('scene package is not loaded');
  const group = new THREE.Group();
  group.name = definition.name || definition.definition_id;
  const geometryAsset = currentManifest.geometry_assets.find((asset) => asset.asset_id === definition.geometry_asset_id);
  if (geometryAsset) {
    let geometry = geometryCache.get(geometryAsset.asset_id);
    if (!geometry) {
      geometry = await loadGlb(currentFiles, geometryAsset.uri);
      applyAssetTransform(geometry, geometryAsset.asset_to_scene);
      geometryCache.set(geometryAsset.asset_id, geometry);
    }
    const renderGeometry = geometry.clone(true);
    renderGeometry.traverse((child) => {
      if (child instanceof THREE.Mesh) child.material = materialFor(definition);
    });
    group.add(renderGeometry);
  }
  const edgeAsset = currentManifest.edge_assets.find((asset) => asset.asset_id === definition.edge_asset_id);
  if (edgeAsset) {
    let edge = edgeCache.get(edgeAsset.asset_id);
    if (!edge) {
      edge = await loadGlb(currentFiles, edgeAsset.uri);
      applyAssetTransform(edge, edgeAsset.asset_to_scene);
      edge.traverse((child) => { if (child instanceof THREE.LineSegments) child.material = new THREE.LineBasicMaterial({ color: '#6e7e92', transparent: true, opacity: 0.58 }); });
      edgeCache.set(edgeAsset.asset_id, edge);
    }
    const edgeInstance = edge.clone(true);
    edgeInstance.visible = true;
    group.add(edgeInstance);
  }
  const sidecar = sidecarForDefinition(definition);
  if (sidecar) {
    const vertices = sidecar.entities.filter((entity) => entity.kind === 'vertex');
    if (vertices.length) {
      const positions = new Float32Array(vertices.length * 3);
      vertices.forEach((entity, index) => {
        const position = entity.geometry.position as Vec3;
        positions.set([position[0] / 1000, position[1] / 1000, position[2] / 1000], index * 3);
      });
      const vertexGeometry = new THREE.BufferGeometry();
      vertexGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      const vertexPoints = new THREE.Points(
        vertexGeometry,
        new THREE.PointsMaterial({ color: '#d8ff83', size: 7, sizeAttenuation: false, depthWrite: false, transparent: true, opacity: 0.48 }),
      );
      vertexPoints.visible = selectionMode === 'vertex';
      vertexPoints.userData.pickRole = 'vertex';
      vertexPoints.userData.vertexEntityIds = vertices.map((entity) => entity.entity_id);
      group.add(vertexPoints);
    }
  }
  return group;
}

function applySelectionModeVisibility(): void {
  for (const object of nodeObjects.values()) {
    object.traverse((child) => {
      if (child.userData.pickRole === 'vertex') child.visible = selectionMode === 'vertex';
    });
  }
}

function clearModel(): void {
  clearSelectionOverlay();
  const disposedGeometries = new Set<THREE.BufferGeometry>();
  const disposedMaterials = new Set<THREE.Material>();
  const dispose = (root: THREE.Object3D): void => {
    root.traverse((object) => {
      if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments || object instanceof THREE.Points) {
        if (!disposedGeometries.has(object.geometry)) {
          object.geometry.dispose();
          disposedGeometries.add(object.geometry);
        }
        const materials = Array.isArray(object.material) ? object.material : [object.material];
        materials.forEach((material) => {
          if (!disposedMaterials.has(material)) {
            material.dispose();
            disposedMaterials.add(material);
          }
        });
      }
    });
  };
  for (const object of geometryCache.values()) dispose(object);
  for (const object of edgeCache.values()) dispose(object);
  while (modelRoot.children.length) {
    const child = modelRoot.children[0];
    dispose(child);
    modelRoot.remove(child);
  }
  nodeObjects.clear();
  nodeRows.clear();
  geometryCache.clear();
  edgeCache.clear();
  entityCache.clear();
  currentModel = null;
  sourceFiles.clear();
  sourceDock.clear();
  featureRows.clear();
  featureTree.innerHTML = '<div class="tree-empty">Open a model-backed scene to inspect its operations.</div>';
  featureCount.textContent = '0';
  selectedNodeId = null;
  selectedFeatureId = null;
}

function renderTree(manifest: SceneManifest): void {
  tree.replaceChildren();
  nodeRows.clear();
  const byParent = new Map<string | null, SceneNode[]>();
  for (const node of manifest.nodes) byParent.set(node.parent_node_id, [...(byParent.get(node.parent_node_id) ?? []), node]);
  for (const nodes of byParent.values()) nodes.sort((a, b) => a.order - b.order);
  const append = (parent: HTMLElement, parentId: string | null, depth: number): void => {
    for (const node of byParent.get(parentId) ?? []) {
      const row = document.createElement('button');
      row.className = 'tree-row';
      row.style.setProperty('--depth', String(depth));
      row.dataset.nodeId = node.node_id;
      row.classList.toggle('hidden-node', !node.visible);
       const hasChildren = (byParent.get(node.node_id)?.length ?? 0) > 0;
       const isAssembly = node.definition_id.includes('/assembly/');
       row.innerHTML = `<span class="tree-chevron">${iconMarkup(hasChildren ? 'ChevronDown' : 'CircleDot', 'tree-chevron-icon')}</span><span class="tree-glyph">${iconMarkup(isAssembly ? 'Boxes' : 'Box', 'tree-type-icon')}</span><span class="tree-label">${escapeHtml(node.name || node.node_id.split('/').pop() || node.node_id)}</span><span class="tree-visibility" role="button" aria-label="Toggle visibility" title="Toggle visibility">${iconMarkup(node.visible ? 'Eye' : 'EyeOff', 'tree-visibility-icon')}</span>`;
       renderIcons(row);
      row.addEventListener('click', () => {
        if (!canSelectNode(node.node_id)) {
          setStatus('Occurrence is hidden or not selectable', true);
          return;
        }
        selectNode(node.node_id);
        highlightComponent(node.node_id);
      });
      row.querySelector<HTMLElement>('.tree-visibility')!.addEventListener('click', (event) => {
        event.stopPropagation();
        toggleNodeVisibility(node.node_id);
      });
      parent.append(row);
      nodeRows.set(node.node_id, row);
      append(parent, node.node_id, depth + 1);
    }
  };
  append(tree, null, 0);
}

function featureIconName(op: string): keyof typeof lucideIcons {
  if (/^(make_box|make_cylinder|make_sphere|make_cone|make_torus|make_(?:rounded_)?box)/.test(op)) return 'Box';
  if (/^(union|fuse|compound|assemble|combine)/.test(op)) return 'Combine';
  if (/^(cut|subtract|difference)/.test(op)) return 'Scissors';
  if (/^(add|make_|extrude|revolve|loft|sweep|fillet|chamfer|shell|offset|thicken)/.test(op)) return 'Plus';
  if (/^(transform|translate|rotate|scale|mirror)/.test(op)) return 'Rotate3d';
  if (/^(select|query|filter|where|geo_)/.test(op)) return 'GitBranch';
  if (/^(sketch|profile|wire|face)/.test(op)) return 'Layers';
  return 'LayoutDashboard';
}

function featureLabel(feature: ModelNode): string {
  return feature.display?.label || feature.op.replace(/^make_/, '').replace(/_r(.*)$/, ' $1').replaceAll('_', ' ');
}

function featureTreeLabel(feature: ModelNode): string {
  const operation = featureLabel(feature);
  const targets = feature.source?.assignment_targets.filter((target) => target.trim().length > 0) ?? [];
  return targets.length ? `${targets.join(', ')} = ${operation}` : operation;
}

function renderFeatureTree(): void {
  featureRows.clear();
  featureTree.replaceChildren();
  const model = currentModel;
  if (!model || model.graph.nodes.length === 0) {
    featureTree.innerHTML = '<div class="tree-empty">This package has no embedded operation DAG.</div>';
    featureCount.textContent = '0';
    return;
  }

  const byId = new Map(model.graph.nodes.map((feature) => [feature.node_id, feature]));
  const visibleFeatures = model.graph.nodes.filter((feature) => !/^apply_tag(?:_|$)/.test(feature.op));
  const visibleIds = new Set(visibleFeatures.map((feature) => feature.node_id));
  const resolvedInputCache = new Map<string, string[]>();
  const resolveVisibleInput = (featureId: string, path = new Set<string>()): string[] => {
    if (visibleIds.has(featureId)) return [featureId];
    if (path.has(featureId)) return [];
    const cached = resolvedInputCache.get(featureId);
    if (cached) return cached;
    const feature = byId.get(featureId);
    if (!feature || !/^apply_tag(?:_|$)/.test(feature.op)) return [];
    const nextPath = new Set(path).add(featureId);
    const resolved = [...new Set(feature.inputs.flatMap((input) => resolveVisibleInput(input, nextPath)))];
    resolvedInputCache.set(featureId, resolved);
    return resolved;
  };
  const inputsById = new Map<string, string[]>();
  const consumerCount = new Map<string, number>();
  for (const feature of visibleFeatures) {
    const inputs = [...new Set(feature.inputs.flatMap((input) => resolveVisibleInput(input)))];
    inputsById.set(feature.node_id, inputs);
    for (const input of inputs) consumerCount.set(input, (consumerCount.get(input) ?? 0) + 1);
  }
  const rootIds = [...new Set((model.leaf_ids ?? []).flatMap((id) => resolveVisibleInput(id)))];
  if (!rootIds.length) {
    rootIds.push(...visibleFeatures.filter((feature) => !consumerCount.has(feature.node_id)).map((feature) => feature.node_id));
  }

  const expandedPaths = new Set<string>(rootIds.map((_, index) => `root/${index}`));
  const canonicalPathById = new Map<string, string>();
  const rowsByPath = new Map<string, HTMLButtonElement>();
  const addFeatureRow = (parent: HTMLElement, featureId: string, depth: number, path: string, ancestors: Set<string>): void => {
    const feature = byId.get(featureId);
    if (!feature) return;
    const inputs = inputsById.get(featureId) ?? [];
    const canonicalPath = canonicalPathById.get(featureId);
    const reference = canonicalPath !== undefined || ancestors.has(featureId);
    if (!reference) canonicalPathById.set(featureId, path);
    const row = document.createElement('button');
    row.className = `tree-row feature-tree-row${reference ? ' feature-reference-row' : ''}`;
    row.style.setProperty('--depth', String(depth));
    row.dataset.featureId = featureId;
    row.dataset.featurePath = path;
    row.classList.toggle('selected', featureId === selectedFeatureId);
    const expanded = !reference && inputs.length > 0 && expandedPaths.has(path);
    const shared = (consumerCount.get(featureId) ?? 0) > 1;
    const prefixIcon = reference ? 'Link' : inputs.length ? (expanded ? 'ChevronDown' : 'ChevronRight') : 'CircleDot';
    row.setAttribute('aria-expanded', inputs.length && !reference ? String(expanded) : 'false');
    row.setAttribute('aria-label', reference ? `Reference to ${featureTreeLabel(feature)}` : featureTreeLabel(feature));
    row.innerHTML = `<span class="tree-chevron">${iconMarkup(prefixIcon, 'tree-chevron-icon')}</span><span class="tree-glyph feature-glyph">${iconMarkup(featureIconName(feature.op), 'tree-type-icon')}</span><span class="tree-label" title="${escapeHtml(feature.op)}">${escapeHtml(featureTreeLabel(feature))}</span>${reference ? '<span class="feature-reference-mark">REF</span>' : ''}${shared && !reference ? `<span class="feature-shared-mark" title="Used by ${consumerCount.get(featureId)} operations">USED ${consumerCount.get(featureId)}</span>` : ''}${inputs.length && !reference ? `<span class="feature-input-count" title="${inputs.length} visible graph input${inputs.length === 1 ? '' : 's'}">${inputs.length} IN</span>` : ''}${feature.tags?.length ? '<span class="feature-tag-mark">TAG</span>' : ''}`;
    renderIcons(row);
    row.addEventListener('click', () => {
      selectFeature(featureId);
      if (reference) {
        const targetPath = canonicalPathById.get(featureId);
        const target = targetPath ? rowsByPath.get(targetPath) : undefined;
        target?.scrollIntoView({ block: 'center' });
        target?.classList.add('feature-reference-target');
        window.setTimeout(() => target?.classList.remove('feature-reference-target'), 700);
        return;
      }
      if (!inputs.length) return;
      if (expandedPaths.has(path)) expandedPaths.delete(path);
      else expandedPaths.add(path);
      rebuild();
    });
    parent.append(row);
    rowsByPath.set(path, row);
    featureRows.set(featureId, [...(featureRows.get(featureId) ?? []), row]);
    if (!expanded) return;
    const children = document.createElement('div');
    children.className = 'feature-dag-children';
    parent.append(children);
    const nextAncestors = new Set(ancestors).add(featureId);
    inputs.forEach((input, index) => addFeatureRow(children, input, depth + 1, `${path}/${index}`, nextAncestors));
  };
  const rebuild = (): void => {
    featureTree.replaceChildren();
    featureRows.clear();
    canonicalPathById.clear();
    rowsByPath.clear();
    rootIds.forEach((rootId, index) => addFeatureRow(featureTree, rootId, 0, `root/${index}`, new Set()));
  };
  rebuild();
  featureCount.textContent = String(visibleFeatures.length);
}

function escapeHtml(value: string): string { return value.replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character] || character); }

function sourceLocationMarkup(source: OperationSource): string {
  const start = Math.max(1, source.line);
  const end = Math.max(start, source.end_line);
  const location = source.path ? `${source.path}:${start}${end !== start ? `-${end}` : ''}` : 'Source path is unavailable';
  return `<div class="source-file-path">${escapeHtml(location)}</div>${source.path && sourceFiles.has(source.path) ? '<p class="detail-muted">The embedded file is open in the Source dock.</p>' : `<pre class="source-call"><code>${escapeHtml(source.call_text)}</code></pre>`}`;
}

function pythonLiteral(value: unknown): string {
  if (value === null) return 'None';
  if (value === true) return 'True';
  if (value === false) return 'False';
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : 'None';
  return JSON.stringify(String(value));
}

function jsonText(value: unknown): string {
  const rendered = JSON.stringify(value, null, 2);
  return rendered === undefined ? 'null' : rendered;
}

function entityCenter(entity: Entity): Vec3 | null {
  const value = entity.kind === 'vertex' ? entity.properties.position : entity.properties.centroid;
  return Array.isArray(value) && value.length === 3 && value.every((item) => typeof item === 'number') ? value as Vec3 : null;
}

function entityMeasure(entity: Entity): [string, number] | null {
  const path = entity.kind === 'solid' ? 'geom.volume' : entity.kind === 'face' ? 'geom.area' : entity.kind === 'edge' ? 'geom.length' : null;
  const value = entity.kind === 'solid' ? entity.properties.volume : entity.kind === 'face' ? entity.properties.area : entity.kind === 'edge' ? entity.properties.length : null;
  return path && typeof value === 'number' ? [path, value] : null;
}

function selectionSourceForEntity(entity: Entity): SourceRecord {
  const source = entity.source;
  if (!currentModel || typeof source.node_id !== 'string') return source;
  const byId = new Map(currentModel.graph.nodes.map((node) => [node.node_id, node]));
  const visited = new Set<string>();
  const findSolidProducer = (nodeId: string): ModelNode | null => {
    if (visited.has(nodeId)) return null;
    visited.add(nodeId);
    const node = byId.get(nodeId);
    if (!node) return null;
    if (/(?:_rsolid|_rshape|_rcompound)$/.test(node.op)) return node;
    for (const input of node.inputs) {
      const producer = findSolidProducer(input);
      if (producer) return producer;
    }
    return null;
  };
  const producer = findSolidProducer(source.node_id);
  return producer ? { ...source, node_id: producer.node_id, output_slot: 0 } : source;
}

function qlSelectorForEntity(entity: Entity, sidecar: EntitySidecar): { expression: string; unique: boolean } {
  type Fact = { expression: string; matches: (candidate: Entity) => boolean };
  const candidates = sidecar.entities.filter((candidate) => candidate.kind === entity.kind);
  const facts: Fact[] = [];
  for (const tag of entity.evaluated_tags) {
    facts.push({ expression: `Q.tag(${pythonLiteral(tag)})`, matches: (candidate) => candidate.evaluated_tags.includes(tag) });
  }
  const geometryType = entity.geometry.type;
  if (typeof geometryType === 'string' && !geometryType.startsWith('other_') && geometryType !== 'brep_solid' && geometryType !== 'point') {
    const expected = geometryType.toUpperCase().replace(/^BSPLINE_(CURVE|SURFACE)$/, 'BSPLINE');
    facts.push({ expression: `Q.prop("geom.type", "==", ${pythonLiteral(expected)})`, matches: (candidate) => candidate.geometry.type === geometryType });
  }
  const measure = entityMeasure(entity);
  if (measure) {
    facts.push({ expression: `Q.prop(${pythonLiteral(measure[0])}, "==", ${pythonLiteral(measure[1])})`, matches: (candidate) => entityMeasure(candidate)?.[1] === measure[1] });
  }
  const center = entityCenter(entity);
  if (center) {
    (['x', 'y', 'z'] as const).forEach((axis, index) => facts.push({
      expression: `Q.prop("geom.center.${axis}", "==", ${pythonLiteral(center[index])})`,
      matches: (candidate) => entityCenter(candidate)?.[index] === center[index],
    }));
  }
  let matches = candidates;
  const selectedFacts: Fact[] = [];
  for (const fact of facts) {
    const narrowed = matches.filter(fact.matches);
    if (narrowed.length < matches.length) {
      selectedFacts.push(fact);
      matches = narrowed;
    }
    if (matches.length === 1) break;
  }
  const unique = matches.length === 1 && matches[0].entity_id === entity.entity_id;
  const factory = entity.kind === 'solid' ? 'Q.ShapeSelector(target_kind="solid")' : `Q.${entity.kind}s()`;
  const source = selectionSourceForEntity(entity);
  const lines = [factory];
  if (typeof source.node_id === 'string') lines.push(`.from_source(${pythonLiteral(source.node_id)}, ${typeof source.output_slot === 'number' ? source.output_slot : 0})`);
  if (selectedFacts.length === 1) lines.push(`.where(${selectedFacts[0].expression})`);
  if (selectedFacts.length > 1) lines.push(`.where(Q.and_(\n    ${selectedFacts.map((fact) => fact.expression).join(',\n    ')}\n))`);
  lines.push('.exactly(1)');
  return { expression: `(${lines.map((line) => `    ${line}`).join('\n')}\n)`, unique };
}

function metadataSection(title: string, value: Record<string, unknown> | undefined): string {
  if (!value || Object.keys(value).length === 0) return '';
  return `<div class="detail-section"><span class="eyebrow">${escapeHtml(title)}</span><pre class="params">${escapeHtml(jsonText(value))}</pre></div>`;
}

function sourceIdentityRows(source: SourceRecord | undefined): string {
  if (!source) return '<dt>Source</dt><dd>unavailable</dd>';
  const rows: Array<[string, unknown]> = [['Kind', source.kind]];
  if (source.graph_id) rows.push(['Graph', source.graph_id]);
  if (source.node_id) rows.push(['Operation', source.node_id]);
  if (typeof source.output_slot === 'number') rows.push(['Output slot', source.output_slot]);
  if (source.semantic_type) rows.push(['Semantic type', source.semantic_type]);
  if (source.semantic_id) rows.push(['Semantic ID', source.semantic_id]);
  if (source.source_id) rows.push(['Source ID', source.source_id]);
  if (source.root_id) rows.push(['Root ID', source.root_id]);
  if (source.topo_id) rows.push(['Topology ID', source.topo_id]);
  return rows.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd title="${escapeHtml(String(value))}">${escapeHtml(String(value))}</dd>`).join('');
}

function sidecarForDefinition(definition: Definition | undefined): EntitySidecar | null {
  if (!currentManifest || !currentFiles || !definition?.entity_asset_id) return null;
  const asset = currentManifest.entity_assets.find((item) => item.entity_asset_id === definition.entity_asset_id);
  if (!asset) return null;
  const cached = entityCache.get(asset.entity_asset_id);
  if (cached) return cached;
  const parsed = JSON.parse(strFromU8(bytesFor(currentFiles, asset.uri))) as EntitySidecar;
  entityCache.set(asset.entity_asset_id, parsed);
  return parsed;
}

function selectNode(nodeId: string, entityId?: string): void {
  if (!currentManifest) return;
  if (!canSelectNode(nodeId)) {
    setStatus('Occurrence is hidden or not selectable', true);
    return;
  }
  clearSelectionOverlay();
  selectedNodeId = nodeId;
  selectedFeatureId = null;
  for (const [id, row] of nodeRows) row.classList.toggle('selected', id === nodeId);
  for (const rows of featureRows.values()) rows.forEach((row) => row.classList.remove('selected'));
  const node = currentManifest.nodes.find((item) => item.node_id === nodeId);
  if (!node) return;
  const definition = manifestByDefinition.get(node.definition_id);
  selectionKind.textContent = definition?.kind.toUpperCase() ?? 'NODE';
  const sidecar = sidecarForDefinition(definition);
  const entity = sidecar?.entities.find((item) => item.entity_id === entityId);
  const solid = sidecar?.entities.find((item) => item.kind === 'solid');
  selectionKind.textContent = entity?.kind.toUpperCase() ?? definition?.kind.toUpperCase() ?? 'NODE';
  const evaluated = entity ?? solid;
  const inspected = evaluated;
  const measure = inspected ? entityMeasure(inspected) : null;
  const measureLabel = inspected?.kind === 'face' ? 'Area' : inspected?.kind === 'edge' ? 'Length' : inspected?.kind === 'vertex' ? 'Position' : 'Volume';
  const measureUnit = inspected?.kind === 'face' ? 'mm²' : inspected?.kind === 'edge' ? 'mm' : inspected?.kind === 'vertex' ? 'mm' : 'mm³';
  const measureValue = inspected?.kind === 'vertex' ? (inspected.properties.position as Vec3 | undefined)?.map(formatNumber).join(', ') : formatNumber(measure?.[1]);
  const componentPath = Array.isArray(node.source.component_path) && node.source.component_path.length ? node.source.component_path.join(' / ') : 'root';
  const tags = inspected?.evaluated_tags ?? [];
  const selector = inspected && sidecar ? qlSelectorForEntity(inspected, sidecar) : null;
   const iconName: keyof typeof lucideIcons = inspected?.kind === 'face'
     ? 'ScanFace'
     : inspected?.kind === 'edge'
       ? 'Spline'
       : inspected?.kind === 'vertex'
         ? 'CircleDot'
         : definition?.kind === 'assembly'
           ? 'Boxes'
           : 'Box';
  const occurrenceObject = nodeObjects.get(nodeId);
  const effectiveVisible = occurrenceObject ? isEffectivelyVisible(occurrenceObject) : node.visible;
   details.innerHTML = `
     <div class="detail-title"><span class="detail-icon">${iconMarkup(iconName, 'detail-icon-svg')}</span><div><strong>${escapeHtml(entity ? `${node.name || node.node_id} / ${entity.entity_id}` : node.name || node.node_id)}</strong><span class="detail-definition-path">${escapeHtml(node.definition_id)}</span></div></div>
      <div class="detail-section"><span class="eyebrow">OCCURRENCE</span><dl><dt>Node</dt><dd class="path-value" title="${escapeHtml(node.node_id)}">${escapeHtml(node.node_id)}</dd><dt>Component path</dt><dd class="path-value" title="${escapeHtml(componentPath)}">${escapeHtml(componentPath)}</dd><dt>Visibility</dt><dd>${effectiveVisible ? 'Visible' : 'Hidden'}</dd><dt>Selectable</dt><dd>${canSelectNode(nodeId) ? 'Yes' : 'No'}</dd><dt>Order</dt><dd>${node.order}</dd></dl></div>
    ${evaluated ? `<div class="detail-section"><span class="eyebrow">${entity ? 'EVALUATED ENTITY' : 'EVALUATED BODY'}</span><dl><dt>Entity</dt><dd title="${escapeHtml(evaluated.entity_id)}">${escapeHtml(evaluated.entity_id)}</dd><dt>Topology</dt><dd>${escapeHtml(evaluated.kind)}</dd><dt>Geometry</dt><dd>${escapeHtml(String(evaluated.geometry.type ?? 'unknown'))}</dd><dt>${measureLabel}</dt><dd>${escapeHtml(measureValue || 'n/a')} ${measureUnit}</dd><dt>Quality</dt><dd>${escapeHtml(String(evaluated.properties.quality ?? 'evaluated'))}</dd><dt>Render</dt><dd>${escapeHtml(evaluated.render_status)}</dd><dt>Parents</dt><dd>${evaluated.parent_entity_ids.length}</dd><dt>Children</dt><dd>${evaluated.child_entity_ids.length}</dd></dl></div>` : ''}
     <div class="detail-section"><span class="eyebrow">NAMING & SOURCE</span><dl><dt>Definition</dt><dd title="${escapeHtml(node.definition_id)}">${escapeHtml(node.definition_id)}</dd>${sourceIdentityRows(definition?.source)}${inspected ? sourceIdentityRows(inspected.source) : ''}</dl></div>
    ${inspected ? `<div class="detail-section"><span class="eyebrow">TAGS</span>${tags.length ? `<div class="tag-list">${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join('')}</div>` : '<p class="detail-muted">No evaluated tags.</p>'}</div>` : ''}
     ${selector ? `<div class="detail-section"><div class="detail-section-heading"><span class="eyebrow">UNIQUE QL SELECTOR</span>${selector.unique ? `<button id="copy-ql" class="copy-button">${iconMarkup('Copy', 'button-icon')}<span>COPY</span></button>` : ''}</div>${selector.unique ? `<pre class="selector-code">${escapeHtml(selector.expression)}</pre>` : '<p class="selector-warning">The exported tags and geometric facts do not uniquely identify this entity. No selector was fabricated.</p>'}</div>` : ''}
    ${inspected ? metadataSection('ENTITY METADATA', inspected.sdk_metadata) : ''}
    ${metadataSection('DEFINITION METADATA', definition?.sdk_metadata)}
    ${metadataSection('OCCURRENCE METADATA', node.sdk_metadata)}
     <div class="detail-section"><span class="eyebrow">DEFINITION</span><dl><dt>Type</dt><dd>${escapeHtml(definition?.kind ?? 'unknown')}</dd><dt>Geometry</dt><dd>${definition?.geometry_asset_id ? 'GLB / cached' : 'none'}</dd><dt>Entity sidecar</dt><dd>${definition?.entity_asset_id ? 'available' : 'none'}</dd></dl></div>`;
   renderIcons(details);
  const copyButton = details.querySelector<HTMLButtonElement>('#copy-ql');
  copyButton?.addEventListener('click', async () => {
    if (!selector?.unique) return;
    try {
      await navigator.clipboard.writeText(selector.expression);
       copyButton.innerHTML = `${iconMarkup('CopyCheck', 'button-icon')}<span>COPIED</span>`;
       renderIcons(copyButton);
       window.setTimeout(() => {
         copyButton.innerHTML = `${iconMarkup('Copy', 'button-icon')}<span>COPY</span>`;
         renderIcons(copyButton);
       }, 1200);
    } catch {
      setStatus('Clipboard access was denied', currentManifest !== null);
    }
  });
  if (entityId) highlightEntity(nodeId, entityId);
}

function selectFeature(featureId: string): void {
  if (!currentModel) return;
  clearSelectionOverlay();
  selectedFeatureId = featureId;
  selectedNodeId = null;
  for (const row of nodeRows.values()) row.classList.remove('selected');
   for (const [id, rows] of featureRows) rows.forEach((row) => row.classList.toggle('selected', id === featureId));
  const feature = currentModel.graph.nodes.find((item) => item.node_id === featureId);
  if (!feature) return;
  selectionKind.textContent = 'FEATURE';
  const inputs = feature.inputs.length ? feature.inputs.join(', ') : 'none';
   const assignment = feature.source?.assignment_targets.length ? feature.source.assignment_targets.join(', ') : 'unassigned';
   details.innerHTML = `<div class="detail-title"><span class="detail-icon">${iconMarkup(featureIconName(feature.op), 'detail-icon-svg')}</span><div><strong>${escapeHtml(featureLabel(feature))}</strong><span class="detail-definition-path">${escapeHtml(feature.node_id)}</span></div></div><div class="detail-section"><span class="eyebrow">OPERATION</span><dl><dt>Function</dt><dd>${escapeHtml(feature.op)}</dd><dt>Category</dt><dd>${escapeHtml(feature.display?.category || 'operation')}</dd><dt>Assigned to</dt><dd>${escapeHtml(assignment)}</dd><dt>Inputs</dt><dd title="${escapeHtml(inputs)}">${escapeHtml(inputs)}</dd><dt>Output count</dt><dd>${feature.output_count ?? 1}</dd></dl></div>${feature.source ? `<div class="detail-section source-section"><span class="eyebrow">SOURCE</span>${sourceLocationMarkup(feature.source)}</div>` : ''}<div class="detail-section"><span class="eyebrow">PARAMETERS</span><pre class="params">${escapeHtml(jsonText(feature.params))}</pre></div>${feature.display?.summary ? `<div class="detail-section"><span class="eyebrow">SUMMARY</span><p class="detail-summary">${escapeHtml(feature.display.summary)}</p></div>` : ''}${feature.tags?.length ? `<div class="detail-section"><span class="eyebrow">TAGS</span><div class="tag-list">${feature.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join('')}</div></div>` : ''}`;
   renderIcons(details);
   if (feature.source) sourceDock.reveal(feature.source);
}

function clearFeatureSelection(): void {
  if (selectedFeatureId === null) return;
  selectedFeatureId = null;
  selectionKind.textContent = 'SCENE';
  for (const rows of featureRows.values()) rows.forEach((row) => row.classList.remove('selected'));
   details.innerHTML = `<div class="empty-state"><span class="empty-cross">${iconMarkup('LayoutDashboard', 'empty-state-icon')}</span><strong>Feature selection cleared</strong><span>Select a Blueprint node to inspect its operation and dependencies.</span></div>`;
   renderIcons(details);
}

function clearSelectionOverlay(): void {
  for (const overlay of selectedOverlays) {
    overlay.parent?.remove(overlay);
    overlay.traverse((object) => {
      if (!(object instanceof THREE.Mesh || object instanceof THREE.LineSegments || object instanceof THREE.Points || object instanceof LineSegments2)) return;
      object.geometry.dispose();
      const material = object.material;
      (Array.isArray(material) ? material : [material]).forEach((item) => item.dispose());
    });
  }
  selectedOverlays = [];
}

function isEffectivelyVisible(object: THREE.Object3D): boolean {
  for (let current: THREE.Object3D | null = object; current; current = current.parent) {
    if (!current.visible) return false;
    if (current === modelRoot) break;
  }
  return true;
}

function canSelectNode(nodeId: string): boolean {
  if (!currentManifest) return false;
  const byId = new Map(currentManifest.nodes.map((node) => [node.node_id, node]));
  for (let currentId: string | null = nodeId; currentId; ) {
    const manifestNode = byId.get(currentId);
    if (!manifestNode || !manifestNode.visible || !manifestNode.selectable) return false;
    currentId = manifestNode.parent_node_id;
  }
  const object = nodeObjects.get(nodeId);
  if (object && !isEffectivelyVisible(object)) return false;
  if (object) {
    for (let current: THREE.Object3D | null = object; current; current = current.parent) {
      const ancestorNodeId = current.userData.nodeId;
      if (typeof ancestorNodeId === 'string' && currentManifest.nodes.find((item) => item.node_id === ancestorNodeId)?.selectable === false) return false;
      if (current === modelRoot) break;
    }
  }
  return true;
}

function attachSelectionOverlay(source: THREE.Object3D, overlay: THREE.Object3D): void {
  overlay.name = 'selection-overlay';
  overlay.userData.pickable = false;
  overlay.renderOrder = 10;
  overlay.matrix.copy(source.matrix);
  overlay.matrixAutoUpdate = false;
  overlay.visible = source.visible;
  source.parent?.add(overlay);
  selectedOverlays.push(overlay);
}

function highlightEntity(nodeId: string, entityId?: string): void {
  clearSelectionOverlay();
  const node = nodeObjects.get(nodeId);
  if (!node) return;
  const definition = manifestByDefinition.get(String(node.userData.definitionId));
  const sidecar = sidecarForDefinition(definition);
  const entityGroup = entityId ? sidecar?.face_groups.find((group) => group.entity_id === entityId) : undefined;
  const edgeGroup = entityId ? sidecar?.edge_groups?.find((group) => group.entity_id === entityId) : undefined;
  node.traverse((child) => {
    if (selectedOverlays.length || !isEffectivelyVisible(child) || !(child instanceof THREE.Mesh || child instanceof THREE.LineSegments || child instanceof THREE.Points)) return;
    const source = child as THREE.Mesh | THREE.LineSegments | THREE.Points;
    const range = entityGroup || edgeGroup;
    const isVertex = entityId?.startsWith('entity/vertex/') && source instanceof THREE.Points;
    if (!range && !isVertex && entityId !== 'entity/solid/0') return;
    if (entityGroup && !(source instanceof THREE.Mesh)) return;
    if (edgeGroup && !entityGroup && !(source instanceof THREE.LineSegments)) return;
    if (isVertex && !source.userData.vertexEntityIds?.includes(entityId)) return;
    const material = source instanceof THREE.LineSegments
      ? new LineMaterial({ color: '#fff04d', linewidth: 5, worldUnits: false, depthTest: false, transparent: true, opacity: 1 })
      : source instanceof THREE.Points
        ? new THREE.PointsMaterial({ color: '#fff04d', size: 16, sizeAttenuation: false, depthTest: false, transparent: true, opacity: 1 })
      : new THREE.MeshBasicMaterial({ color: '#fff04d', transparent: true, opacity: 0.78, depthTest: false, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 });
    let overlay: THREE.Object3D;
    if (source instanceof THREE.LineSegments && range) {
      const lineGeometry = new LineSegmentsGeometry();
      const positions: number[] = [];
      const index = source.geometry.index;
      const position = source.geometry.getAttribute('position');
      for (let offset = range.first_index; offset < range.first_index + range.index_count; offset += 2) {
        const a = index ? index.getX(offset) : offset;
        const b = index ? index.getX(offset + 1) : offset + 1;
        positions.push(position.getX(a), position.getY(a), position.getZ(a), position.getX(b), position.getY(b), position.getZ(b));
      }
      lineGeometry.setPositions(positions);
      const lineMaterial = material as LineMaterial;
      lineMaterial.resolution.set(renderer.domElement.clientWidth, renderer.domElement.clientHeight);
      overlay = new LineSegments2(lineGeometry, lineMaterial);
    } else if (source instanceof THREE.Points) {
      const geometry = source.geometry.clone();
      const vertexIndex = source.userData.vertexEntityIds.indexOf(entityId);
      geometry.setDrawRange(vertexIndex, 1);
      overlay = new THREE.Points(geometry, material as THREE.PointsMaterial);
    } else {
      const geometry = source.geometry.clone();
      if (range) geometry.setDrawRange(range.first_index, range.index_count);
      overlay = new THREE.Mesh(geometry, material as THREE.MeshBasicMaterial);
    }
    attachSelectionOverlay(source, overlay);
  });
}

function highlightComponent(nodeId: string): void {
  clearSelectionOverlay();
  const node = nodeObjects.get(nodeId);
  if (!node) return;
  const meshes: THREE.Mesh[] = [];
  node.traverse((child) => {
    if (child instanceof THREE.Mesh && isEffectivelyVisible(child)) meshes.push(child);
  });
  for (const child of meshes) {
    const geometry = child.geometry.clone();
    const material = new THREE.MeshBasicMaterial({ color: '#fff04d', transparent: true, opacity: 0.44, depthTest: false, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 });
    const overlay = new THREE.Mesh(geometry, material);
    attachSelectionOverlay(child, overlay);
  }
}

function toggleNodeVisibility(nodeId: string): void {
  const object = nodeObjects.get(nodeId);
  const row = nodeRows.get(nodeId);
  if (!object || !row) return;
  object.visible = !object.visible;
  const manifestNode = currentManifest?.nodes.find((node) => node.node_id === nodeId);
  if (manifestNode) manifestNode.visible = object.visible;
   row.classList.toggle('hidden-node', !object.visible);
   const visibility = row.querySelector<HTMLElement>('.tree-visibility');
   if (visibility) {
     visibility.innerHTML = iconMarkup(object.visible ? 'Eye' : 'EyeOff', 'tree-visibility-icon');
     visibility.setAttribute('aria-label', object.visible ? 'Hide occurrence' : 'Show occurrence');
     visibility.setAttribute('title', object.visible ? 'Hide occurrence' : 'Show occurrence');
     renderIcons(visibility);
   }
  if (selectedNodeId && !canSelectNode(selectedNodeId)) {
    clearSelectionOverlay();
    selectedNodeId = null;
    selectedFeatureId = null;
    for (const selectedRow of nodeRows.values()) selectedRow.classList.remove('selected');
    for (const rows of featureRows.values()) rows.forEach((row) => row.classList.remove('selected'));
    selectionKind.textContent = 'SCENE';
     details.innerHTML = `<div class="empty-state"><span class="empty-cross">${iconMarkup('EyeOff', 'empty-state-icon')}</span><strong>Selection hidden</strong><span>The selected occurrence is hidden or no longer selectable.</span></div>`;
     renderIcons(details);
  } else if (!isEffectivelyVisible(object)) {
    clearSelectionOverlay();
  }
}

function formatNumber(value: unknown): string { return typeof value === 'number' ? new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value) : 'n/a'; }

function frameModel(): void {
  const box = new THREE.Box3().setFromObject(modelRoot);
  if (box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const radius = Math.max(size.length() * 0.5, 0.01);
  const direction = new THREE.Vector3(1, 0.78, 1).normalize();
  camera.position.copy(center).add(direction.multiplyScalar(radius * 2.4));
  camera.near = Math.max(radius / 100, 0.001);
  camera.far = Math.max(radius * 100, 10);
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.maxDistance = radius * 12;
  controls.update();
}

async function loadPackage(files: PackageFiles): Promise<void> {
  const manifest = JSON.parse(strFromU8(bytesFor(files, 'scene.json'))) as SceneManifest;
  if (manifest.schema_version !== '1.0') throw new Error(`unsupported scene schema: ${manifest.schema_version}`);
  await validatePackageMembers(files, manifest);
  currentManifest = manifest;
  currentFiles = files;
  manifestByDefinition.clear();
  appearanceById.clear();
  for (const definition of manifest.definitions) manifestByDefinition.set(definition.definition_id, definition);
  for (const appearance of manifest.appearances) appearanceById.set(appearance.appearance_id, appearance);
  clearModel();
  if (manifest.source.embedded_artifact_uri === 'model/model.json') {
    currentModel = JSON.parse(strFromU8(bytesFor(files, 'model/model.json'))) as ModelDocument;
    for (const sourceFile of manifest.source.source_files ?? []) {
      sourceFiles.set(sourceFile.path, strFromU8(bytesFor(files, sourceFile.uri)));
    }
    sourceDock.setFiles(sourceFiles);
  }
  renderTree(manifest);
  renderFeatureTree();
  sceneTitle.textContent = manifest.scene_id.replaceAll('-', ' ');
  nodeCount.textContent = String(manifest.nodes.length);
  packageMeta.textContent = `${manifest.generator.profile} · ${manifest.generator.simplecadapi_version} · ${manifest.coordinate_system.length_unit}`;
  const nodesByParent = new Map<string | null, SceneNode[]>();
  for (const node of manifest.nodes) nodesByParent.set(node.parent_node_id, [...(nodesByParent.get(node.parent_node_id) ?? []), node]);
  const build = async (parent: THREE.Object3D, parentId: string | null): Promise<void> => {
    for (const node of (nodesByParent.get(parentId) ?? []).sort((a, b) => a.order - b.order)) {
      const definition = manifestByDefinition.get(node.definition_id);
      if (!definition) continue;
      const object = new THREE.Group();
      object.name = node.node_id;
      object.matrixAutoUpdate = false;
      object.matrix.copy(placementMatrix(node.transform));
      object.visible = node.visible;
      object.userData.nodeId = node.node_id;
      object.userData.definitionId = node.definition_id;
      nodeObjects.set(node.node_id, object);
      parent.add(object);
      if (definition.kind !== 'assembly') {
        const instance = await instantiateDefinition(definition);
        instance.traverse((child) => { child.userData.nodeId = node.node_id; child.userData.definitionId = node.definition_id; });
        object.add(instance);
      }
      await build(object, node.node_id);
    }
  };
  await build(modelRoot, null);
  frameModel();
  loading.classList.add('hidden');
  setStatus(`${manifest.nodes.length} occurrences · ${manifest.geometry_assets.length} geometry asset${manifest.geometry_assets.length === 1 ? '' : 's'} · ${currentModel?.graph.nodes.length ?? 0} features`, true);
}

function unzipPackage(raw: Uint8Array): PackageFiles {
  if (raw.byteLength > MAX_PACKAGE_BYTES) throw new Error('scene package exceeds browser size limit');
  let memberCount = 0;
  let unpackedBytes = 0;
  const seenNames = new Set<string>();
  unzipSync(raw, { filter: (entry) => {
    validateMemberName(entry.name);
    const foldedName = entry.name.toLowerCase();
    if (seenNames.has(foldedName)) throw new Error(`duplicate or case-colliding scene package member: ${entry.name}`);
    seenNames.add(foldedName);
    memberCount += 1;
    unpackedBytes += entry.originalSize;
    if (entry.compression !== 0 && entry.compression !== 8) throw new Error(`unsupported ZIP compression method: ${entry.name}`);
    if (memberCount > MAX_PACKAGE_MEMBERS) throw new Error('scene package member count is invalid');
    if (entry.originalSize > MAX_MEMBER_BYTES) throw new Error(`scene package member exceeds browser size limit: ${entry.name}`);
    if (entry.name === 'scene.json' && entry.originalSize > MAX_SCENE_JSON_BYTES) throw new Error('scene.json is missing or too large');
    if (unpackedBytes > MAX_UNPACKED_BYTES) throw new Error('scene package expands beyond browser size limit');
    if (entry.originalSize > MAX_COMPRESSION_RATIO * Math.max(1, entry.size)) throw new Error(`scene package member compression ratio is too high: ${entry.name}`);
    return false;
  }});
  if (memberCount === 0 || !seenNames.has('scene.json')) throw new Error('scene.json is missing or too large');
  if (unpackedBytes > MAX_COMPRESSION_RATIO * raw.byteLength) throw new Error('scene package compression ratio is too high');
  const files = unzipSync(raw) as PackageFiles;
  const entries = Object.entries(files);
  if (entries.length !== memberCount) throw new Error('scene package member count changed during extraction');
  const total = entries.reduce((sum, [, value]) => sum + value.byteLength, 0);
  if (total !== unpackedBytes) throw new Error('scene package decoded size differs from ZIP metadata');
  const scene = files['scene.json'];
  if (!scene || scene.byteLength > MAX_SCENE_JSON_BYTES) throw new Error('scene.json is missing or too large');
  return files;
}

document.querySelector<HTMLButtonElement>('#fit-button')!.addEventListener('click', frameModel);
const selectionModeButtons = Array.from(document.querySelectorAll<HTMLButtonElement>('.selection-mode'));
for (const button of selectionModeButtons) {
  button.addEventListener('click', () => {
    selectionMode = button.dataset.selectionMode as SelectionMode;
    selectionModeButtons.forEach((item) => item.classList.toggle('active', item === button));
    clearSelectionOverlay();
    applySelectionModeVisibility();
    setStatus(`Selection intent: ${selectionMode.toUpperCase()}`, currentManifest !== null);
  });
}
const fileInput = document.querySelector<HTMLInputElement>('#file-input')!;
document.querySelector<HTMLButtonElement>('#open-button')!.addEventListener('click', () => fileInput.click());
const setNavigatorTab = (tab: 'components' | 'features'): void => {
  const features = tab === 'features';
  componentsTab.classList.toggle('active', !features);
  featuresTab.classList.toggle('active', features);
  componentsTab.setAttribute('aria-selected', String(!features));
  featuresTab.setAttribute('aria-selected', String(features));
  componentsView.hidden = features;
  featuresView.hidden = !features;
};
componentsTab.addEventListener('click', () => setNavigatorTab('components'));
featuresTab.addEventListener('click', () => setNavigatorTab('features'));
fileInput.addEventListener('change', async () => {
  const file = fileInput.files?.[0];
  if (!file) return;
  try {
    if (file.size > MAX_PACKAGE_BYTES) throw new Error('scene package exceeds browser size limit');
    await loadPackage(unzipPackage(new Uint8Array(await file.arrayBuffer())));
  } catch (error) { setStatus(error instanceof Error ? error.message : 'Unable to open package'); loading.classList.add('hidden'); }
});

viewport.addEventListener('dragover', (event) => {
  event.preventDefault();
  viewport.classList.add('drop-target');
});
viewport.addEventListener('dragleave', () => viewport.classList.remove('drop-target'));
viewport.addEventListener('drop', async (event) => {
  event.preventDefault();
  viewport.classList.remove('drop-target');
  const file = event.dataTransfer?.files[0];
  if (!file) return;
  try {
    if (file.size > MAX_PACKAGE_BYTES) throw new Error('scene package exceeds browser size limit');
    loading.classList.remove('hidden');
    setStatus('Opening scene package');
    await loadPackage(unzipPackage(new Uint8Array(await file.arrayBuffer())));
  } catch (error) {
    setStatus(error instanceof Error ? error.message : 'Unable to open package');
    loading.classList.add('hidden');
  }
});

function resize(): void {
  const width = viewport.clientWidth;
  const height = viewport.clientHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / Math.max(height, 1);
  camera.updateProjectionMatrix();
  for (const overlay of selectedOverlays) {
    overlay.traverse((object) => {
      if (object instanceof LineSegments2) object.material.resolution.set(width, height);
    });
  }
}
new ResizeObserver(resize).observe(viewport);
resize();
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let selectionPointerActive = false;

function pointerRay(event: PointerEvent): void {
  const bounds = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
  pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const distance = camera.position.distanceTo(controls.target);
  const worldPerPixel = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov * 0.5)) * distance / Math.max(bounds.height, 1);
  raycaster.params.Line.threshold = worldPerPixel * 5;
  raycaster.params.Points.threshold = worldPerPixel * 8;
}

function validSelectionHit(event: PointerEvent): THREE.Intersection | null {
  pointerRay(event);
  const hits = raycaster.intersectObjects(modelRoot.children, true).filter((hit) => {
    if (hit.object.userData.pickable === false || !isEffectivelyVisible(hit.object)) return false;
    const nodeId = hit.object.userData.nodeId;
    return typeof nodeId === 'string' && canSelectNode(nodeId);
  });
  const meshHit = hits.find((hit) => hit.object instanceof THREE.Mesh);
  if (selectionMode === 'component' || selectionMode === 'solid' || selectionMode === 'face') {
    return meshHit ?? null;
  }
  const candidate = hits.find((hit) => selectionMode === 'edge' ? hit.object instanceof THREE.LineSegments : hit.object instanceof THREE.Points);
  if (!candidate) return null;
  if (!meshHit) return candidate;
  const occlusionAllowance = selectionMode === 'edge' ? raycaster.params.Line.threshold : raycaster.params.Points.threshold;
  return candidate.distance <= meshHit.distance + occlusionAllowance * 1.5 ? candidate : null;
}

function commitSelection(event: PointerEvent): void {
  const hit = validSelectionHit(event);
  if (!hit) {
    setStatus(`No ${selectionMode} at pointer`, currentManifest !== null);
    return;
  }
  const nodeId = hit?.object.userData.nodeId;
  const definitionId = hit?.object.userData.definitionId;
  if (typeof nodeId !== 'string' || typeof definitionId !== 'string') return;
  const definition = manifestByDefinition.get(definitionId);
  const sidecar = sidecarForDefinition(definition);
  if (selectionMode === 'component') {
    selectNode(nodeId);
    highlightComponent(nodeId);
    return;
  }
  if (selectionMode === 'solid') {
    selectNode(nodeId, 'entity/solid/0');
    return;
  }
  let entityId: string | undefined;
  if (selectionMode === 'face' && hit.object instanceof THREE.Mesh && typeof hit.faceIndex === 'number') {
    const triangleOffset = hit.faceIndex * 3;
    entityId = sidecar?.face_groups.find((group) => triangleOffset >= group.first_index && triangleOffset < group.first_index + group.index_count)?.entity_id;
  } else if (selectionMode === 'edge' && hit.object instanceof THREE.LineSegments && typeof hit.index === 'number') {
    entityId = sidecar?.edge_groups?.find((group) => hit.index! >= group.first_index && hit.index! < group.first_index + group.index_count)?.entity_id;
  } else if (selectionMode === 'vertex' && hit.object instanceof THREE.Points && typeof hit.index === 'number') {
    entityId = hit.object.userData.vertexEntityIds?.[hit.index];
  }
  if (entityId) {
    selectNode(nodeId, entityId);
  } else {
    setStatus(`No ${selectionMode} at pointer`, true);
  }
}

bindClickSelection({
  element: renderer.domElement,
  camera,
  controls,
  onPointerStateChange: (active) => { selectionPointerActive = active; },
  onClick: commitSelection,
});
renderer.domElement.addEventListener('pointermove', (event) => {
  if (selectionPointerActive) return;
  renderer.domElement.style.cursor = validSelectionHit(event) ? 'crosshair' : 'default';
});
renderer.domElement.addEventListener('pointerleave', () => {
  renderer.domElement.style.cursor = 'default';
});
renderer.setAnimationLoop(() => { controls.update(); renderer.render(threeScene, camera); });

loading.classList.add('hidden');
details.innerHTML = `<div class="empty-state"><span class="empty-cross">${iconMarkup('PackageOpen', 'empty-state-icon')}</span><strong>Choose a scene package</strong><span>Open a .scene.zip file or drop one into the viewport.</span></div>`;
renderIcons(details);
