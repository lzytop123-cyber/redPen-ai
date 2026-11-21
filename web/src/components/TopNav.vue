<template>
  <header class="top-nav no-print" @keydown.esc="dismissMenu" @focusout="closeWhenLeaving">
    <div class="nav-inner">
      <button class="brand" @click="navigate('library')">
        <img src="/favicon.svg" alt="" class="brand-mark" />
        <span class="brand-name">知行岛·自习室</span>
      </button>

      <nav id="site-navigation" class="nav-links" :class="{ 'menu-open': menuOpen }" aria-label="主要导航">
        <button
          :class="['nav-item', activePage === 'library' ? 'active' : '']"
          @click="navigate('library')"
        >
          真题库
        </button>
        <button
          :class="['nav-item', activePage === 'custom' ? 'active' : '']"
          @click="navigate('custom')"
        >
          自由批改
        </button>
        <button
          :class="['nav-item', activePage === 'history' ? 'active' : '']"
          @click="navigate('history')"
        >
          批改记录
        </button>
      </nav>

      <div class="nav-right">
        <button ref="menuButton" class="menu-button btn btn-ghost btn-sm" :aria-expanded="menuOpen"
          aria-controls="site-navigation" @click="menuOpen = !menuOpen">菜单</button>
        <template v-if="userState.user">
          <button class="quota-pill" @click="menuOpen = false; openAccountModal()" title="点击兑换额度或查看套餐">
            <span v-if="userState.user.is_vip" class="vip-tag">月卡畅批</span>
            <span v-else class="quota-count">
              剩余 <strong>{{ userState.user.free_quota + userState.user.paid_quota }}</strong> 次
            </span>
            <span class="pill-divider"></span>
            <span class="user-name">{{ userState.user.nickname }}</span>
          </button>
          <button class="btn btn-outline btn-sm" @click="menuOpen = false; openAccountModal()">兑换码</button>
        </template>
        <template v-else>
          <button class="btn btn-ghost btn-sm" @click="menuOpen = false; openAuthModal('login')">登录</button>
          <button class="btn btn-primary btn-sm" @click="menuOpen = false; openAuthModal('register')">
            注册
          </button>
        </template>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { openAccountModal, openAuthModal, userState } from "../stores/auth";

defineProps<{
  activePage: string;
}>();

const emit = defineEmits<{
  (e: "navigate", page: "library" | "custom" | "history"): void;
}>();
const menuOpen = ref(false);
const menuButton = ref<HTMLButtonElement | null>(null);

function navigate(page: "library" | "custom" | "history") {
  menuOpen.value = false;
  emit("navigate", page);
}

function dismissMenu() {
  if (!menuOpen.value) return;
  menuOpen.value = false;
  menuButton.value?.focus();
}

function closeWhenLeaving(event: FocusEvent) {
  if (!(event.currentTarget as HTMLElement).contains(event.relatedTarget as Node | null)) {
    menuOpen.value = false;
  }
}
</script>

<style scoped>
.top-nav {
  position: sticky;
  top: 0;
  z-index: 40;
  height: var(--nav-height);
  background: rgba(255, 255, 252, 0.96);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--border-subtle);
}

.nav-inner {
  max-width: var(--catalog-max);
  height: 100%;
  margin: 0 auto;
  padding: 0 var(--catalog-gutter);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.brand {
  background: transparent;
  border: 0;
  padding: 0;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.brand-mark {
  height: 28px;
  width: auto;
  display: block;
}

.brand-name {
  font-family: var(--font-serif);
  font-size: 17.5px;
  font-weight: 700;
  color: var(--ink-primary);
  letter-spacing: 0.4px;
}



.nav-links {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border-radius: 10px;
  background: rgba(23, 28, 26, 0.035);
}

.nav-item {
  border: none;
  background: transparent;
  padding: 6px 15px;
  border-radius: 7px;
  color: var(--ink-secondary);
  font-size: 13.5px;
  font-weight: 500;
  transition: all 0.16s ease;
}

.nav-item:hover {
  color: var(--ink-primary);
}

.nav-item.active {
  background: var(--bg-surface);
  color: var(--brand);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.quota-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px;
  border-radius: 99px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-subtle);
  color: var(--ink-primary);
  font-size: 13px;
  transition: all 0.15s ease;
}

.quota-pill:hover {
  border-color: var(--brand-border);
  background: var(--brand-soft);
}

.vip-tag {
  background: linear-gradient(135deg, #b45309, #d97706);
  color: #fff;
  font-size: 11.5px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 99px;
}

.quota-count {
  color: var(--ink-secondary);
}

.quota-count strong {
  color: var(--brand);
  font-weight: 700;
}

.pill-divider {
  width: 1px;
  height: 12px;
  background: var(--border-strong);
}

.user-name {
  font-weight: 600;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.menu-button { display: none; }
@media (max-width: 760px) {
  .nav-inner { padding: 0 var(--catalog-gutter); gap: 8px; }
  .brand { gap: 6px; }
  .brand-name { font-size: 16px; }
  .brand-mark { height: 23px; }
  .nav-right { gap: 2px; }
  .nav-right .btn, .quota-pill { min-height: 40px; padding-inline: 8px; }
  .menu-button { display: inline-flex; }
  .nav-links { display: none; position: absolute; top: 100%; right: 12px; padding: 6px; min-width: 158px; flex-direction: column; align-items: stretch; background: var(--bg-surface); border: 1px solid var(--border-strong); box-shadow: var(--shadow-md); }
  .nav-links.menu-open { display: flex; }
  .nav-item { min-height: 41px; text-align: left; }
  .nav-item.active { background: var(--brand-soft); box-shadow: none; }
  .quota-pill { border: 0; border-radius: 5px; }
  .nav-right .btn-outline, .pill-divider, .user-name { display: none; }
}
@media (max-width: 360px) {
  .brand-mark { height: 17px; }
  .brand-name { font-size: 14px; }
  .nav-inner { gap: 4px; }
  .nav-right .btn { padding-inline: 6px; }
}
</style>
