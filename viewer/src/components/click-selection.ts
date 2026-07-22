import * as THREE from 'three';
import type { OrbitControls } from 'three/addons/controls/OrbitControls.js';

type ClickSelectionOptions = {
  element: HTMLElement;
  camera: THREE.PerspectiveCamera;
  controls: OrbitControls;
  movementThreshold?: number;
  onPointerStateChange?: (active: boolean) => void;
  onClick: (event: PointerEvent) => void;
};

export function bindClickSelection(options: ClickSelectionOptions): () => void {
  const { element, camera, controls, onClick, movementThreshold = 4 } = options;
  let pointerDown: {
    x: number;
    y: number;
    button: number;
    position: THREE.Vector3;
    target: THREE.Vector3;
    zoom: number;
  } | null = null;

  const onPointerDown = (event: PointerEvent): void => {
    pointerDown = {
      x: event.clientX,
      y: event.clientY,
      button: event.button,
      position: camera.position.clone(),
      target: controls.target.clone(),
      zoom: camera.zoom,
    };
    options.onPointerStateChange?.(true);
  };
  const onPointerUp = (event: PointerEvent): void => {
    const down = pointerDown;
    pointerDown = null;
    options.onPointerStateChange?.(false);
    if (!down || down.button !== 0 || event.button !== 0) return;
    if (Math.hypot(event.clientX - down.x, event.clientY - down.y) > movementThreshold) return;

    // OrbitControls treats any pointer movement as rotation. Drain that movement,
    // then restore the click-time camera before committing selection.
    const damping = controls.enableDamping;
    controls.enableDamping = false;
    controls.update();
    camera.position.copy(down.position);
    camera.zoom = down.zoom;
    camera.updateProjectionMatrix();
    controls.target.copy(down.target);
    controls.update();
    controls.enableDamping = damping;
    onClick(event);
  };
  const onPointerLeave = (): void => {
    pointerDown = null;
    options.onPointerStateChange?.(false);
  };

  element.addEventListener('pointerdown', onPointerDown);
  element.addEventListener('pointerup', onPointerUp);
  element.addEventListener('pointerleave', onPointerLeave);
  return () => {
    element.removeEventListener('pointerdown', onPointerDown);
    element.removeEventListener('pointerup', onPointerUp);
    element.removeEventListener('pointerleave', onPointerLeave);
  };
}
