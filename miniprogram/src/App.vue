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
  --paper: #faf9f6;
  --ink: #242c32;
  --muted: #5d676c;
  --rule: #d8d9d3;
  --wash: #eeefea;
  --action: #294859;
  --mark: #994535;
  --display: "Songti SC", "STSong", "Noto Serif CJK SC", "SimSun", serif;
  background: var(--paper);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 28rpx;
  line-height: 1.55;
}
.page {
  max-width: 760px;
  margin: 0 auto;
  box-sizing: border-box;
}
</style>
