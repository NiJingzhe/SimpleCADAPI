// Interactive BRep scene viewport used by the reverse-engineering mode.
// Adapts the package viewer's scene assembly + raycast picking + entity
// highlight into a reusable class so the original side and the rebuilt side
// share one code path.

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { strFromU8 } from 'fflate';
import { bindClickSelection } from './components/click-selection';
import { addWideEdgeVisual, cadPointToGltf, disposeObject, materialFor, placementMatrix, type Resolution } from './cad-three';
import type { PackageFiles } from './product-package';
import type { Entity, EntitySidecar, FaceGroup, SceneManifest, SceneNode, Vec3 } from './scene2';

export type SelectionMode = 'component' | 'solid' | 'face' | 'edge' | 'vertex';
export type PickResult = { nodeId: string; entityId: string | null; mode: SelectionMode; entity: Entity | null };
export type CameraState = {
  position: Vec3;
  target: Vec3;
  up: Vec3;
  fov_deg: number;
  width: number;
  height: number;
};

export const MARK_COLORS = ['#ff5c5c', '#ffd23f', '#4ade80', '#60a5fa', '#c084fc', '#fb923c', '#f472b6', '#34d399'];

export type SceneViewOptions = {
  onPick?: (result: PickResult) => void;
  selectionMode?: SelectionMode;
  background?: string;
  interactive?: boolean;
};

type Mark = { key: string; color: string; overlays: THREE.Object3D[] };

export class SceneView {
  readonly host: HTMLElement;
  readonly threeScene: THREE.Scene;
  readonly camera: THREE.PerspectiveCamera;
  readonly renderer: THREE.WebGLRenderer;
  readonly controls: OrbitControls;
  readonly modelRoot = new THREE.Group();
  onPick: ((result: PickResult) => void) | null;

  private loader = new GLTFLoader();
  private raycaster = new THREE.Raycaster();
  private pointer = new THREE.Vector2();
  private geometryCache = new Map<string, THREE.Object3D>();
  private edgeCache = new Map<string, THREE.Object3D>();
  private entityCache = new Map<string, EntitySidecar>();
  private nodeObjects = new Map<string, THREE.Group>();
  nodeVisibility = new Map<string, boolean>();
  manifest: SceneManifest | null = null;
  files: PackageFiles | null = null;
  selectionMode: SelectionMode;
  marks: Mark[] = [];
  private observer: ResizeObserver;
  private unbindClick: (() => void) | null = null;
  private pendingFrame = true;
  private disposed = false;

  constructor(host: HTMLElement, options: SceneViewOptions = {}) {
    this.host = host;
    this.onPick = options.onPick ?? null;
    this.selectionMode = options.selectionMode ?? 'face';
    this.threeScene = new THREE.Scene();
    this.threeScene.background = new THREE.Color(options.background ?? '#0b0e12');
    this.camera = new THREE.PerspectiveCamera(42, 1, 0.01, 1000);
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(2.4, 2.1, 3.0);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.1;
    host.append(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.minDistance = 0.01;
    this.controls.maxDistance = 1000;
    this.modelRoot.name = 'scene-root';
    this.threeScene.add(this.modelRoot);
    this.threeScene.add(new THREE.HemisphereLight('#d9e9ff', '#10141b', 1.7));
    const keyLight = new THREE.DirectionalLight('#fff8e9', 3.1);
    keyLight.position.set(4, 7, 5);
    this.threeScene.add(keyLight, keyLight.target);
    const fillLight = new THREE.DirectionalLight('#8db4ff', 1.1);
    fillLight.position.set(-5, -6, 7);
    this.threeScene.add(fillLight, fillLight.target);
    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(host);
    this.resize();
    this.renderer.setAnimationLoop(() => {
      this.controls.update();
      this.renderer.render(this.threeScene, this.camera);
    });
    if (options.interactive !== false) {
      this.unbindClick = bindClickSelection({
        element: this.renderer.domElement,
        camera: this.camera,
        controls: this.controls,
        onClick: (event) => {
          const result = this.pick(event);
          if (result) this.onPick?.(result);
        },
      });
    }
  }

  // -- scene loading -------------------------------------------------------

  private bytesFor(uri: string): Uint8Array {
    const value = this.files?.[uri];
    if (!value) throw new Error(`scene file is missing: ${uri}`);
    return value;
  }

  private async loadGlb(uri: string): Promise<THREE.Object3D> {
    const bytes = this.bytesFor(uri);
    const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    const gltf = await this.loader.parseAsync(buffer, '');
    return gltf.scene;
  }

  private resolution(): Resolution {
    return { width: this.renderer.domElement.clientWidth, height: this.renderer.domElement.clientHeight };
  }

  sidecarFor(node: SceneNode | undefined): EntitySidecar | null {
    if (!this.manifest || !this.files || !node?.entity_asset_id) return null;
    const asset = this.manifest.entity_assets.find((item) => item.asset_id === node.entity_asset_id);
    if (!asset) return null;
    const cached = this.entityCache.get(asset.asset_id);
    if (cached) return cached;
    const parsed = JSON.parse(strFromU8(this.bytesFor(asset.uri))) as EntitySidecar;
    if (parsed.schema_version !== '2.0') throw new Error(`entity sidecar schema differs: ${asset.uri}`);
    this.entityCache.set(asset.asset_id, parsed);
    return parsed;
  }

  async loadScene(files: PackageFiles): Promise<void> {
    const sceneBytes = files['scene.json'];
    if (!sceneBytes) throw new Error('scene.json is missing from the scene files');
    const manifest = JSON.parse(strFromU8(sceneBytes)) as SceneManifest;
    if (manifest.schema_version !== '2.0') throw new Error(`unsupported scene schema: ${manifest.schema_version}`);
    this.clearScene();
    this.files = files;
    this.manifest = manifest;
    const nodesByParent = new Map<string | null, SceneNode[]>();
    for (const node of manifest.nodes) nodesByParent.set(node.parent_node_id, [...(nodesByParent.get(node.parent_node_id) ?? []), node]);
    const build = async (parent: THREE.Object3D, parentId: string | null): Promise<void> => {
      for (const node of nodesByParent.get(parentId) ?? []) {
        const object = new THREE.Group();
        object.name = node.node_id;
        object.matrixAutoUpdate = false;
        object.matrix.copy(placementMatrix(node.transform));
        object.visible = this.nodeVisibility.get(node.node_id) ?? true;
        object.userData.nodeId = node.node_id;
        object.userData.definitionId = node.definition_id;
        this.nodeObjects.set(node.node_id, object);
        parent.add(object);
        if (node.node_kind === 'part' || node.node_kind === 'solid') {
          const instance = await this.instantiateNode(node);
          instance.traverse((child: THREE.Object3D) => { child.userData.nodeId = node.node_id; child.userData.definitionId = node.definition_id; });
          object.add(instance);
        }
        await build(object, node.node_id);
      }
    };
    await build(this.modelRoot, null);
    this.applySelectionModeVisibility();
    this.pendingFrame = true;
    this.resize();
  }

  private async instantiateNode(node: SceneNode): Promise<THREE.Group> {
    if (!this.manifest) throw new Error('scene is not loaded');
    const group = new THREE.Group();
    group.name = node.display_name || node.node_id;
    const geometryAsset = node.geometry_asset_id ? this.manifest.geometry_assets.find((asset) => asset.asset_id === node.geometry_asset_id) : undefined;
    if (geometryAsset) {
      let geometry = this.geometryCache.get(geometryAsset.asset_id);
      if (!geometry) {
        geometry = await this.loadGlb(geometryAsset.uri);
        this.geometryCache.set(geometryAsset.asset_id, geometry);
      }
      const renderGeometry = geometry.clone(true);
      renderGeometry.traverse((child) => {
        if (child instanceof THREE.Mesh) child.material = materialFor(node);
      });
      group.add(renderGeometry);
    }
    const sidecar = this.sidecarFor(node);
    const edgeAsset = sidecar ? this.manifest.geometry_assets.find((asset) => asset.asset_id === sidecar.edge_asset_id) : undefined;
    if (edgeAsset) {
      let edge = this.edgeCache.get(edgeAsset.asset_id);
      if (!edge) {
        edge = await this.loadGlb(edgeAsset.uri);
        this.edgeCache.set(edgeAsset.asset_id, edge);
      }
      const edgeInstance = edge.clone(true);
      edgeInstance.traverse((child) => { if (child instanceof THREE.LineSegments) addWideEdgeVisual(child, this.resolution()); });
      group.add(edgeInstance);
    }
    if (sidecar) {
      const vertices = sidecar.entities.filter((entity) => entity.kind === 'vertex');
      if (vertices.length) {
        const positions = new Float32Array(vertices.length * 3);
        vertices.forEach((entity, index) => {
          const position = entity.properties.position;
          if (Array.isArray(position) && position.length === 3 && position.every((item) => typeof item === 'number')) cadPointToGltf(position as Vec3).toArray(positions, index * 3);
        });
        const vertexGeometry = new THREE.BufferGeometry();
        vertexGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        const vertexPoints = new THREE.Points(vertexGeometry, new THREE.PointsMaterial({ color: '#d8ff83', size: 7, sizeAttenuation: false, depthWrite: false, transparent: true, opacity: 0.48 }));
        vertexPoints.visible = this.selectionMode === 'vertex';
        vertexPoints.userData.pickRole = 'vertex';
        vertexPoints.userData.pickable = true;
        vertexPoints.userData.vertexEntityIds = vertices.map((entity) => entity.entity_id);
        group.add(vertexPoints);
      }
    }
    return group;
  }

  clearScene(): void {
    this.clearMarks();
    for (const object of this.geometryCache.values()) disposeObject(object);
    for (const object of this.edgeCache.values()) disposeObject(object);
    while (this.modelRoot.children.length) {
      const child = this.modelRoot.children[0];
      disposeObject(child);
      this.modelRoot.remove(child);
    }
    this.nodeObjects.clear();
    this.nodeVisibility.clear();
    this.edgeCache.clear();
    this.entityCache.clear();
    this.geometryCache.clear();
    this.manifest = null;
    this.files = null;
  }

  // -- picking ---------------------------------------------------------------

  setSelectionMode(mode: SelectionMode): void {
    this.selectionMode = mode;
    this.applySelectionModeVisibility();
  }

  private applySelectionModeVisibility(): void {
    for (const object of this.nodeObjects.values()) {
      object.traverse((child) => {
        if (child.userData.pickRole === 'vertex') child.visible = this.selectionMode === 'vertex';
      });
    }
  }

  private isEffectivelyVisible(object: THREE.Object3D): boolean {
    for (let current: THREE.Object3D | null = object; current; current = current.parent) {
      if (!current.visible) return false;
      if (current === this.modelRoot) break;
    }
    return true;
  }

  setNodeVisible(nodeId: string, visible: boolean): void {
    const object = this.nodeObjects.get(nodeId);
    if (!object) return;
    object.visible = visible;
    this.nodeVisibility.set(nodeId, visible);
  }

  get nodes(): SceneNode[] {
    return this.manifest?.nodes ?? [];
  }

  nodeObject(nodeId: string): THREE.Group | undefined {
    return this.nodeObjects.get(nodeId);
  }

  entityFor(nodeId: string, entityId: string): Entity | null {
    const node = this.manifest?.nodes.find((item) => item.node_id === nodeId);
    return this.sidecarFor(node)?.entities.find((item) => item.entity_id === entityId) ?? null;
  }

  private pointerRay(event: PointerEvent): void {
    const bounds = this.renderer.domElement.getBoundingClientRect();
    this.pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
    this.pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const distance = this.camera.position.distanceTo(this.controls.target);
    const worldPerPixel = 2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov * 0.5)) * distance / Math.max(bounds.height, 1);
    this.raycaster.params.Line.threshold = worldPerPixel * 5;
    this.raycaster.params.Points.threshold = worldPerPixel * 8;
  }

  pick(event: PointerEvent): PickResult | null {
    this.pointerRay(event);
    const hits = this.raycaster.intersectObjects(this.modelRoot.children, true).filter((hit) => {
      if (hit.object.userData.pickable === false || !this.isEffectivelyVisible(hit.object)) return false;
      return typeof hit.object.userData.nodeId === 'string';
    });
    const meshHit = hits.find((hit) => hit.object instanceof THREE.Mesh);
    if (this.selectionMode === 'component' || this.selectionMode === 'solid' || this.selectionMode === 'face') {
      if (!meshHit) return null;
    } else {
      const candidate = hits.find((hit) => this.selectionMode === 'edge' ? hit.object instanceof THREE.LineSegments : hit.object instanceof THREE.Points);
      if (!candidate) return null;
      if (meshHit) {
        const occlusionAllowance = this.selectionMode === 'edge' ? this.raycaster.params.Line.threshold : this.raycaster.params.Points.threshold;
        if (candidate.distance > meshHit.distance + occlusionAllowance * 1.5) return null;
      }
    }
    const hit = (this.selectionMode === 'edge' || this.selectionMode === 'vertex')
      ? hits.find((item) => this.selectionMode === 'edge' ? item.object instanceof THREE.LineSegments : item.object instanceof THREE.Points) ?? meshHit
      : meshHit;
    if (!hit) return null;
    const nodeId = hit.object.userData.nodeId as string;
    const node = this.manifest?.nodes.find((item) => item.node_id === nodeId);
    const sidecar = this.sidecarFor(node);
    if (this.selectionMode === 'component') {
      return { nodeId, entityId: null, mode: 'component', entity: null };
    }
    if (this.selectionMode === 'solid') {
      const solid = sidecar?.entities.find((item) => item.kind === 'solid') ?? null;
      return { nodeId, entityId: solid?.entity_id ?? null, mode: 'solid', entity: solid };
    }
    let entityId: string | undefined;
    if (this.selectionMode === 'face' && hit.object instanceof THREE.Mesh && typeof hit.faceIndex === 'number') {
      const triangleOffset = hit.faceIndex * 3;
      entityId = sidecar?.face_groups.find((group: FaceGroup) => triangleOffset >= group.first_index && triangleOffset < group.first_index + group.index_count)?.entity_id;
    } else if (this.selectionMode === 'edge' && hit.object instanceof THREE.LineSegments && typeof hit.index === 'number') {
      entityId = sidecar?.edge_groups.find((group: FaceGroup) => hit.index! >= group.first_index && hit.index! < group.first_index + group.index_count)?.entity_id;
    } else if (this.selectionMode === 'vertex' && hit.object instanceof THREE.Points && typeof hit.index === 'number') {
      entityId = hit.object.userData.vertexEntityIds?.[hit.index];
    }
    if (!entityId) return null;
    return { nodeId, entityId, mode: this.selectionMode, entity: this.entityFor(nodeId, entityId) };
  }

  // -- highlight + marks -------------------------------------------------------

  private attachOverlay(source: THREE.Object3D, overlay: THREE.Object3D): THREE.Object3D {
    overlay.name = 'entity-overlay';
    overlay.userData.pickable = false;
    overlay.renderOrder = 10;
    overlay.matrix.copy(source.matrix);
    overlay.matrixAutoUpdate = false;
    overlay.visible = source.visible;
    source.parent?.add(overlay);
    return overlay;
  }

  buildEntityOverlays(nodeId: string, entityId: string | null, color: string, opacity = 0.72): THREE.Object3D[] {
    const object = this.nodeObjects.get(nodeId);
    const node = this.manifest?.nodes.find((item) => item.node_id === nodeId);
    const sidecar = this.sidecarFor(node);
    if (!object || !sidecar) return [];
    const entityGroup = entityId ? sidecar.face_groups.find((group: FaceGroup) => group.entity_id === entityId) : undefined;
    const edgeGroup = entityId ? sidecar.edge_groups.find((group: FaceGroup) => group.entity_id === entityId) : undefined;
    const isSolid = entityId?.startsWith('entity/solid/');
    const isVertex = entityId?.startsWith('entity/vertex/');
    const overlays: THREE.Object3D[] = [];
    object.traverse((child: THREE.Object3D) => {
      if (overlays.length || !this.isEffectivelyVisible(child) || !(child instanceof THREE.Mesh || child instanceof THREE.LineSegments || child instanceof THREE.Points)) return;
      const source = child as THREE.Mesh | THREE.LineSegments | THREE.Points;
      const range = entityGroup || edgeGroup;
      if (!range && !isVertex && !isSolid) return;
      if (entityGroup && !(source instanceof THREE.Mesh)) return;
      if (edgeGroup && !entityGroup && !(source instanceof THREE.LineSegments)) return;
      if (isVertex && !source.userData.vertexEntityIds?.includes(entityId!)) return;
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
        const material = new LineMaterial({ color, linewidth: 5, worldUnits: false, depthTest: false, transparent: true, opacity: 1 });
        material.resolution.set(this.renderer.domElement.clientWidth, this.renderer.domElement.clientHeight);
        overlays.push(this.attachOverlay(source, new LineSegments2(lineGeometry, material)));
      } else if (source instanceof THREE.Points) {
        const geometry = source.geometry.clone();
        const vertexIndex = source.userData.vertexEntityIds.indexOf(entityId!);
        geometry.setDrawRange(vertexIndex, 1);
        overlays.push(this.attachOverlay(source, new THREE.Points(geometry, new THREE.PointsMaterial({ color, size: 16, sizeAttenuation: false, depthTest: false, transparent: true, opacity: 1 }))));
      } else {
        const geometry = source.geometry.clone();
        if (range) geometry.setDrawRange(range.first_index, range.index_count);
        overlays.push(this.attachOverlay(source, new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: isSolid ? opacity * 0.55 : opacity, depthTest: false, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 }))));
      }
    });
    return overlays;
  }

  addMark(nodeId: string, entityId: string | null, color: string): void {
    const key = `${nodeId}::${entityId ?? 'component'}`;
    if (this.marks.some((mark) => mark.key === key)) return;
    const overlays = this.buildEntityOverlays(nodeId, entityId, color);
    if (overlays.length) this.marks.push({ key, color, overlays });
  }

  removeMark(key: string): void {
    const index = this.marks.findIndex((mark) => mark.key === key);
    if (index < 0) return;
    for (const overlay of this.marks[index].overlays) {
      overlay.parent?.remove(overlay);
      disposeObject(overlay);
    }
    this.marks.splice(index, 1);
  }

  clearMarks(): void {
    for (const mark of this.marks) {
      for (const overlay of mark.overlays) {
        overlay.parent?.remove(overlay);
        disposeObject(overlay);
      }
    }
    this.marks = [];
  }

  hasMark(nodeId: string, entityId: string | null): boolean {
    return this.marks.some((mark) => mark.key === `${nodeId}::${entityId ?? 'component'}`);
  }

  // -- camera + lifecycle --------------------------------------------------------

  frame(): void {
    const box = new THREE.Box3().setFromObject(this.modelRoot);
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.length() * 0.5, 0.01);
    this.camera.position.copy(center).add(new THREE.Vector3(1, 0.78, 1).normalize().multiplyScalar(radius * 2.8));
    this.camera.near = Math.max(radius / 100, 0.001);
    this.camera.far = Math.max(radius * 100, 10);
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(center);
    this.controls.maxDistance = radius * 12;
    this.controls.update();
  }

  getCameraState(): CameraState {
    const bounds = this.renderer.domElement.getBoundingClientRect();
    return {
      position: [this.camera.position.x, this.camera.position.y, this.camera.position.z],
      target: [this.controls.target.x, this.controls.target.y, this.controls.target.z],
      up: [this.camera.up.x, this.camera.up.y, this.camera.up.z],
      fov_deg: this.camera.fov,
      width: Math.round(bounds.width),
      height: Math.round(bounds.height),
    };
  }

  snapshotPng(): string | null {
    try {
      this.renderer.render(this.threeScene, this.camera);
      return this.renderer.domElement.toDataURL('image/png');
    } catch {
      return null;
    }
  }

  private resize(): void {
    const width = this.host.clientWidth;
    const height = this.host.clientHeight;
    if (width <= 0 || height <= 0) return;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / Math.max(height, 1);
    this.camera.updateProjectionMatrix();
    // The scene may load before the host has its final layout; re-frame once.
    if (this.pendingFrame && this.modelRoot.children.length) {
      this.pendingFrame = false;
      this.frame();
    }
    const resolution = this.resolution();
    this.modelRoot.traverse((object) => {
      if (object instanceof LineSegments2) object.material.resolution.set(resolution.width, resolution.height);
    });
    for (const mark of this.marks) {
      for (const overlay of mark.overlays) {
        overlay.traverse((object) => {
          if (object instanceof LineSegments2) object.material.resolution.set(resolution.width, resolution.height);
        });
      }
    }
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.unbindClick?.();
    this.observer.disconnect();
    this.renderer.setAnimationLoop(null);
    this.clearScene();
    this.controls.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
