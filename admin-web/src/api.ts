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

export function uploadImageUrl(filename: string): string {
  return `/api/admin/uploads/${encodeURIComponent(filename)}?pwd=${encodeURIComponent(getAdminPwd())}`;
}

export function exportCodesCsvUrl(): string {
  return `/api/admin/codes/export?pwd=${encodeURIComponent(getAdminPwd())}`;
}
