<template>
  <div v-if="userState.authModalOpen" class="modal-mask" @click.self="close">
    <div class="modal-card paper-card">
      <button class="close-btn" @click="close" aria-label="关闭">×</button>

      <div class="modal-head">
        <img src="/logo.jpg" alt="知行岛·自习室" class="modal-logo" />
        <h2>{{ mode === "login" ? "登录精批工作台" : "注册备考账号" }}</h2>
        <p v-if="mode === 'register'">新账号立即赠送 <strong>3 次</strong> AI 红笔精批体验额度</p>
        <p v-else>同步你的历史精批报告、薄弱项画像与月卡权益</p>
      </div>

      <div class="mode-tabs">
        <button
          type="button"
          :class="['mode-tab', mode === 'login' ? 'active' : '']"
          @click="switchMode('login')"
        >
          账号登录
        </button>
        <button
          type="button"
          :class="['mode-tab', mode === 'register' ? 'active' : '']"
          @click="switchMode('register')"
        >
          新用户注册
        </button>
      </div>

      <form class="auth-form" @submit.prevent="handleSubmit">
        <label class="field">
          <span>手机号 / 账号</span>
          <input
            v-model="username"
            type="text"
            placeholder="请输入手机号或自定义账号（3~32位）"
            autocomplete="username"
            required
          />
        </label>

        <label class="field">
          <span>登录密码</span>
          <input
            v-model="password"
            type="password"
            placeholder="请输入 6 位以上密码"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
            required
          />
        </label>

        <label v-if="mode === 'register'" class="field">
          <span>昵称（选填）</span>
          <input
            v-model="nickname"
            type="text"
            placeholder="如：2026国考必胜"
            maxlength="32"
          />
        </label>

        <div v-if="errorMsg" class="form-error">{{ errorMsg }}</div>

        <button class="btn btn-primary btn-lg submit-full" type="submit" :disabled="submitting">
          {{ submitting ? "提交中..." : mode === "login" ? "立即登录" : "注册并领取 3 次精批" }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { apiRequest } from "../api/client";
import { applyLoginSuccess, showToast, userState } from "../stores/auth";
import type { UserInfo } from "../types";

const username = ref("");
const password = ref("");
const nickname = ref("");
const errorMsg = ref("");
const submitting = ref(false);

const mode = computed(() => userState.authModalMode);

watch(
  () => userState.authModalOpen,
  (open) => {
    if (open) {
      errorMsg.value = "";
    }
  }
);

function switchMode(next: "login" | "register") {
  userState.authModalMode = next;
  errorMsg.value = "";
}

function close() {
  userState.authModalOpen = false;
}

async function handleSubmit() {
  errorMsg.value = "";
  const u = username.value.trim();
  if (u.length < 3) {
    errorMsg.value = "账号至少需要 3 个字符";
    return;
  }
  if (password.value.length < 6) {
    errorMsg.value = "密码至少需要 6 位";
    return;
  }

  submitting.value = true;
  try {
    const endpoint = mode.value === "login" ? "/api/auth/login" : "/api/auth/register";
    const payload =
      mode.value === "login"
        ? { username: u, password: password.value }
        : { username: u, password: password.value, nickname: nickname.value.trim() || undefined };

    const res = await apiRequest<{ token: string; user: UserInfo }>(endpoint, {
      method: "POST",
      body: payload,
      skipAuthRedirect: true,
    });
    applyLoginSuccess(res.token, res.user);
    password.value = "";
    showToast(
      mode.value === "register" ? "注册成功！已赠送 3 次精批额度" : `欢迎回来，${res.user.nickname}`,
      "success"
    );
  } catch (err: any) {
    errorMsg.value = err?.message || "操作失败，请稍后重试";
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(20, 24, 31, 0.48);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal-card {
  position: relative;
  width: 100%;
  max-width: 420px;
  padding: 32px 30px 28px;
  box-shadow: var(--shadow-lg);
}

.close-btn {
  position: absolute;
  top: 14px;
  right: 16px;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--ink-muted);
  font-size: 22px;
  line-height: 1;
}

.close-btn:hover {
  background: var(--bg-hover);
  color: var(--ink-primary);
}

.modal-head {
  text-align: center;
  margin-bottom: 20px;
}

.modal-logo {
  display: block;
  height: 76px;
  width: auto;
  margin: 0 auto 8px;
  mix-blend-mode: multiply;
}

.modal-head h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 21px;
  color: var(--ink-primary);
}

.modal-head p {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--ink-muted);
}

.modal-head strong {
  color: var(--red-pen);
}

.mode-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 4px;
  border-radius: var(--radius-md);
  background: var(--bg-inset);
  margin-bottom: 18px;
}

.mode-tab {
  border: none;
  background: transparent;
  padding: 8px 0;
  border-radius: 7px;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--ink-secondary);
}

.mode-tab.active {
  background: var(--bg-surface);
  color: var(--ink-primary);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field span {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink-secondary);
}

.field input {
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-strong);
  background: var(--bg-subtle);
  color: var(--ink-primary);
  outline: none;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.field input:focus {
  border-color: var(--brand);
  background: #fff;
}

.form-error {
  padding: 9px 12px;
  border-radius: var(--radius-sm);
  background: var(--red-pen-soft);
  border: 1px solid var(--red-pen-border);
  color: var(--red-pen);
  font-size: 13px;
}

.submit-full {
  width: 100%;
  margin-top: 4px;
}
</style>
