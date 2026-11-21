import { reactive, ref } from "vue";
import { apiRequest, getToken, setToken, setUnauthorizedHandler } from "../api/client";
import type { UserInfo } from "../types";

export const userState = reactive<{
  user: UserInfo | null;
  loading: boolean;
  authModalOpen: boolean;
  authModalMode: "login" | "register";
  accountModalOpen: boolean;
}>({
  user: null,
  loading: false,
  authModalOpen: false,
  authModalMode: "login",
  accountModalOpen: false,
});

export interface ToastItem {
  id: number;
  type: "info" | "success" | "error" | "warn";
  text: string;
}

export const toasts = ref<ToastItem[]>([]);
let toastSeq = 1;

export function showToast(text: string, type: ToastItem["type"] = "info", duration = 3200) {
  const id = toastSeq++;
  toasts.value.push({ id, type, text });
  window.setTimeout(() => {
    toasts.value = toasts.value.filter((t) => t.id !== id);
  }, duration);
}

setUnauthorizedHandler(() => {
  userState.user = null;
  userState.authModalMode = "login";
  userState.authModalOpen = true;
});

export function openAuthModal(mode: "login" | "register" = "login") {
  userState.authModalMode = mode;
  userState.authModalOpen = true;
}

export function openAccountModal() {
  if (!userState.user) {
    openAuthModal("login");
    return;
  }
  userState.accountModalOpen = true;
}

export async function refreshUser(silent = true): Promise<UserInfo | null> {
  if (!getToken()) {
    userState.user = null;
    return null;
  }
  userState.loading = true;
  try {
    const me = await apiRequest<UserInfo>("/api/auth/me", { skipAuthRedirect: silent });
    userState.user = me;
    return me;
  } catch {
    if (!silent) {
      userState.user = null;
    }
    return null;
  } finally {
    userState.loading = false;
  }
}

export function applyLoginSuccess(token: string, user: UserInfo) {
  setToken(token);
  userState.user = user;
  userState.authModalOpen = false;
}

export function logout() {
  setToken("");
  userState.user = null;
  userState.accountModalOpen = false;
  showToast("已退出登录", "info");
}
