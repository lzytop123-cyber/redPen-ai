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

    <view class="card">
      <view class="card-h">精批套餐（预留微信支付 v3 对接位）</view>
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

onShow(async () => {
  user.value = await request({ url: "/api/auth/me" });
});

function buyTip(planName: string) {
  uni.showModal({
    title: "接入提示",
    content: `已选中【${planName}】。上线前只需在后端接入微信支付 v3 JSAPI 并在小程序端调用 uni.requestPayment 即可收款。`,
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
  margin-bottom: 18rpx;
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
