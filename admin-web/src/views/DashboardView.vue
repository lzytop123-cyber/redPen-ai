<template>
  <div v-if="stats">
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-label">累计用户数</div>
        <div class="stat-val">{{ stats.total_users }}</div>
        <div class="stat-sub">今日新增 +{{ stats.today_users }} ｜ 月卡生效 {{ stats.active_vips }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">今日精批篇数</div>
        <div class="stat-val text-blue">{{ stats.today_tasks }}</div>
        <div class="stat-sub">累计精批 {{ stats.total_tasks }} 篇</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">批改成功率</div>
        <div class="stat-val text-green">{{ stats.success_rate }}%</div>
        <div class="stat-sub">失败任务 {{ stats.failed_tasks }} 条</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">题库与采分点覆盖</div>
        <div class="stat-val">{{ stats.total_questions }}</div>
        <div class="stat-sub">申论小题已含采分点 {{ stats.short_with_points }} / {{ stats.short_total }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">兑换码库存</div>
        <div class="stat-val text-amber">{{ stats.unused_codes }}</div>
        <div class="stat-sub">已核销 {{ stats.used_codes }} 个</div>
      </div>
    </div>

    <div class="two-col">
      <!-- 近 7 天批改趋势柱状图 -->
      <div class="card">
        <div class="card-title">
          <span>📈 近 7 天精批趋势</span>
          <button class="btn btn-sm" @click="load">刷新</button>
        </div>
        <div class="chart-box">
          <div v-for="d in stats.trend_7d" :key="d.date" class="bar-col">
            <div class="bar-num">{{ d.count }}</div>
            <div class="bar-track">
              <div class="bar-fill" :style="{ height: barHeight(d.count) + '%' }" />
            </div>
            <div class="bar-date">{{ d.date }}</div>
          </div>
        </div>
      </div>

      <!-- 热门被练真题 Top 10 -->
      <div class="card">
        <div class="card-title">🔥 热门被练真题 Top 10</div>
        <div v-if="!stats.top_questions.length" style="color:#94a3b8;padding:30px 0;text-align:center;">
          暂无批改数据
        </div>
        <table v-else class="tbl">
          <thead>
            <tr><th>真题 ID</th><th>题目名称</th><th style="width:70px;">批改次</th></tr>
          </thead>
          <tbody>
            <tr v-for="q in stats.top_questions" :key="q.question_id">
              <td><code>{{ q.question_id }}</code></td>
              <td>{{ q.title }}</td>
              <td><span class="badge badge-blue">{{ q.count }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { adminFetch } from "../api";

const stats = ref<any>(null);

function barHeight(count: number): number {
  const max = Math.max(1, ...(stats.value?.trend_7d || []).map((x: any) => x.count));
  return Math.max(6, Math.round((count / max) * 100));
}

async function load() {
  stats.value = await adminFetch("/api/admin/stats");
}

onMounted(load);
</script>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}
.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 18px 20px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.05);
}
.stat-label { font-size: 13px; color: #64748b; }
.stat-val { font-size: 30px; font-weight: 800; margin: 6px 0; color: #0f172a; }
.stat-sub { font-size: 12px; color: #94a3b8; }
.text-blue { color: #2563eb; }
.text-green { color: #16a34a; }
.text-amber { color: #d97706; }
.two-col {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 18px;
}
@media (max-width: 960px) {
  .two-col { grid-template-columns: 1fr; }
}
.chart-box {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  height: 220px;
  padding: 16px 8px 0;
  gap: 12px;
}
.bar-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}
.bar-num { font-size: 12px; font-weight: 700; color: #2563eb; margin-bottom: 6px; }
.bar-track {
  flex: 1;
  width: 28px;
  background: #f1f5f9;
  border-radius: 6px;
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}
.bar-fill {
  width: 100%;
  background: linear-gradient(180deg, #3b82f6, #1d4ed8);
  border-radius: 6px 6px 0 0;
}
.bar-date { font-size: 12px; color: #64748b; margin-top: 8px; }
</style>
