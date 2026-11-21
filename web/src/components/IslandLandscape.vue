<template>
  <canvas ref="canvas" class="island-landscape" width="1440" height="500" aria-hidden="true"></canvas>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

const canvas = ref<HTMLCanvasElement | null>(null);

// Project a series of terrain sections onto the page, drawing the far shore first.
const peaks = [
  [-0.38, -0.12, 0.32, 0.55, 0.54],
  [0.04, -0.33, 0.28, 0.47, 1.16],
  [0.47, 0.12, 0.34, 0.54, 0.68],
];

function elevation(x: number, depth: number) {
  const ridge = peaks.reduce((sum, [cx, cz, sx, sz, height]) =>
    sum + height * Math.exp(-(((x - cx) / sx) ** 2 + ((depth - cz) / sz) ** 2)), 0);
  const folds = 1 + 0.085 * Math.sin(x * 24 + depth * 5) + 0.04 * Math.cos(x * 47 - depth * 3);
  return ridge * folds;
}

let observer: ResizeObserver | undefined;

function drawLandscape() {
  const ctx = canvas.value?.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(2, 0, 0, 2, 0, 0);
  ctx.clearRect(0, 0, 720, 250);
  const compact = ctx.canvas.clientWidth < 260;
  const slices = compact ? 22 : 68;
  ctx.lineJoin = "round";
  // 铜版画 / 水墨等高线质感：浅宣纸底配极细松烟墨线，零 AI 荧光感
  for (let i = 0; i < (compact ? 3 : 9); i++) {
    ctx.beginPath();
    ctx.ellipse(391, 179, 210 + i * 12, 33 + i * 4, -0.06, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(36, 40, 38, ${Math.max(0.02, 0.11 - i * 0.01)})`;
    ctx.lineWidth = 0.55;
    ctx.stroke();
  }
  for (let slice = 0; slice <= slices; slice++) {
    const z = -1 + 2 * slice / slices;
    const halfWidth = Math.sqrt(Math.max(0, 1 - z * z));
    const line = new Path2D();
    const base = 176 + z * 36;
    let left = 0;
    let right = 0;
    for (let i = 0; i <= 250; i++) {
      const x = halfWidth * (i / 125 - 1);
      const px = 387 + 249 * x + z * 28;
      const py = base - elevation(x, z) * 100 - 9 * x;
      if (i === 0) { line.moveTo(px, py); left = px; }
      else line.lineTo(px, py);
      right = px;
    }
    const face = new Path2D(line);
    face.lineTo(right, base + 11);
    face.lineTo(left, base + 11);
    face.closePath();
    ctx.fillStyle = "#f4efe5";
    ctx.fill(face);
    const isMajor = slice % 5 === 0;
    ctx.lineWidth = compact ? 1.5 : (isMajor ? 0.9 : 0.52);
    ctx.strokeStyle = isMajor ? "rgba(28, 34, 31, 0.42)" : "rgba(28, 34, 31, 0.16)";
    ctx.stroke(line);
  }
}

onMounted(() => {
  drawLandscape();
  if (canvas.value) {
    observer = new ResizeObserver(drawLandscape);
    observer.observe(canvas.value);
  }
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<style scoped>
.island-landscape { display: block; width: 100%; height: 100%; object-fit: contain; }
</style>
