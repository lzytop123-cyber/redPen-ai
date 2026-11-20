<template>
  <!-- 登录页 -->
  <div v-if="!loggedIn" class="login-page">
    <div class="login-card">
      <div class="login-logo">知行岛申论精批</div>
      <div class="login-sub">商业运营管理后台</div>
      <input
        v-model="pwdInput"
        type="password"
        class="input"
        style="width:100%;margin-top:20px;padding:12px;"
        placeholder="请输入管理员密码（本地默认 admin123）"
        @keyup.enter="handleLogin"
      />
      <div v-if="loginErr" style="color:#dc2626;font-size:13px;margin-top:8px;">{{ loginErr }}</div>
      <button class="btn btn-primary" style="width:100%;justify-content:center;margin-top:16px;padding:11px;" @click="handleLogin">
        登录运营后台
      </button>
    </div>
  </div>

  <!-- 主后台框架：深蓝侧边栏 + 内容区 -->
  <div v-else class="layout">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-main">知行岛申论精批</div>
        <div class="brand-sub">Admin Console</div>
      </div>
      <nav class="nav">
        <button
          v-for="m in menus"
          :key="m.key"
          :class="['nav-item', activeMenu === m.key ? 'active' : '']"
          @click="activeMenu = m.key"
        >
          <span>{{ m.icon }}</span>
          <span>{{ m.label }}</span>
        </button>
      </nav>
      <div class="side-foot">
        <button class="nav-item" style="width:100%;" @click="handleLogout">🚪 退出登录</button>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div style="font-size:16px;font-weight:700;">{{ currentMenuLabel }}</div>
        <div style="font-size:12px;color:#64748b;">知行岛教育科技 · 线上运营中心</div>
      </header>
      <section class="content">
        <DashboardView v-if="activeMenu === 'dashboard'" />
        <TasksView v-else-if="activeMenu === 'tasks'" />
        <QuestionsView v-else-if="activeMenu === 'questions'" />
        <UsersView v-else-if="activeMenu === 'users'" />
        <CodesView v-else-if="activeMenu === 'codes'" />
        <SystemView v-else-if="activeMenu === 'system'" />
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { adminFetch, clearAdminPwd, getAdminPwd, setAdminPwd } from "./api";
import DashboardView from "./views/DashboardView.vue";
import TasksView from "./views/TasksView.vue";
import QuestionsView from "./views/QuestionsView.vue";
import UsersView from "./views/UsersView.vue";
import CodesView from "./views/CodesView.vue";
import SystemView from "./views/SystemView.vue";

const menus = [
  { key: "dashboard", icon: "📊", label: "运营总览" },
  { key: "tasks", icon: "📝", label: "批改质检" },
  { key: "questions", icon: "📚", label: "真题与采分点" },
  { key: "users", icon: "👥", label: "用户管理" },
  { key: "codes", icon: "🎁", label: "兑换码卡密" },
  { key: "system", icon: "⚙️", label: "系统与模型" },
];

const loggedIn = ref(false);
const pwdInput = ref("");
const loginErr = ref("");
const activeMenu = ref("dashboard");

const currentMenuLabel = computed(() => menus.find((m) => m.key === activeMenu.value)?.label || "");

async function handleLogin() {
  loginErr.value = "";
  setAdminPwd(pwdInput.value.trim());
  try {
    await adminFetch("/api/admin/stats");
    loggedIn.value = true;
  } catch (e: any) {
    clearAdminPwd();
    loginErr.value = e.message || "密码错误";
  }
}

function handleLogout() {
  clearAdminPwd();
  loggedIn.value = false;
  pwdInput.value = "";
}

onMounted(async () => {
  if (getAdminPwd()) {
    try {
      await adminFetch("/api/admin/stats");
      loggedIn.value = true;
    } catch {
      clearAdminPwd();
    }
  }
});
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f172a, #1e3a8a);
}
.login-card {
  width: 380px;
  max-width: 92vw;
  background: #fff;
  border-radius: 16px;
  padding: 36px 32px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.25);
  text-align: center;
}
.login-logo { font-size: 24px; font-weight: 800; color: #1e3a8a; }
.login-sub { font-size: 13px; color: #64748b; margin-top: 6px; }
.layout {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 224px;
  background: #0f172a;
  color: #cbd5e1;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.brand {
  padding: 22px 20px;
  border-bottom: 1px solid #1e293b;
}
.brand-main { font-size: 17px; font-weight: 800; color: #fff; }
.brand-sub { font-size: 11px; color: #64748b; margin-top: 4px; }
.nav {
  flex: 1;
  padding: 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 14px;
  border-radius: 10px;
  border: 0;
  background: transparent;
  color: #cbd5e1;
  font-size: 14px;
  cursor: pointer;
  text-align: left;
  transition: all 0.15s;
}
.nav-item:hover { background: #1e293b; color: #fff; }
.nav-item.active { background: #2563eb; color: #fff; font-weight: 600; }
.side-foot {
  padding: 12px;
  border-top: 1px solid #1e293b;
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.topbar {
  height: 58px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.content {
  flex: 1;
  padding: 20px 24px 48px;
  overflow-y: auto;
}
</style>
