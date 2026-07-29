// Interpolasi warna kontinu untuk heatmap compatibility score.
// Mirror dari token warna di globals.css (--twin-accent-danger/warning/safe),
// diduplikasi di sini sebagai hex karena CSS custom properties tidak mudah
// dibaca untuk interpolasi numerik di JS tanpa getComputedStyle.
const DANGER = { r: 0xd1, g: 0x55, b: 0x3d }; // --twin-accent-danger
const WARNING = { r: 0xe0, g: 0xa0, b: 0x30 }; // --twin-accent-warning
const SAFE = { r: 0x5f, g: 0xae, b: 0x72 }; // --twin-accent-safe

function lerp(a: number, b: number, t: number): number {
  return Math.round(a + (b - a) * t);
}

function rgbToHex(r: number, g: number, b: number): string {
  return `#${[r, g, b].map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}

/**
 * score: 0.0 - 1.0
 * < 0.5  : interpolasi danger -> warning
 * >= 0.5 : interpolasi warning -> safe
 */
export function compatibilityScoreToColor(score: number): string {
  const clamped = Math.max(0, Math.min(1, score));

  if (clamped < 0.5) {
    const t = clamped / 0.5;
    return rgbToHex(
      lerp(DANGER.r, WARNING.r, t),
      lerp(DANGER.g, WARNING.g, t),
      lerp(DANGER.b, WARNING.b, t)
    );
  }

  const t = (clamped - 0.5) / 0.5;
  return rgbToHex(
    lerp(WARNING.r, SAFE.r, t),
    lerp(WARNING.g, SAFE.g, t),
    lerp(WARNING.b, SAFE.b, t)
  );
}

/**
 * Menentukan warna teks (gelap/terang) agar tetap terbaca di atas
 * background heatmap yang bervariasi.
 */
export function readableTextColor(score: number): string {
  return score >= 0.35 && score <= 0.75 ? "#12151a" : "#f4f5f6";
}