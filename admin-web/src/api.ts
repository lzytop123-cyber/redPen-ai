const PWD_KEY = "zhixingdao_admin_pwd";

function resolveApiBase(): string {
  const raw = (import.meta.env.VITE_API_BASE ?? "").trim().replace(/\/$/, "");
  if (!raw) return "";
  if (import.meta.env.PROD && !raw.startsWith("https://")) {
    throw new Error("生产构建的 VITE_API_BASE 必须是 https:// 开头，或留空以使用同源 /api");
  }
  return raw;
}

const API_BASE = resolveApiBase();

export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${normalized}`;
}

export function getAdminPwd(): string {
  return sessionStorage.getItem(PWD_KEY) || "";
}

export function setAdminPwd(pwd: string) {
  sessionStorage.setItem(PWD_KEY, pwd);
}

export function clearAdminPwd() {
  sessionStorage.removeItem(PWD_KEY);
}

export async function adminFetch<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const pwd = getAdminPwd();
  const res = await fetch(apiUrl(path), {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Password": pwd,
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `请求失败 (${res.status})`);
  }
  return res.json();
}

export async function fetchUploadImageBlobUrl(filename: string): Promise<string> {
  const res = await fetch(apiUrl(`/api/admin/uploads/${encodeURIComponent(filename)}`), {
    headers: { "X-Admin-Password": getAdminPwd() },
  });
  if (!res.ok) {
    throw new Error("原图加载失败");
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function downloadCodesCsv(): Promise<void> {
  const res = await fetch(apiUrl("/api/admin/codes/export"), {
    headers: { "X-Admin-Password": getAdminPwd() },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "导出失败");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "zhixingdao_codes.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * 将后端返回的 UTC 时间字符串（如 "2026-11-21T10:03:12.345"）转换为北京时间（UTC+8）"YYYY-MM-DD HH:mm"
 */
export function formatBeijingTime(iso?: string | null, dateOnly = false): string {
  if (!iso) return "";
  const raw = iso.trim();
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(raw);
  const d = new Date(hasTz ? raw : `${raw.replace(" ", "T")}Z`);
  if (Number.isNaN(d.getTime())) {
    return raw.replace("T", " ").slice(0, dateOnly ? 10 : 16);
  }
  const bjMs = d.getTime() + 8 * 3600 * 1000;
  const bj = new Date(bjMs);
  const yyyy = bj.getUTCFullYear();
  const mm = String(bj.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(bj.getUTCDate()).padStart(2, "0");
  if (dateOnly) return `${yyyy}-${mm}-${dd}`;
  const hh = String(bj.getUTCHours()).padStart(2, "0");
  const min = String(bj.getUTCMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
}

