<template>
  <view class="page">
    <view class="profile-card">
      <view class="name">{{ user?.nickname || "我的账户" }}</view>
      <view class="quota-row">
        <view class="quota-item">
          <view class="q-num">{{ user?.free_quota ?? "—" }}</view>
          <view class="q-label">免费次数</view>
        </view>
        <view class="quota-item">
          <view class="q-num">{{ user?.paid_quota ?? "—" }}</view>
          <view class="q-label">按次余额</view>
        </view>
        <view class="quota-item">
          <view class="q-num">{{ user ? (user.is_vip ? "有效" : "未开通") : "—" }}</view>
          <view class="q-label">月卡状态</view>
        </view>
      </view>
    </view>

    <view class="card">
      <view class="card-h">兑换练习次数或月卡</view>
      <view class="redeem-desc">输入从自习室前台或店铺取得的兑换码。</view>
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
      <view class="card-h">套餐说明</view>
      <view class="plan" @click="buyTip('冲刺体验包 9.9元/5次')">
        <view>
          <view class="plan-name">冲刺体验包（5 次精批）</view>
          <view class="plan-desc">申论大小作文 / 考研英语通用，永久有效</view>
        </view>
        <view class="price">¥9.9</view>
      </view>
      <view class="plan" @click="buyTip('上岸畅批月卡 29.9元/月')">
        <view>
          <view class="plan-name">上岸畅批月卡（30 天无限次）</view>
          <view class="plan-desc">自激活起 30 天内有效</view>
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
.page { padding: 42rpx 36rpx 54rpx; }
.name { font-family: var(--display); font-size: 48rpx; font-weight: 700; padding-bottom: 22rpx; border-bottom: 3rpx solid var(--ink); }
.quota-row { display: flex; margin: 28rpx 0 32rpx; }
.quota-item { flex: 1; min-width: 0; padding-left: 18rpx; border-left: 1rpx solid var(--rule); }
.quota-item:first-child { padding-left: 0; border: 0; }
.q-num { font-family: var(--display); font-size: 38rpx; line-height: 1.35; font-variant-numeric: tabular-nums; }
.q-label, .redeem-desc, .plan-desc { color: var(--muted); font-size: 24rpx; margin-top: 6rpx; }
.card { border-top: 1rpx solid var(--rule); padding: 26rpx 0; }
.card-h { font-family: var(--display); font-size: 34rpx; font-weight: 700; }
.redeem-row, .plan { display: flex; align-items: center; gap: 16rpx; }
.redeem-row { margin-top: 20rpx; }
.redeem-input { flex: 1; min-width: 0; padding: 0 15rpx; height: 76rpx; font-size: 25rpx; background: white; border: 1rpx solid var(--rule); border-radius: 5rpx; }
.redeem-btn { flex-shrink: 0; margin: 0; padding: 0 18rpx; line-height: 76rpx; font-size: 26rpx; color: white; background: var(--action); border-radius: 5rpx; }
.plan { justify-content: space-between; padding: 22rpx 0; border-bottom: 1rpx solid var(--rule); }
.plan-name { font-size: 28rpx; font-weight: 600; }
.price { color: var(--ink); font-family: var(--display); font-size: 34rpx; }
</style>
