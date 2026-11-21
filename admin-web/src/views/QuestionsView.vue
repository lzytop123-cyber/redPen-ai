<template>
  <div class="card">
    <div class="card-title">
      <span>📚 真题库与可视化采分点管理（共 {{ total }} 道）</span>
      <button class="btn btn-primary" @click="openCreate">+ 新增真题</button>
    </div>

    <div class="toolbar">
      <select v-model="examType" class="select" @change="resetAndLoad">
        <option value="">全部大类</option>
        <option value="shenlun_short">申论小题</option>
        <option value="shenlun_essay">申论大作文</option>
        <option value="kaoyan_english">考研英语</option>
        <option value="kaoyan_396">396经综写作</option>
      </select>
      <input v-model="region" class="input" placeholder="地区（如 国考/山西/贵州）" style="width:160px;" @keyup.enter="resetAndLoad" />
      <select v-model="hasPoints" class="select" @change="resetAndLoad">
        <option value="">采分点状态(全部)</option>
        <option value="yes">已有标准采分点</option>
        <option value="no">暂缺采分点</option>
      </select>
      <input v-model="keyword" class="input" placeholder="搜索 ID / 标题 / 题干" style="width:220px;" @keyup.enter="resetAndLoad" />
      <button class="btn btn-primary" @click="resetAndLoad">搜索</button>
    </div>

    <table class="tbl">
      <thead>
        <tr>
          <th>真题 ID</th>
          <th>标题</th>
          <th>年份</th>
          <th>满分</th>
          <th>材料字数</th>
          <th>采分点</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="q in items" :key="q.question_id">
          <td><code>{{ q.question_id }}</code></td>
          <td style="max-width:300px;">{{ q.title }}</td>
          <td>{{ q.year || "-" }}</td>
          <td>{{ q.full_score }}</td>
          <td>{{ q.material_len }}</td>
          <td>
            <span v-if="q.scoring_point_count > 0" class="badge badge-green">{{ q.scoring_point_count }} 个点</span>
            <span v-else-if="q.exam_type === 'shenlun_short'" class="badge badge-amber">待生成</span>
            <span v-else class="badge badge-gray">量表</span>
          </td>
          <td>
            <button class="btn btn-sm btn-primary" @click="openEdit(q.question_id)">编辑 / 采分点</button>
            <button class="btn btn-sm btn-danger" @click="removeQuestion(q.question_id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="pager">
      <span>第 {{ page }} 页 / 共 {{ Math.max(1, Math.ceil(total / pageSize)) }} 页</span>
      <div style="display:flex;gap:8px;">
        <button class="btn btn-sm" :disabled="page <= 1" @click="page--; load()">上一页</button>
        <button class="btn btn-sm" :disabled="page * pageSize >= total" @click="page++; load()">下一页</button>
      </div>
    </div>
  </div>

  <!-- 可视化真题与采分点编辑器抽屉 -->
  <div v-if="editing" class="modal-mask" @click.self="editing = null">
    <div class="drawer">
      <div class="drawer-head">
        <div style="font-weight:700;font-size:16px;">
          {{ isCreate ? "新增真题" : `编辑真题：${editing.question_id}` }}
        </div>
        <button class="btn btn-sm" @click="editing = null">关闭</button>
      </div>
      <div class="drawer-body">
        <div class="form-grid">
          <label v-if="isCreate">真题 ID（留空自动生成）<input v-model="editing.question_id" class="input" placeholder="如 SX-2026-S01" /></label>
          <label>大类
            <select v-model="editing.exam_type" class="select">
              <option value="shenlun_short">申论小题</option>
              <option value="shenlun_essay">申论大作文</option>
              <option value="kaoyan_english">考研英语</option>
            </select>
          </label>
          <label>年份<input v-model.number="editing.year" type="number" class="input" /></label>
          <label>满分<input v-model.number="editing.full_score" type="number" step="0.5" class="input" /></label>
          <label>地区/试卷名<input v-model="editing.paper" class="input" placeholder="如 山西-2026" /></label>
          <label>细分题型<input v-model="editing.sub_type" class="input" placeholder="单一题（归纳概括）" /></label>
          <label>最少字数<input v-model.number="editing.min_words" type="number" class="input" /></label>
          <label>最多字数<input v-model.number="editing.max_words" type="number" class="input" /></label>
        </div>

        <label class="full-label">标题<input v-model="editing.title" class="input" /></label>
        <label class="full-label">题目要求<textarea v-model="editing.prompt" class="textarea" rows="4" /></label>
        <label class="full-label">给定材料（{{ (editing.material_summary || "").length }} 字）<textarea v-model="editing.material_summary" class="textarea" rows="5" /></label>

        <!-- 可视化采分点表单编辑器 -->
        <div class="points-sec">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <div>
              <b>🎯 标准采分点配置</b>
              <span style="font-size:12px;color:#64748b;margin-left:8px;">
                当前合计 {{ pointsSum }} 分 / 满分 {{ editing.full_score }} 分
              </span>
            </div>
            <div style="display:flex;gap:8px;">
              <button v-if="!isCreate && editing.exam_type === 'shenlun_short'" class="btn btn-sm btn-success" :disabled="genLoading" @click="aiGeneratePoints">
                {{ genLoading ? "生成中..." : "✨ AI 一键生成 v2 采分点" }}
              </button>
              <button class="btn btn-sm btn-primary" @click="addPoint">+ 新增采分点</button>
            </div>
          </div>

          <div v-for="(p, idx) in editing.scoring_points" :key="idx" class="point-edit-row">
            <input v-model="p.point_id" class="input" style="width:58px;" placeholder="P1" />
            <input v-model="p.keyword" class="input" style="width:150px;" placeholder="规范总括词" />
            <input v-model.number="p.score" type="number" step="0.5" class="input" style="width:72px;" placeholder="分值" />
            <input v-model="p.description" class="input" style="flex:1;" placeholder="采分细项与同义表述" />
            <button class="btn btn-sm btn-danger" @click="editing.scoring_points.splice(idx, 1)">删</button>
          </div>
        </div>

        <label class="full-label">参考答案 / 立意解析<textarea v-model="editing.reference_answer" class="textarea" rows="5" /></label>
      </div>
      <div class="drawer-foot">
        <button class="btn" @click="editing = null">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="saveEdit">{{ saving ? "保存中..." : "保存并立即生效" }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { adminFetch } from "../api";

const examType = ref("");
const region = ref("");
const hasPoints = ref("");
const keyword = ref("");
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const items = ref<any[]>([]);

const editing = ref<any>(null);
const isCreate = ref(false);
const saving = ref(false);
const genLoading = ref(false);

const pointsSum = computed(() => {
  const list = editing.value?.scoring_points || [];
  return list.reduce((acc: number, p: any) => acc + (Number(p.score) || 0), 0).toFixed(1);
});

async function load() {
  const qs = new URLSearchParams({ page: String(page.value), page_size: String(pageSize) });
  if (examType.value) qs.set("exam_type", examType.value);
  if (region.value.trim()) qs.set("region", region.value.trim());
  if (hasPoints.value) qs.set("has_points", hasPoints.value);
  if (keyword.value.trim()) qs.set("keyword", keyword.value.trim());
  const res = await adminFetch(`/api/admin/questions?${qs.toString()}`);
  total.value = res.total;
  items.value = res.items;
}

function resetAndLoad() {
  page.value = 1;
  load();
}

function openCreate() {
  isCreate.value = true;
  editing.value = {
    question_id: "",
    exam_type: "shenlun_short",
    title: "",
    year: 2026,
    paper: "",
    sub_type: "单一题（归纳概括）",
    prompt: "",
    material_summary: "",
    full_score: 15,
    min_words: 0,
    max_words: 250,
    scoring_points: [],
    reference_answer: "",
  };
}

async function openEdit(qid: string) {
  isCreate.value = false;
  editing.value = await adminFetch(`/api/admin/questions/${encodeURIComponent(qid)}`);
}

function addPoint() {
  const nextIdx = (editing.value.scoring_points?.length || 0) + 1;
  editing.value.scoring_points.push({ point_id: `P${nextIdx}`, keyword: "", description: "", score: 2.5 });
}

async function aiGeneratePoints() {
  genLoading.value = true;
  try {
    const res = await adminFetch(`/api/admin/questions/${encodeURIComponent(editing.value.question_id)}/generate-points`, {
      method: "POST",
    });
    editing.value.scoring_points = res.scoring_points;
    editing.value.reference_answer = res.reference_answer;
    alert("已基于完整材料自动生成 v2 标准采分点并入库！");
    load();
  } catch (e: any) {
    alert("生成失败：" + e.message);
  } finally {
    genLoading.value = false;
  }
}

async function saveEdit() {
  saving.value = true;
  try {
    if (isCreate.value) {
      await adminFetch("/api/admin/questions", { method: "POST", body: JSON.stringify(editing.value) });
    } else {
      await adminFetch(`/api/admin/questions/${encodeURIComponent(editing.value.question_id)}`, {
        method: "PUT",
        body: JSON.stringify(editing.value),
      });
    }
    editing.value = null;
    load();
  } catch (e: any) {
    alert("保存失败：" + e.message);
  } finally {
    saving.value = false;
  }
}

async function removeQuestion(qid: string) {
  if (!confirm(`确定永久删除真题 ${qid} 吗？`)) return;
  await adminFetch(`/api/admin/questions/${encodeURIComponent(qid)}`, { method: "DELETE" });
  load();
}

onMounted(load);
</script>

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}
.form-grid label, .full-label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 10px;
}
.points-sec {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px;
  margin: 14px 0;
}
.point-edit-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
</style>
