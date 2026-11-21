const TOKEN_KEY = "zxd_pc_token";

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

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token: string): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let onUnauthorizedHandler: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorizedHandler = fn;
}

export async function apiRequest<T = any>(
  url: string,
  options: {
    method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    body?: any;
    skipAuthRedirect?: boolean;
  } = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let resp: Response;
  try {
    resp = await fetch(apiUrl(url), {
      method: options.method || "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "无法连接到批改服务，请检查网络或确认后端已启动");
  }

  const contentType = resp.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await resp.json().catch(() => ({}))
    : await resp.text().catch(() => "");

  if (!resp.ok) {
    if (resp.status === 401 && !options.skipAuthRedirect) {
      setToken("");
      onUnauthorizedHandler?.();
    }
    const detail =
      typeof data === "object" && data && "detail" in data
        ? String((data as any).detail)
        : `请求失败 (${resp.status})`;
    throw new ApiError(resp.status, detail);
  }

  return data as T;
}

async function compressImageForOcr(file: File): Promise<File> {
  // 对超过 600KB 的手机原图自动缩放到长边 1800px 并转为高清晰度 JPEG，自动摆正 EXIF 方向且提速 3 倍
  if (file.size <= 600 * 1024 && (file.type === "image/jpeg" || file.type === "image/png")) {
    return file;
  }
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      const maxSide = 1800;
      let { width, height } = img;
      if (width > maxSide || height > maxSide) {
        if (width >= height) {
          height = Math.round((height * maxSide) / width);
          width = maxSide;
        } else {
          width = Math.round((width * maxSide) / height);
          height = maxSide;
        }
      }
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        resolve(file);
        return;
      }
      ctx.fillStyle = "#FFFFFF";
      ctx.fillRect(0, 0, width, height);
      ctx.drawImage(img, 0, 0, width, height);
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            resolve(file);
            return;
          }
          const baseName = (file.name || "handwriting").replace(/\.[^.]+$/, "");
          resolve(new File([blob], `${baseName}.jpg`, { type: "image/jpeg" }));
        },
        "image/jpeg",
        0.86
      );
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(file);
    };
    img.src = url;
  });
}

export async function uploadOcrImage(
  file: File,
  examType: string
): Promise<{
  image_path: string;
  recognized_text: string;
  word_count: number;
  mock_mode: boolean;
}> {
  const token = getToken();
  const optimizedFile = await compressImageForOcr(file);
  const form = new FormData();
  form.append("file", optimizedFile, optimizedFile.name || "handwriting.jpg");

  let resp: Response;
  try {
    resp = await fetch(apiUrl(`/api/grading/ocr?exam_type=${encodeURIComponent(examType)}`), {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
  } catch {
    throw new ApiError(0, "图片上传失败，请检查网络连接");
  }

  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    if (resp.status === 401) {
      setToken("");
      onUnauthorizedHandler?.();
    }
    throw new ApiError(resp.status, data?.detail || `手写识别失败 (${resp.status})`);
  }
  return data;
}
