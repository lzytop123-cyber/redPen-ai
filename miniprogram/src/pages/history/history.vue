<template>
  <view class="page">
    <view v-if="weaknesses.length" class="card">
      <view class="card-h">我的高频扣分薄弱项</view>
      <view class="tags">
        <text v-for="w in weaknesses" :key="w.tag" class="wtag">
          #{{ w.tag }} ({{ w.count }}次)
        </text>
      </view>
    </view>

    <view class="card">
      <view class="card-h">历史精批记录 ({{ items.length }})</view>
      <view v-if="items.length === 0" class="empty">还没有批改记录，快去真题库练一篇吧</view>
      <view v-for="item in items" :key="item.task_id" class="row" @click="openReport(item.task_id)">
        <view class="row-title">{{ item.question_title }}</view>
        <view class="row-bottom">
          <text class="band">{{ item.band_label || item.status }}</text>
          <text v-if="item.final_score !== null" class="score">{{ item.final_score }} / {{ item.full_score }} 分</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { request } from "@/utils/request";

const weaknesses = ref<Array<{ tag: string; count: number }>>([]);
const items = ref<any[]>([]);

onShow(async () => {
  const res = await request<any>({ url: "/api/grading/history" });
  weaknesses.value = res.top_weaknesses || [];
  items.value = res.items || [];
});

function openReport(taskId: string) {
  uni.navigateTo({ url: `/pages/report/report?taskId=${encodeURIComponent(taskId)}` });
}
</script>

<style scoped>
.page {
  padding: 20rpx 24rpx;
}
.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
}
.card-h {
  font-size: 30rpx;
  font-weight: 700;
  margin-bottom: 16rpx;
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}
.wtag {
  background: #eef2ff;
  color: #3730a3;
  font-size: 24rpx;
  padding: 6rpx 16rpx;
  border-radius: 99rpx;
}
.row {
  padding: 18rpx 0;
  border-bottom: 1rpx solid #f3f4f6;
}
.row-title {
  font-size: 28rpx;
  font-weight: 600;
}
.row-bottom {
  display: flex;
  justify-content: space-between;
  margin-top: 10rpx;
  font-size: 24rpx;
}
.band {
  color: #6b7280;
}
.score {
  color: #2563eb;
  font-weight: 700;
}
.empty {
  text-align: center;
  color: #9ca3af;
  padding: 40rpx 0;
}
</style>
