<template>
  <div
    v-if="userState.accountModalOpen && userState.user"
    class="modal-mask"
    @click.self="close"
    @keydown.esc="close"
    tabindex="-1"
  >
    <div class="modal-card paper-card">
      <!-- 独立的顶部标题栏，彻底消除关闭按钮错位 -->
      <div class="modal-topbar">
        <span class="modal-title">我的账号与额度</span>
        <button class="close-btn" type="button" @click="close" aria-label="关闭">×</button>
      </div>

      <!-- 暖宣纸「自习室通行证」风格账号卡 -->
      <div class="pass-card">
        <img src="/favicon.svg" alt="" class="pass-watermark" aria-hidden="true" />

        <div class="pass-head">
          <div class="pass-identity">
            <div v-if="!editingName" class="name-row">
              <span class="profile-name">{{ userState.user.nickname }}</span>
              <button type="button" class="edit-name-btn" @click="startEditName">修改昵称</button>
            </div>
            <div v-else class="name-edit-row">
              <input
                v-model="nicknameDraft"
                type="text"
                class="name-input"
                maxlength="24"
                placeholder="输入新昵称"
                @keyup.enter="saveNickname"
              />
              <button type="button" class="btn btn-primary btn-sm" :disabled="savingName" @click="saveNickname">
                保存
              </button>
              <button type="button" class="btn btn-ghost btn-sm" @click="editingName = false">取消</button>
            </div>
            <div class="profile-account">
              账号：{{ userState.user.username || `ID #${userState.user.user_id}` }}
            </div>
          </div>

          <button type="button" class="btn-logout" @click="logout">退出登录</button>
        </div>

        <div class="quota-strip">
          <div class="quota-cell">
            <div class="q-num">{{ userState.user.free_quota }}</div>
            <div class="q-label">免费体验次数</div>
          </div>
          <div class="quota-divider"></div>
          <div class="quota-cell">
            <div class="q-num">{{ userState.user.paid_quota }}</div>
            <div class="q-label">按次包剩余</div>
          </div>
          <div class="quota-divider"></div>
          <div class="quota-cell">
            <div :class="['q-num', userState.user.is_vip ? 'vip-active' : 'vip-idle']">
              {{ userState.user.is_vip ? "生效中" : "未开通" }}
            </div>
            <div class="q-label">{{ vipExpireText || "上岸畅批月卡" }}</div>
          </div>
        </div>
      </div>

      <!-- 兑换码核销 -->
      <div class="section">
        <div class="section-h">兑换码激活额度 / 月卡</div>
        <p class="section-desc">
          内测期可向自习室前台免费领取体验码，或凭购买的激活码在此输入秒到账（支持叠加）。
        </p>
        <div class="redeem-row">
          <input
            v-model="redeemCode"
            type="text"
            class="redeem-input"
            placeholder="请输入兑换码，例如 VIP-XXXX-XXXX"
            @keyup.enter="handleRedeem"
          />
          <button class="btn btn-primary" :disabled="redeeming" @click="handleRedeem">
            {{ redeeming ? "核销中..." : "立即兑换" }}
          </button>
        </div>
      </div>

      <!-- 精批套餐参考 -->
      <div class="section">
        <div class="section-h">精批套餐参考</div>
        <div class="plan-grid">
          <div class="plan-card">
            <div class="plan-head">
              <span class="plan-title">冲刺体验包</span>
              <span class="plan-price">¥9.9</span>
            </div>
            <div class="plan-sub">5 次全题型精批 · 永久有效</div>
            <ul class="plan-list">
              <li>申论大小作文 / 考研英语通用</li>
              <li>逐句红笔批注与采分点溯源</li>
              <li>保留原思路生成高分升格范文</li>
            </ul>
          </div>

          <div class="plan-card featured">
            <div class="plan-badge">考前推荐</div>
            <div class="plan-head">
              <span class="plan-title">上岸畅批月卡</span>
              <span class="plan-price">¥29.9</span>
            </div>
            <div class="plan-sub">30 天不限次精批 · 二刷重写无压力</div>
            <ul class="plan-list">
              <li>30 天不限次提交真题与自由批改</li>
              <li>不限次拍照识字（单次最多 4 页）</li>
              <li>高频薄弱项诊断与打卡图导出</li>
            </ul>
          </div>
        </div>
        <div class="buy-note">
          获取激活码请联系自习室前台或小红书「知行岛·自习室」客服，核销后立即生效。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { apiRequest } from "../api/client";
import { logout, showToast, userState } from "../stores/auth";
import type { UserInfo } from "../types";

const redeemCode = ref("");
const redeeming = ref(false);

const editingName = ref(false);
const nicknameDraft = ref("");
const savingName = ref(false);

const vipExpireText = computed(() => {
  const dt = userState.user?.vip_expire_at;
  if (!dt || !userState.user?.is_vip) return "";
  return `至 ${dt.slice(0, 10)} 到期`;
});

function close() {
  editingName.value = false;
  userState.accountModalOpen = false;
}

function startEditName() {
  nicknameDraft.value = userState.user?.nickname || "";
  editingName.value = true;
}

async function saveNickname() {
  const next = nicknameDraft.value.trim();
  if (!next) {
    showToast("昵称不能为空", "warn");
    return;
  }
  savingName.value = true;
  try {
    const updated = await apiRequest<UserInfo>("/api/auth/profile", {
      method: "PATCH",
      body: { nickname: next },
    });
    userState.user = updated;
    editingName.value = false;
    showToast("昵称已更新", "success");
  } catch (err: any) {
    showToast(err?.message || "昵称修改失败", "error");
  } finally {
    savingName.value = false;
  }
}

async function handleRedeem() {
  const code = redeemCode.value.trim();
  if (!code) {
    showToast("请先输入兑换码", "warn");
    return;
  }
  redeeming.value = true;
  try {
    const res = await apiRequest<{ message: string; user: UserInfo }>("/api/auth/redeem", {
      method: "POST",
      body: { code },
    });
    userState.user = res.user;
    redeemCode.value = "";
    showToast(res.message, "success");
  } catch (err: any) {
    showToast(err?.message || "兑换失败，请核对兑换码", "error");
  } finally {
    redeeming.value = false;
  }
}
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(20, 24, 22, 0.45);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal-card {
  width: 100%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
  padding: 20px 26px 24px;
  box-shadow: var(--shadow-lg);
}

.modal-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.modal-title {
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 700;
  color: var(--ink-primary);
}

.close-btn {
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--ink-muted);
  font-size: 21px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: var(--bg-hover);
  color: var(--ink-primary);
}

/* 暖宣纸自习室通行证 */
.pass-card {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-md);
  border: 1px solid #e1dacb;
  background: linear-gradient(125deg, #fbf9f3 0%, #f1ece0 100%);
  padding: 20px 22px 18px;
  margin-bottom: 22px;
}

.pass-watermark {
  position: absolute;
  right: 18px;
  top: 12px;
  height: 44px;
  opacity: 0.06;
  pointer-events: none;
}

.pass-head {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 18px;
}

.name-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.profile-name {
  font-family: var(--font-serif);
  font-size: 21px;
  font-weight: 700;
  color: var(--ink-primary);
}

.edit-name-btn {
  border: 0;
  background: transparent;
  padding: 0;
  font-size: 12px;
  color: var(--ink-muted);
}

.edit-name-btn:hover {
  color: var(--ink-primary);
  text-decoration: underline;
}

.name-edit-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.name-input {
  width: 150px;
  padding: 5px 8px;
  border-radius: 6px;
  border: 1px solid #d5cebf;
  background: #fff;
  font-size: 13px;
  outline: none;
}

.name-input:focus {
  border-color: var(--brand);
}

.profile-account {
  font-size: 12.5px;
  color: var(--ink-muted);
  margin-top: 3px;
}

.btn-logout {
  border: 1px solid #dad3c5;
  background: rgba(255, 255, 255, 0.72);
  color: var(--ink-secondary);
  font-size: 12px;
  padding: 5px 12px;
  border-radius: 99px;
  transition: all 0.14s ease;
}

.btn-logout:hover {
  background: #fff;
  color: var(--red-pen);
  border-color: var(--red-pen-border);
}

.quota-strip {
  position: relative;
  display: flex;
  align-items: center;
  padding-top: 14px;
  border-top: 1px solid rgba(26, 28, 27, 0.08);
}

.quota-cell {
  flex: 1;
  text-align: center;
}

.quota-divider {
  width: 1px;
  height: 28px;
  background: rgba(26, 28, 27, 0.1);
}

.q-num {
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 700;
  color: var(--ink-primary);
  line-height: 1.2;
}

.q-num.vip-active {
  color: var(--red-pen);
  font-size: 20px;
}

.q-num.vip-idle {
  color: var(--ink-muted);
  font-size: 18px;
  font-weight: 600;
}

.q-label {
  font-size: 12px;
  color: var(--ink-muted);
  margin-top: 4px;
}

.section {
  margin-bottom: 20px;
}

.section:last-child {
  margin-bottom: 0;
}

.section-h {
  font-size: 14.5px;
  font-weight: 700;
  color: var(--ink-primary);
  margin-bottom: 5px;
}

.section-desc {
  margin: 0 0 11px;
  font-size: 12.5px;
  color: var(--ink-muted);
}

.redeem-row {
  display: flex;
  gap: 10px;
}

.redeem-input {
  flex: 1;
  padding: 9px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-strong);
  background: var(--bg-subtle);
  outline: none;
  text-transform: uppercase;
}

.redeem-input:focus {
  border-color: var(--brand);
  background: #fff;
}

.plan-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.plan-card {
  position: relative;
  border: 1px solid #e4dfd3;
  border-radius: var(--radius-md);
  padding: 16px 17px;
  background: #faf8f3;
}

.plan-card.featured {
  border-color: var(--brand);
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(26, 28, 27, 0.05);
}

.plan-badge {
  position: absolute;
  top: -10px;
  right: 12px;
  background: var(--red-pen);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 99px;
}

.plan-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.plan-title {
  font-weight: 700;
  font-size: 15px;
  color: var(--ink-primary);
}

.plan-price {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 900;
  color: var(--red-pen);
}

.plan-sub {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 4px 0 10px;
}

.plan-list {
  margin: 0;
  padding-left: 16px;
  font-size: 12.5px;
  color: var(--ink-secondary);
  line-height: 1.75;
}

.buy-note {
  margin-top: 12px;
  font-size: 12px;
  color: var(--ink-muted);
  text-align: center;
}

@media (max-width: 600px) {
  .plan-grid {
    grid-template-columns: 1fr;
  }
}
</style>
