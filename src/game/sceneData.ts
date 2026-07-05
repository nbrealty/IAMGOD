// Hollywood & Highland scene GEOMETRY — building footprints and the shared spatial
// constants the renderer reads. NPC souls now live in src/soul/ (the roster + the
// utility-AI engine); this file is pure geometry.

export interface Building {
  special?: "tcl";
  x: number;
  width?: number;
  height?: number;
  side?: "north" | "south";
  facadeColor?: string;
  roofColor?: string;
  label?: string;
  marquee?: string;
  marqueeColor?: string;
  depth?: number;
  skew?: number;
}

// Virtual canvas size — the renderer draws to this coordinate space and scales.
export const SCENE_W = 1600;
export const SCENE_H = 900;

export const ROAD_TOP = 420;
export const ROAD_BOTTOM = 520;
export const NORTH_SIDEWALK_TOP = 380;
export const SOUTH_SIDEWALK_TOP = ROAD_BOTTOM;
export const SOUTH_SIDEWALK_BOTTOM = 560;
export const NORTH_BASELINE = NORTH_SIDEWALK_TOP;
export const SOUTH_BASELINE = SOUTH_SIDEWALK_BOTTOM;
export const HIGHLAND_LEFT = 480;
export const HIGHLAND_RIGHT = 560;

export const NORTH_BUILDINGS: Building[] = [
  { special: "tcl", x: 60 },
  { x: 350, width: 100, height: 74, side: "north", facadeColor: "#8a6a44", label: "SOUVENIRS" },
  {
    x: 600,
    width: 250,
    height: 150,
    side: "north",
    facadeColor: "#5b6b7a",
    label: "OVATION HOLLYWOOD",
    marquee: "DOLBY THEATRE",
    marqueeColor: "#c9962c",
  },
  { x: 900, width: 90, height: 80, side: "north", facadeColor: "#7a5b6a", label: "CANDY CO." },
  {
    x: 1030,
    width: 210,
    height: 140,
    side: "north",
    facadeColor: "#7a3b2e",
    label: "EL CAPITAN",
    marquee: "NOW PLAYING",
    marqueeColor: "#2e8f6b",
  },
  {
    x: 1290,
    width: 240,
    height: 110,
    side: "north",
    facadeColor: "#3c3c46",
    label: "MADAME TUSSAUDS",
    marquee: "WAX MUSEUM",
    marqueeColor: "#c9962c",
  },
];

export const SOUTH_BUILDINGS: Building[] = [
  { x: 60, width: 130, height: 90, side: "south", facadeColor: "#6a5a44", label: "T-SHIRTS" },
  { x: 220, width: 120, height: 80, side: "south", facadeColor: "#4a5a6a", label: "PIZZA" },
  { x: 600, width: 170, height: 100, side: "south", facadeColor: "#5c4a63", label: "TOUR TICKETS" },
  { x: 810, width: 130, height: 82, side: "south", facadeColor: "#6a4a4a", label: "GIFT SHOP" },
  { x: 1000, width: 150, height: 92, side: "south", facadeColor: "#4a6a52", label: "CAFE" },
  { x: 1220, width: 250, height: 100, side: "south", facadeColor: "#5a5040", label: "PARKING STRUCTURE" },
];
