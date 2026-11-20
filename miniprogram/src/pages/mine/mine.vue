<template>
  <view class="page">
    <view class="profile-card">
      <view class="name">{{ user?.nickname || "备考战友" }}</view>
      <view class="quota-row">
        <view class="quota-item">
          <view class="q-num">{{ user?.free_quota ?? 0 }}</view>
          <view class="q-label">剩余免费体验</view>
        </view>
        <view class="quota-item">
          <view class="q-num">{{ user?.paid_quota ?? 0 }}</view>
          <view class="q-label">剩余按次包</view>
        </view>
        <view class="quota-item">
          <view class="q-num">{{ user?.is_vip ? "生效中" : "未开通" }}</view>
          <view class="q-label">上岸月卡</view>
        </view>
      </view>
    </view>

    <!-- 兑换码核销卡片（安卓 + iOS 100% 合规过审收款） -->
    <view class="card" style="margin-bottom: 20rpx;">
      <view class="card-h">🎁 兑换码激活额度 / 月卡</view>
      <view class="redeem-desc">在自习室前台或小红书店铺购买激活码后，在此输入即可秒到账</view>
      <view class="redeem-row">
        <input
          v-model="redeemInput"
          class="redeem-input"
          placeholder="请输入兑换码（如 RP-XXXX-XXXX）"
        />
        <button class="redeem-btn" size="mini" :loading="redeeming" @click="handleRedeem">
          立即兑换
        </button>
      </view>
    </view>

    <view class="card">
      <view class="card-h">精批套餐参考</view>
      <view class="plan" @click="buyTip('冲刺体验包 9.9元/5次')">
        <view>
          <view class="plan-name">冲刺体验包（5 次精批）</view>
          <view class="plan-desc">申论大小作文 / 考研英语通用，永久有效</view>
        </view>
        <view class="price">¥9.9</view>
      </view>
      <view class="plan highlight" @click="buyTip('上岸畅批月卡 29.9元/月')">
        <view>
          <view class="plan-name">上岸畅批月卡（30 天无限次）</view>
          <view class="plan-desc">含专属个人薄弱项诊断与同思路升格范文</view>
        </view>
        <view class="price">¥29.9</view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { request } from "@/utils/request";

const user = ref<any>(null);
const redeemInput = ref("");
const redeeming = ref(false);

async function loadUser() {
  user.value = await request({ url: "/api/auth/me" });
}

onShow(loadUser);

async function handleRedeem() {
  const code = redeemInput.value.trim();
  if (!code) {
    uni.showToast({ title: "请先输入兑换码", icon: "none" });
    return;
  }
  redeeming.value = true;
  try {
    const res = await request<{ message: string; user: any }>({
      url: "/api/auth/redeem",
      method: "POST",
      data: { code },
    });
    user.value = res.user;
    redeemInput.value = "";
    uni.showToast({ title: res.message, icon: "success" });
  } finally {
    redeeming.value = false;
  }
}

function buyTip(planName: string) {
  uni.showModal({
    title: "获取激活码",
    content: `如需开通【${planName}】，请联系自习室前台或小红书客服获取兑换码，在上方输入框粘贴即可立即到账。`,
    showCancel: false,
  });
}
</script>

<style scoped>
.page {
  padding: 20rpx 24rpx;
}
.profile-card {
  background: linear-gradient(135deg, #1e3a8a, #2563eb);
  color: #fff;
  border-radius: 18rpx;
  padding: 32rpx 28rpx;
  margin-bottom: 24rpx;
}
.name {
  font-size: 36rpx;
  font-weight: 700;
  margin-bottom: 24rpx;
}
.quota-row {
  display: flex;
  justify-content: space-between;
  text-align: center;
}
.quota-item {
  flex: 1;
}
.q-num {
  font-size: 38rpx;
  font-weight: 800;
}
.q-label {
  font-size: 22rpx;
  opacity: 0.85;
  margin-top: 6rpx;
}
.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
}
.card-h {
  font-size: 28rpx;
  font-weight: 700;
  margin-bottom: 14rpx;
}
.redeem-desc {
  font-size: 23rpx;
  color: #6b7280;
  margin-bottom: 16rpx;
}
.redeem-row {
  display: flex;
  gap: 14rpx;
  align-items: center;
}
.redeem-input {
  flex: 1;
  background: #f9fafb;
  border: 1rpx solid #d1d5db;
  border-radius: 10rpx;
  padding: 14rpx 18rpx;
  font-size: 26rpx;
}
.redeem-btn {
  background: #2563eb;
  color: #fff;
  margin: 0;
  padding: 0 24rpx;
  line-height: 68rpx;
  height: 68rpx;
  border-radius: 10rpx;
}
.plan {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 22rpx;
  border: 2rpx solid #e5e7eb;
  border-radius: 14rpx;
  margin-bottom: 16rpx;
}
.plan.highlight {
  border-color: #2563eb;
  background: #eff6ff;
}
.plan-name {
  font-size: 28rpx;
  font-weight: 700;
}
.plan-desc {
  font-size: 22rpx;
  color: #6b7280;
  margin-top: 6rpx;
}
.price {
  font-size: 36rpx;
  font-weight: 800;
  color: #dc2626;
}
</style>
