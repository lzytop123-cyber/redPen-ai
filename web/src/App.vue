<template>
  <div class="app-root">
    <TopNav :active-page="navActivePage" @navigate="handleNav" />

    <main class="main-stage">
      <LibraryView
        v-if="route.page === 'library'"
        @open-question="openQuestion"
        @open-custom="openCustom"
      />

      <WorkspaceView
        v-else-if="route.page === 'workspace'"
        :question-id="route.questionId"
        :from-task-id="route.fromTaskId"
        :custom-mode="route.customMode"
        :initial-exam-type="route.examType"
        @back="goLibrary"
        @submitted="openReport"
      />

      <ReportView
        v-else-if="route.page === 'report' && route.taskId"
        :task-id="route.taskId"
        @back="goBackFromReport"
        @rewrite="openRewrite"
      />

      <HistoryView
        v-else-if="route.page === 'history'"
        @open-report="openReport"
        @rewrite-question="openRewrite"
      />
    </main>

    <AuthModal />
    <AccountModal />
    <FeedbackWidget :page="route.page" :question-id="route.questionId" :task-id="route.taskId" />
    <ToastContainer />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive } from "vue";
import AccountModal from "./components/AccountModal.vue";
import AuthModal from "./components/AuthModal.vue";
import FeedbackWidget from "./components/FeedbackWidget.vue";
import ToastContainer from "./components/ToastContainer.vue";
import TopNav from "./components/TopNav.vue";
import { refreshUser } from "./stores/auth";
import type { ExamType } from "./types";
import HistoryView from "./views/HistoryView.vue";
import LibraryView from "./views/LibraryView.vue";
import ReportView from "./views/ReportView.vue";
import WorkspaceView from "./views/WorkspaceView.vue";

interface RouteState {
  page: "library" | "workspace" | "report" | "history";
  questionId?: string;
  fromTaskId?: string;
  customMode?: boolean;
  examType?: ExamType;
  taskId?: string;
  prevPage?: "library" | "history";
}

const route = reactive<RouteState>({
  page: "library",
  prevPage: "library",
});

const navActivePage = computed(() => {
  if (route.page === "workspace" && route.customMode) return "custom";
  if (route.page === "history") return "history";
  return "library";
});

function syncHash() {
  let hash = "#/";
  if (route.page === "history") {
    hash = "#/history";
  } else if (route.page === "workspace") {
    if (route.customMode) {
      hash = `#/custom?type=${encodeURIComponent(route.examType || "shenlun_essay")}`;
    } else {
      const q = new URLSearchParams();
      if (route.questionId) q.set("qid", route.questionId);
      if (route.fromTaskId) q.set("fromTask", route.fromTaskId);
      hash = `#/work?${q.toString()}`;
    }
  } else if (route.page === "report" && route.taskId) {
    hash = `#/report?taskId=${encodeURIComponent(route.taskId)}`;
  }
  if (window.location.hash !== hash) {
    window.history.pushState(null, "", hash);
  }
}

function parseHash() {
  const raw = window.location.hash || "#/";
  const [path, queryStr] = raw.replace(/^#/, "").split("?");
  const params = new URLSearchParams(queryStr || "");

  if (path === "/history") {
    route.page = "history";
  } else if (path === "/custom") {
    route.page = "workspace";
    route.customMode = true;
    route.questionId = "";
    route.fromTaskId = "";
    route.examType = (params.get("type") as ExamType) || "shenlun_essay";
  } else if (path === "/work") {
    route.page = "workspace";
    route.customMode = false;
    route.questionId = params.get("qid") || "";
    route.fromTaskId = params.get("fromTask") || "";
  } else if (path === "/report" && params.get("taskId")) {
    route.page = "report";
    route.taskId = params.get("taskId") || "";
  } else {
    route.page = "library";
  }
}

function handleNav(target: "library" | "custom" | "history") {
  if (target === "library") {
    goLibrary();
  } else if (target === "custom") {
    openCustom("shenlun_essay");
  } else {
    route.page = "history";
    syncHash();
  }
}

function goLibrary() {
  route.page = "library";
  route.prevPage = "library";
  syncHash();
}

function openQuestion(questionId: string) {
  route.page = "workspace";
  route.customMode = false;
  route.questionId = questionId;
  route.fromTaskId = "";
  syncHash();
}

function openCustom(examType: ExamType) {
  route.page = "workspace";
  route.customMode = true;
  route.questionId = "";
  route.fromTaskId = "";
  route.examType = examType;
  syncHash();
}

function openRewrite(questionId: string, fromTaskId: string) {
  route.page = "workspace";
  route.customMode = false;
  route.questionId = questionId;
  route.fromTaskId = fromTaskId;
  syncHash();
}

function openReport(taskId: string) {
  route.prevPage = route.page === "history" ? "history" : "library";
  route.page = "report";
  route.taskId = taskId;
  syncHash();
}

function goBackFromReport() {
  route.page = route.prevPage || "library";
  syncHash();
}

onMounted(() => {
  parseHash();
  window.addEventListener("hashchange", parseHash);
  window.addEventListener("popstate", parseHash);
  refreshUser(true);
});

onBeforeUnmount(() => {
  window.removeEventListener("hashchange", parseHash);
  window.removeEventListener("popstate", parseHash);
});
</script>

<style scoped>
.app-root {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-stage {
  flex: 1;
}
</style>
