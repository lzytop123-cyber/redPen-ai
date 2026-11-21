const PWD_KEY = "zhixingdao_admin_pwd";

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
  const res = await fetch(path, {
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
  const res = await fetch(`/api/admin/uploads/${encodeURIComponent(filename)}`, {
    headers: { "X-Admin-Password": getAdminPwd() },
  });
  if (!res.ok) {
    throw new Error("原图加载失败");
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function downloadCodesCsv(): Promise<void> {
  const res = await fetch("/api/admin/codes/export", {
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
