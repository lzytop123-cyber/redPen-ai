<template>
  <view class="page">
    <view class="title">练习记录</view>
    <view v-if="weaknesses.length" class="card">
      <view class="card-h">常见扣分项</view>
      <view class="tags">
        <text v-for="w in weaknesses" :key="w.tag" class="wtag">
          {{ w.tag }} · {{ w.count }} 次
        </text>
      </view>
    </view>

    <view class="card">
      <view class="card-h">最近提交 <text v-if="items.length" class="count">{{ items.length }} 篇</text></view>
      <view v-if="loadError" class="empty" @click="loadHistory">记录加载失败，点此重试</view>
      <view v-else-if="loading && !items.length" class="empty">正在读取记录…</view>
      <view v-else-if="!items.length" class="empty">
        <view>提交第一篇作答后，就能在这里回看批注。</view>
        <button class="library-btn" @click="openLibrary">去选题</button>
      </view>
      <view v-for="item in items" :key="item.task_id" class="row" @click="openReport(item.task_id)">
        <view class="row-title">{{ item.question_title }}</view>
        <view class="row-bottom">
          <text class="band">{{ item.band_label || statusLabels[item.status] || "已提交" }}</text>
          <text v-if="item.final_score !== null" class="score">{{ item.final_score }} / {{ item.full_score }} 分</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { ensureLogin, request } from "@/utils/request";

const weaknesses = ref<Array<{ tag: string; count: number }>>([]);
const items = ref<any[]>([]);

const loading = ref(true);
const loadError = ref(false);
const statusLabels: Record<string, string> = { pending: "等待批改", running: "批改中", failed: "批改未完成", completed: "已批改" };

async function loadHistory() {
  loading.value = true;
  loadError.value = false;
  try {
    await ensureLogin();
    const res = await request<any>({ url: "/api/grading/history" });
    weaknesses.value = res.top_weaknesses || [];
    items.value = res.items || [];
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
}
onShow(loadHistory);

function openLibrary() {
  uni.switchTab({ url: "/pages/index/index" });
}

function openReport(taskId: string) {
  uni.navigateTo({ url: `/pages/report/report?taskId=${encodeURIComponent(taskId)}` });
}
</script>

<style scoped>
.page { padding: 42rpx 36rpx; }
.title { font-family: var(--display); font-size: 52rpx; font-weight: 700; padding-bottom: 22rpx; border-bottom: 3rpx solid var(--ink); }
.card { padding: 26rpx 0 0; }
.card-h { display: flex; justify-content: space-between; align-items: baseline; font-weight: 600; font-size: 30rpx; }
.count, .band, .empty { font-size: 25rpx; color: var(--muted); font-weight: 400; }
.tags { display: flex; flex-wrap: wrap; gap: 12rpx; padding: 16rpx 0 24rpx; border-bottom: 1rpx solid var(--rule); }
.wtag { background: var(--wash); color: var(--ink); padding: 5rpx 12rpx; font-size: 24rpx; }
.row { padding: 24rpx 0; border-bottom: 1rpx solid var(--rule); }
.row-title { font-family: var(--display); font-size: 34rpx; line-height: 1.5; font-weight: 600; }
.row-bottom { display: flex; justify-content: space-between; gap: 14rpx; margin-top: 8rpx; }
.score { color: var(--mark); font-size: 27rpx; font-variant-numeric: tabular-nums; }
.empty { padding: 40rpx 0; }
.library-btn { display: inline-block; margin-top: 20rpx; background: var(--action); color: white; font-size: 26rpx; border-radius: 5rpx; }
</style>
