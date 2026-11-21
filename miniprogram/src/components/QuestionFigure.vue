<template>
  <view v-if="caption" class="figure">
    <view class="figure-heading">
      <text>练习示意图 · 依题干绘制</text>
      <button class="enlarge" size="mini" @click="preview">放大查看</button>
    </view>
    <image class="figure-image" :src="source" mode="widthFix" :aria-label="caption" @click="preview" />
    <view class="caption">{{ caption }}</view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import figures from "../../../data/practice_figures.json";

const props = defineProps<{ questionId: string }>();
const catalog: Record<string, { caption: string; extension: string }> = figures;
const figure = computed(() => catalog[props.questionId]);
const caption = computed(() => figure.value?.caption);
const source = computed(() => `/static/figures/${props.questionId}.${figure.value?.extension}`);
function openImage(path: string) {
  uni.previewImage({
    current: path,
    urls: [path],
    fail: () => uni.showToast({ title: "图片暂时无法打开，请重试", icon: "none" }),
  });
}

// #ifdef MP-WEIXIN
declare const wx: { env: { USER_DATA_PATH: string } };
// #endif
function preview() {
  // #ifdef MP-WEIXIN
  // Native preview receives a local user file, including when the device is offline.
  const localPath = wx.env.USER_DATA_PATH + "/practice-" + source.value.split("/").pop();
  uni.getFileSystemManager().copyFile({
    srcPath: source.value,
    destPath: localPath,
    success: () => openImage(localPath),
    fail: () => openImage(source.value),
  });
  // #endif
  // #ifndef MP-WEIXIN
  openImage(source.value);
  // #endif
}
</script>

<style scoped>
.figure { margin-top: 24rpx; }
.figure-heading { display: flex; align-items: center; justify-content: space-between; font-size: 26rpx; font-weight: 600; }
.enlarge { margin: 0; color: var(--action); background: var(--wash); }
.figure-image { display: block; width: 100%; border-radius: 12rpx; margin-top: 12rpx; }
.caption { margin-top: 10rpx; color: var(--muted); font-size: 24rpx; line-height: 1.6; }
</style>
