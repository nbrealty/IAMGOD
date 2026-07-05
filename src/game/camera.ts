// Camera for the block view. Works in CSS-pixel screen space:
//   screen = (world - cam.{x,y}) * cam.zoom
//   world  = screen / cam.zoom + cam.{x,y}
// (Device-pixel-ratio is applied separately in the renderer's transform.)

export interface Camera {
  x: number; // world coord shown at the viewport's top-left
  y: number;
  zoom: number; // CSS pixels per world unit
}

// The minimum zoom that still covers the viewport in at least one axis, so you can't
// pan past the edge of the world in that axis (the other axis stays pannable).
export function minZoomFor(vw: number, vh: number, ww: number, wh: number): number {
  return Math.max(vw / ww, vh / wh);
}

function maxZoomFor(minZ: number): number {
  // Allow zooming in much closer now that characters carry real sprite detail.
  return Math.max(minZ * 5, 3);
}

export function clampCamera(cam: Camera, vw: number, vh: number, ww: number, wh: number): void {
  const minZ = minZoomFor(vw, vh, ww, wh);
  cam.zoom = Math.min(maxZoomFor(minZ), Math.max(minZ, cam.zoom));
  const viewW = vw / cam.zoom;
  const viewH = vh / cam.zoom;
  cam.x = Math.min(Math.max(0, cam.x), Math.max(0, ww - viewW));
  cam.y = Math.min(Math.max(0, cam.y), Math.max(0, wh - viewH));
}

export function screenToWorld(cam: Camera, sx: number, sy: number): { x: number; y: number } {
  return { x: sx / cam.zoom + cam.x, y: sy / cam.zoom + cam.y };
}

// Zoom by `factor`, keeping the world point under (sx, sy) fixed on screen.
export function zoomAbout(
  cam: Camera,
  factor: number,
  sx: number,
  sy: number,
  vw: number,
  vh: number,
  ww: number,
  wh: number,
): void {
  const before = screenToWorld(cam, sx, sy);
  const minZ = minZoomFor(vw, vh, ww, wh);
  cam.zoom = Math.min(maxZoomFor(minZ), Math.max(minZ, cam.zoom * factor));
  cam.x = before.x - sx / cam.zoom;
  cam.y = before.y - sy / cam.zoom;
  clampCamera(cam, vw, vh, ww, wh);
}
