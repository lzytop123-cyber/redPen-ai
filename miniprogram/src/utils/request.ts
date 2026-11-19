// 后端 API 地址（本地调试连本机 FastAPI，上线替换为 HTTPS 备案域名）
export const API_BASE_URL = "http://127.0.0.1:8000";

const TOKEN_KEY = "ai_grading_token";

export function getToken(): string {
  return uni.getStorageSync(TOKEN_KEY) || "";
}

export function setToken(token: string) {
  uni.setStorageSync(TOKEN_KEY, token);
}

export async function ensureLogin(): Promise<string> {
  const cached = getToken();
  if (cached) return cached;

  let code = "h5_dev_code";
  // #ifdef MP-WEIXIN
  const loginRes = await new Promise<UniApp.LoginRes>((resolve, reject) => {
    uni.login({ provider: "weixin", success: resolve, fail: reject });
  });
  code = loginRes.code || code;
  // #endif

  const res = await request<{ token: string }>({
    url: "/api/auth/wx-login",
    method: "POST",
    data: { code },
  });
  setToken(res.token);
  return res.token;
}

export function request<T = any>(options: {
  url: string;
  method?: "GET" | "POST" | "PUT" | "DELETE";
  data?: any;
}): Promise<T> {
  const token = getToken();
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE_URL}${options.url}`,
      method: options.method || "GET",
      data: options.data,
      header: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data as T);
        } else {
          const detail = (res.data as any)?.detail || `请求失败 (${res.statusCode})`;
          uni.showToast({ title: String(detail), icon: "none" });
          reject(new Error(String(detail)));
        }
      },
      fail: (err) => {
        uni.showToast({ title: "网络连接失败，请检查后端服务", icon: "none" });
        reject(err);
      },
    });
  });
}

export function uploadHandwriting(filePath: string, examType: string): Promise<{
  image_path: string;
  recognized_text: string;
  word_count: number;
  mock_mode: boolean;
}> {
  const token = getToken();
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${API_BASE_URL}/api/grading/ocr?exam_type=${encodeURIComponent(examType)}`,
      filePath,
      name: "file",
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(JSON.parse(res.data));
        } else {
          reject(new Error(`OCR 失败 (${res.statusCode})`));
        }
      },
      fail: reject,
    });
  });
}
