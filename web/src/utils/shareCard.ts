import type { GradingReport } from "../types";
import { selectReportAdvice } from "./reportAdvice";

function wrapLines(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
  maxLines: number
): string[] {
  const lines: string[] = [];
  let current = "";
  for (const ch of Array.from(text)) {
    if (ch === "\n") {
      lines.push(current);
      current = "";
      if (lines.length >= maxLines) return lines;
      continue;
    }
    const test = current + ch;
    if (ctx.measureText(test).width > maxWidth && current) {
      lines.push(current);
      current = ch;
      if (lines.length >= maxLines) {
        lines[lines.length - 1] = lines[lines.length - 1].slice(0, -1) + "…";
        return lines;
      }
    } else {
      current = test;
    }
  }
  if (current && lines.length < maxLines) {
    lines.push(current);
  }
  return lines;
}

function drawIslandLogo(ctx: CanvasRenderingContext2D, x: number, y: number, scale = 0.42) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(scale, scale);
  ctx.fillStyle = "#1A1C1B";

  // 山岛主体
  ctx.beginPath();
  ctx.moveTo(60, 12);
  ctx.bezierCurveTo(50, 22, 36, 30, 16, 35);
  ctx.lineTo(104, 35);
  ctx.bezierCurveTo(84, 30, 70, 22, 60, 12);
  ctx.closePath();
  ctx.fill();

  // 水平面
  ctx.fillRect(6, 40, 108, 3.2);
  // 水波倒影
  ctx.fillRect(29, 49, 62, 3);
  ctx.fillRect(40, 57.5, 40, 2.8);
  ctx.fillRect(49, 65.5, 22, 2.5);

  ctx.restore();
}

/**
 * 渲染 3:4 竖版小红书宣纸风精批打卡成绩卡 (900 x 1200)
 */
export function renderShareCardDataUrl(report: GradingReport): string {
  const W = 900;
  const H = 1200;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d")!;

  const serif = '"Noto Serif SC", "Songti SC", "STSong", Georgia, serif';
  const sans = '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif';

  // 1. 暖宣纸底色
  const bgGrad = ctx.createLinearGradient(0, 0, W, H);
  bgGrad.addColorStop(0, "#FAF8F3");
  bgGrad.addColorStop(1, "#F0EBE0");
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, W, H);

  // 2. 双层线装书边框
  ctx.strokeStyle = "#DCD4C4";
  ctx.lineWidth = 2;
  ctx.strokeRect(36, 36, W - 72, H - 72);
  ctx.strokeStyle = "rgba(26, 28, 27, 0.08)";
  ctx.lineWidth = 1;
  ctx.strokeRect(46, 46, W - 92, H - 92);

  // 3. 顶部品牌 + 日期
  drawIslandLogo(ctx, 74, 76, 0.44);
  ctx.fillStyle = "#1A1C1B";
  ctx.font = `700 26px ${serif}`;
  ctx.fillText("知行岛·自习室", 136, 104);

  const now = new Date();
  const dateStr = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, "0")}.${String(
    now.getDate()
  ).padStart(2, "0")}`;
  ctx.fillStyle = "#827F78";
  ctx.font = `500 18px ${sans}`;
  ctx.textAlign = "right";
  ctx.fillText(`AI 红笔精批打卡 · ${dateStr}`, W - 76, 102);
  ctx.textAlign = "left";

  // 细分割线 + 朱砂短线
  ctx.fillStyle = "#E2DACB";
  ctx.fillRect(76, 136, W - 152, 1.5);
  ctx.fillStyle = "#C63829";
  ctx.fillRect(76, 135, 44, 3);

  // 4. 题目名称
  ctx.fillStyle = "#1A1C1B";
  ctx.font = `700 32px ${serif}`;
  const titleLines = wrapLines(ctx, report.question_title || "主观题精批报告", W - 152, 2);
  let y = 196;
  for (const line of titleLines) {
    ctx.fillText(line, 76, y);
    y += 46;
  }

  const isEn = report.exam_type === "kaoyan_english";
  ctx.fillStyle = "#75726A";
  ctx.font = `400 20px ${sans}`;
  ctx.fillText(`本次作答 ${report.word_count} ${isEn ? "词" : "字"}`, 76, y + 6);

  // 5. 核心得分朱砂印章卡
  const boxY = y + 38;
  const boxH = 228;
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(76, boxY, W - 152, boxH);
  ctx.strokeStyle = "#E4DDD0";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(76, boxY, W - 152, boxH);

  // 左侧大号朱砂得分
  ctx.fillStyle = "#C63829";
  ctx.font = `900 96px ${serif}`;
  const scoreStr = String(report.final_score);
  ctx.fillText(scoreStr, 118, boxY + 132);
  const sw = ctx.measureText(scoreStr).width;
  ctx.fillStyle = "#8A867E";
  ctx.font = `500 34px ${serif}`;
  ctx.fillText(`/ ${report.full_score}`, 128 + sw, boxY + 130);

  // 右侧定档印章
  const bandText = report.band_label || "精批完成";
  ctx.fillStyle = "#1F2321";
  ctx.fillRect(118, boxY + 158, Math.max(136, bandText.length * 24 + 40), 40);
  ctx.fillStyle = "#FAF8F4";
  ctx.font = `600 20px ${sans}`;
  ctx.fillText(bandText, 138, boxY + 185);

  // 采分点命中率或维度概要（右侧）
  const matches = report.shenlun_detail?.point_matches || [];
  if (matches.length > 0) {
    const hit = matches.filter((m) => m.status === "hit").length;
    const partial = matches.filter((m) => m.status === "partial").length;
    const pct = Math.round(((hit + partial * 0.5) / matches.length) * 100);
    ctx.textAlign = "right";
    ctx.fillStyle = "#78746C";
    ctx.font = `500 18px ${sans}`;
    ctx.fillText("标准采分点命中率", W - 116, boxY + 76);
    ctx.fillStyle = "#1F2321";
    ctx.font = `700 54px ${serif}`;
    ctx.fillText(`${pct}%`, W - 116, boxY + 142);
    ctx.fillStyle = "#78746C";
    ctx.font = `400 18px ${sans}`;
    ctx.fillText(`完整命中 ${hit} / ${matches.length} 点`, W - 116, boxY + 184);
    ctx.textAlign = "left";
  } else {
    const dims = (report.shenlun_essay_detail || report.kaoyan_detail)?.dimensions || [];
    ctx.textAlign = "right";
    ctx.fillStyle = "#78746C";
    ctx.font = `500 18px ${sans}`;
    ctx.fillText("官方维度定档", W - 116, boxY + 72);
    let dy = boxY + 110;
    dims.slice(0, 3).forEach((d) => {
      ctx.fillStyle = "#1A1C1B";
      ctx.font = `500 20px ${sans}`;
      ctx.fillText(`${d.dimension} · 第 ${d.level} 档`, W - 116, dy);
      dy += 34;
    });
    ctx.textAlign = "left";
  }

  // 6. 核心提分建议卡片
  const adv = selectReportAdvice(report);
  const advY = boxY + boxH + 38;
  ctx.fillStyle = "#FDF8F6";
  ctx.fillRect(76, advY, W - 152, 236);
  ctx.fillStyle = "#C63829";
  ctx.fillRect(76, advY, 6, 236);

  ctx.fillStyle = "#C63829";
  ctx.font = `700 18px ${sans}`;
  ctx.fillText("下一步核心提分方向", 108, advY + 42);

  ctx.fillStyle = "#1A1C1B";
  ctx.font = `700 24px ${serif}`;
  const advTitleLines = wrapLines(ctx, adv.title, W - 216, 1);
  ctx.fillText(advTitleLines[0] || "", 108, advY + 86);

  ctx.fillStyle = "#4A4945";
  ctx.font = `400 21px ${sans}`;
  const advBodyLines = wrapLines(ctx, adv.text, W - 216, 3);
  let ay = advY + 130;
  for (const l of advBodyLines) {
    ctx.fillText(l, 108, ay);
    ay += 34;
  }

  // 7. 核心提分改动（最多2条）
  const imps = (report.key_improvements || []).slice(0, 2);
  let iy = advY + 286;
  if (imps.length) {
    ctx.fillStyle = "#78746C";
    ctx.font = `600 18px ${sans}`;
    ctx.fillText("本次报告核心升格要点", 76, iy);
    iy += 36;
    ctx.fillStyle = "#2E2E2B";
    ctx.font = `400 20px ${sans}`;
    for (const imp of imps) {
      const impLines = wrapLines(ctx, `· ${imp}`, W - 152, 2);
      for (const l of impLines) {
        ctx.fillText(l, 76, iy);
        iy += 32;
      }
      iy += 8;
    }
  }

  // 8. 底部自习室落款
  ctx.fillStyle = "#E2DACB";
  ctx.fillRect(76, H - 132, W - 152, 1);

  ctx.fillStyle = "#52514D";
  ctx.font = `600 21px ${serif}`;
  ctx.fillText("道虽迩，不行不至；事虽小，不为不成。", 76, H - 82);

  ctx.textAlign = "right";
  ctx.fillStyle = "#827F78";
  ctx.font = `400 17px ${sans}`;
  ctx.fillText("知行岛·自习室 · 真题 AI 红笔精批", W - 76, H - 82);
  ctx.textAlign = "left";

  return canvas.toDataURL("image/png");
}
