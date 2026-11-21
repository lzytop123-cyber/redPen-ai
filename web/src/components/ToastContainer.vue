<template>
  <div class="toast-stack no-print">
    <transition-group name="toast">
      <div v-for="t in toasts" :key="t.id" :class="['toast-item', t.type]">
        <span class="toast-dot"></span>
        <span>{{ t.text }}</span>
      </div>
    </transition-group>
  </div>
</template>

<script setup lang="ts">
import { toasts } from "../stores/auth";
</script>

<style scoped>
.toast-stack {
  position: fixed;
  top: 74px;
  right: 24px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.toast-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: var(--radius-md);
  background: #1a202c;
  color: #fff;
  font-size: 13.5px;
  box-shadow: var(--shadow-md);
  max-width: 380px;
}

.toast-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #60a5fa;
  flex-shrink: 0;
}

.toast-item.success .toast-dot {
  background: #4ade80;
}

.toast-item.error {
  background: #991b1b;
}

.toast-item.error .toast-dot {
  background: #fca5a5;
}

.toast-item.warn .toast-dot {
  background: #fbbf24;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
