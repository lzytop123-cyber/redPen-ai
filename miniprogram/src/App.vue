<script setup lang="ts">
import { onLaunch } from "@dcloudio/uni-app";
import { ensureLogin } from "@/utils/request";

onLaunch(() => {
  ensureLogin().catch((err) => {
    console.warn("自动登录暂未完成（本地无后端时可忽略）:", err);
  });
});
</script>

<style>
page {
  background-color: #f5f7fa;
  color: #1f2937;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 28rpx;
}
</style>
