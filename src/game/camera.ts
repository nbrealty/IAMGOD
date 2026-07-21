// Camera for the block view. Works in CSS-pixel screen space:
//   screen = (world - cam.{x,y}) * cam.zoom
//   world  = screen / cam.zoom + cam.{x,y}
// (Device-pixel-ratio is applied separately in the renderer's transform.)

export interface Camera {
  x: number; // world coord shown at the viewport's top-left
  y: number;
  zoom: number; // CSS pixels per world unit
}

// The minimum zoom. `cover` (default) = fill the viewport in at least one axis so you never see
// past the world edge (used for the boulevard, and a room's default framing). `cover=false` =
// CONTAIN: the whole world can fit on screen, so a room can be zoomed all the way out to show the
// entire plate (with the empty area centered/letterboxed).
export function minZoomFor(vw: number, vh: number, ww: number, wh: number, cover = true): number {
  return cover ? Math.max(vw / ww, vh / wh) : Math.min(vw / ww, vh / wh);
}

function maxZoomFor(minZ: number): number {
  // Allow zooming in much closer now that characters carry real sprite detail.
  return Math.max(minZ * 5, 3);
}

export function clampCamera(cam: Camera, vw: number, vh: number, ww: number, wh: number, cover = true): void {
  const minZ = minZoomFor(vw, vh, ww, wh, cover);
  cam.zoom = Math.min(maxZoomFor(minZ), Math.max(minZ, cam.zoom));
  const viewW = vw / cam.zoom;
  const viewH = vh / cam.zoom;
  // When the view is wider/taller than the world (zoomed out past cover), CENTER the world in that
  // axis instead of pinning it to the top-left; otherwise clamp so no edge shows.
  cam.x = viewW >= ww ? (ww - viewW) / 2 : Math.min(Math.max(0, cam.x), ww - viewW);
  cam.y = viewH >= wh ? (wh - viewH) / 2 : Math.min(Math.max(0, cam.y), wh - viewH);
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
  cover = true,
): void {
  const before = screenToWorld(cam, sx, sy);
  const minZ = minZoomFor(vw, vh, ww, wh, cover);
  cam.zoom = Math.min(maxZoomFor(minZ), Math.max(minZ, cam.zoom * factor));
  cam.x = before.x - sx / cam.zoom;
  cam.y = before.y - sy / cam.zoom;
  clampCamera(cam, vw, vh, ww, wh, cover);
}
