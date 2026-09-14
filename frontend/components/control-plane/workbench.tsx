"use client";

import { DragEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Archive, ArrowRight, Check, ChevronRight, Download, Eye, FileText, Image as ImageIcon, LockKeyhole, Play, Plus, Sparkles, Upload, X, Zap } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { API_URL } from "@/lib/api";
import type { AuthUser } from "@/lib/auth";
import { Badge, Head, Title } from "./ui";
import { elapsedSeconds, formatBytes, isTaskActive, request, type AgentTask, type ArtifactPreview, type KnowledgeBase, type StoredFile, type TaskAccepted, type Workspace } from "./types";

function displayableMarkdown(value: string) {
  return value
    .replace(/<think>[\s\S]*?<\/think>/gi, "")
    .replace(/<\/?think>/gi, "")
    .trim();
}

const SOURCE_CODE_EXTENSIONS = [
  ".asm", ".astro", ".bash", ".c", ".cc", ".clj", ".cljs", ".cljc", ".cob",
  ".cpp", ".cs", ".css", ".cu", ".cuh", ".cxx", ".dart", ".erl", ".ex", ".exs",
  ".fish", ".fs", ".fsx", ".go", ".gql", ".gradle", ".graphql", ".groovy", ".h",
  ".hh", ".hpp", ".hrl", ".hs", ".htm", ".html", ".hxx", ".java", ".js", ".jsx",
  ".kt", ".kts", ".less", ".lhs", ".lua", ".m", ".mm", ".ml", ".mli", ".nim",
  ".php", ".pl", ".pm", ".proto", ".ps1", ".py", ".r", ".rb", ".rs", ".s", ".sass",
  ".scala", ".scss", ".sh", ".sol", ".sql", ".svelte", ".swift", ".tf", ".ts", ".tsx",
  ".vb", ".vue", ".zig", ".zsh",
] as const;
const SOURCE_CODE_EXTENSION_SET = new Set<string>(SOURCE_CODE_EXTENSIONS);
const WORKBENCH_UPLOAD_ACCEPT = [
  ".pdf", ".md", ".txt", ".csv", ".png", ".jpg", ".jpeg", ".zip", ".json",
  ".toml", ".yaml", ".yml", ".ini", ".cfg", ".xml", ".ipynb",
  ...SOURCE_CODE_EXTENSIONS,
].join(",");

function isCodingInput(file: StoredFile) {
  const normalized = file.display_name.toLocaleLowerCase();
  const suffix = normalized.includes(".") ? normalized.slice(normalized.lastIndexOf(".")) : "";
  return suffix === ".zip" || SOURCE_CODE_EXTENSION_SET.has(suffix);
}

type WorkflowMode = "auto" | "document" | "coding" | "procurement";
type TestCommand = "pytest" | "unittest" | "compile";
type WorkflowTab = {
  id: string;
  taskId: string | null;
  title: string;
  workspaceId: string;
  prompt: string;
  taskMode: WorkflowMode;
  testCommand: TestCommand;
  selectedFileIds: string[];
  selectedKnowledgeBaseIds: string[];
  selectionInitialized: boolean;
  createdAt: string;
};

const WORKFLOW_TABS_KEY = "sovereign-workflow-tabs-v1";
const ACTIVE_WORKFLOW_KEY = "sovereign-active-workflow-v1";
const DEFAULT_PROMPT = "Review the available local context and prepare a concise approval recommendation with safety caveats.";

function workflowTitle(goal: string) {
  const compact = goal.trim().replace(/\s+/g, " ");
  return compact ? `${compact.slice(0, 42)}${compact.length > 42 ? "…" : ""}` : "Untitled workflow";
}

function newWorkflow(workspaceId: string): WorkflowTab {
  return {
    id: crypto.randomUUID(), taskId: null, title: "Untitled workflow", workspaceId,
    prompt: DEFAULT_PROMPT, taskMode: "auto", testCommand: "pytest",
    selectedFileIds: [], selectedKnowledgeBaseIds: [], selectionInitialized: false,
    createdAt: new Date().toISOString(),
  };
}

function workflowFromTask(task: AgentTask): WorkflowTab {
  return {
    id: `task-${task.id}`, taskId: task.id, title: workflowTitle(task.goal),
    workspaceId: task.workspace_id, prompt: task.goal, taskMode: task.mode,
    testCommand: task.test_command, selectedFileIds: task.input_file_ids,
    selectedKnowledgeBaseIds: task.knowledge_base_ids, selectionInitialized: true,
    createdAt: task.created_at,
  };
}

function restoredTabs(storageKey: string): WorkflowTab[] {
  try {
    const value = JSON.parse(window.localStorage.getItem(storageKey) ?? "[]") as unknown;
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is WorkflowTab => Boolean(
      item && typeof item === "object" && "id" in item && "prompt" in item &&
      "workspaceId" in item && "selectedFileIds" in item && Array.isArray(item.selectedFileIds),
    ));
  } catch {
    return [];
  }
}

function activeAgentMessage(status: AgentTask["status"] | undefined, lastStepKind: string | undefined, lastStepTitle: string | undefined, taskType: string | undefined, modelName: string) {
  if (status === "cancel_requested") return {
    title: "Stopping the agent safely",
    detail: "Waiting for the current bounded operation to finish before closing the run.",
  };
  if (status === "queued" || !lastStepKind) return {
    title: "Preparing local execution",
    detail: "Starting the governed worker and reserving local resources.",
  };
  if (lastStepKind === "classification") return {
    title: "Selecting the safest capable model",
    detail: "Matching task requirements against locally registered capabilities.",
  };
  if (lastStepKind === "routing") return {
    title: taskType === "coding" ? "Isolating the repository" : taskType === "procurement" ? "Normalizing quotation evidence" : "Gathering permitted evidence",
    detail: taskType === "coding" ? "Copying only selected source files into a run-scoped working tree." : taskType === "procurement" ? "Combining quotation text, OCR, visual evidence, and policy context." : "Reading selected files and searching selected knowledge indexes.",
  };
  if (lastStepKind === "multimodal") return {
    title: "Comparing grounded evidence",
    detail: "Validating quotation rows, policy constraints, totals, and compliance exceptions.",
  };
  if (lastStepKind === "repository") return {
    title: "Proving the sandbox boundary",
    detail: "Launching a disposable non-root container and checking that external network access fails.",
  };
  if (lastStepKind === "patch") return {
    title: "Running isolated verification",
    detail: "Testing the proposed changes with fixed commands and bounded resources.",
  };
  if (lastStepKind === "sandbox" && lastStepTitle?.includes("failed")) return {
    title: "Repairing the failed attempt",
    detail: `${modelName} is using bounded test output to prepare one safer retry.`,
  };
  if (lastStepKind === "sandbox") return {
    title: "Preparing the minimal patch",
    detail: `${modelName} is reasoning over the isolated repository snapshot.`,
  };
  if (lastStepKind === "retrieval") return {
    title: "Generating a grounded answer",
    detail: `${modelName} is reasoning over the ranked local evidence.`,
  };
  if (lastStepKind === "model") return {
    title: "Building validated deliverables",
    detail: "Converting the response into requested artifacts and checking their structure.",
  };
  return {
    title: "Finalizing the governed run",
    detail: "Committing validation evidence and the immutable audit trail.",
  };
}

export function Workbench() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const currentUser = queryClient.getQueryData<AuthUser | null>(["auth", "me"]);
  const workflowTabsKey = `${WORKFLOW_TABS_KEY}:${currentUser?.id ?? "local"}`;
  const activeWorkflowKey = `${ACTIVE_WORKFLOW_KEY}:${currentUser?.id ?? "local"}`;
  const [tabs, setTabs] = useState<WorkflowTab[]>([]);
  const [activeTabId, setActiveTabId] = useState("");
  const [tabsReady, setTabsReady] = useState(false);
  const [files, setFiles] = useState<StoredFile[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const activeTab = tabs.find((item) => item.id === activeTabId) ?? tabs[0];
  const activeTaskId = activeTab?.taskId ?? null;
  const prompt = activeTab?.prompt ?? "";
  const taskMode = activeTab?.taskMode ?? "auto";
  const testCommand = activeTab?.testCommand ?? "pytest";
  const workspaceId = activeTab?.workspaceId ?? "";
  const selectedFileIds = new Set(activeTab?.selectedFileIds ?? []);
  const selectedKnowledgeBaseIds = new Set(activeTab?.selectedKnowledgeBaseIds ?? []);
  const activeSelectionInitialized = activeTab?.selectionInitialized ?? false;

  function updateTab(tabId: string, patch: Partial<WorkflowTab>) {
    setTabs((current) => current.map((item) => item.id === tabId ? { ...item, ...patch } : item));
  }

  function updateActiveTab(patch: Partial<WorkflowTab>) {
    if (activeTab) updateTab(activeTab.id, patch);
  }

  useEffect(() => {
    request<Workspace[]>("/workspaces").then((available) => {
      setWorkspaces(available);
      const preferred = window.localStorage.getItem("sovereign-default-workspace");
      const initialWorkspace = available.some((item) => item.id === preferred) ? preferred! : (available[0]?.id ?? "");
      const restored = restoredTabs(workflowTabsKey);
      const initialTabs = restored.length ? restored : [newWorkflow(initialWorkspace)];
      setTabs(initialTabs);
      const savedActive = window.localStorage.getItem(activeWorkflowKey);
      setActiveTabId(initialTabs.some((item) => item.id === savedActive) ? savedActive! : initialTabs[0].id);
      setTabsReady(true);
    }).catch((reason: Error) => setError(reason.message));
  }, [activeWorkflowKey, workflowTabsKey]);

  useEffect(() => {
    if (!tabsReady) return;
    window.localStorage.setItem(workflowTabsKey, JSON.stringify(tabs));
    window.localStorage.setItem(activeWorkflowKey, activeTabId);
  }, [activeTabId, activeWorkflowKey, tabs, tabsReady, workflowTabsKey]);

  useEffect(() => {
    if (!workspaceId) return;
    Promise.all([
      request<StoredFile[]>(`/workspaces/${workspaceId}/files`),
      request<KnowledgeBase[]>(`/knowledge-bases?workspace_id=${workspaceId}`),
    ]).then(([stored, bases]) => {
      setFiles(stored);
      setKnowledgeBases(bases);
      if (activeTabId && !activeSelectionInitialized && !activeTaskId) {
        updateTab(activeTabId, {
          selectedFileIds: stored.map((file) => file.id),
          selectedKnowledgeBaseIds: bases.filter((base) => base.status === "ready" && base.active_index_version != null).map((base) => base.id),
          selectionInitialized: true,
        });
      }
    }).catch((reason: Error) => setError(reason.message));
  }, [workspaceId, activeTabId, activeSelectionInitialized, activeTaskId]);

  const tasksQuery = useQuery({
    queryKey: ["tasks", "workbench"],
    queryFn: () => request<AgentTask[]>("/tasks?limit=100"),
    refetchInterval: 2500,
  });

  const taskQuery = useQuery({
    queryKey: ["task", activeTaskId],
    queryFn: () => request<AgentTask>(`/tasks/${activeTaskId}`),
    enabled: Boolean(activeTaskId),
    refetchInterval: (query) => isTaskActive(query.state.data?.status) ? 1000 : false,
  });
  const task = taskQuery.data;
  const run = task?.latest_run;
  const readyBases = knowledgeBases.filter((base) => base.status === "ready" && base.active_index_version != null);

  const submit = useMutation({
    mutationFn: (tab: WorkflowTab) => request<TaskAccepted>("/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        workspace_id: tab.workspaceId,
        goal: tab.prompt.trim(),
        input_file_ids: tab.selectedFileIds,
        knowledge_base_ids: tab.taskMode === "coding" ? [] : tab.selectedKnowledgeBaseIds,
        mode: tab.taskMode,
        test_command: tab.testCommand,
        requested_outputs: tab.taskMode === "coding" ? ["patch", "repository", "sandbox_report"] : tab.taskMode === "procurement" || tab.taskMode === "auto" ? ["xlsx", "docx"] : ["docx"],
      }),
    }),
    onSuccess: (accepted, submittedTab) => {
      updateTab(submittedTab.id, { taskId: accepted.task_id, title: workflowTitle(submittedTab.prompt) });
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
  const cancel = useMutation({
    mutationFn: (taskId: string) => request<AgentTask>(`/tasks/${taskId}/cancel`, { method: "POST" }),
    onSuccess: () => {
      void taskQuery.refetch();
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
  const artifactPreview = useMutation({
    mutationFn: (artifactId: string) => request<ArtifactPreview>(`/artifacts/${artifactId}/preview`),
  });
  useEffect(() => {
    if (!artifactPreview.data) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") artifactPreview.reset();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [artifactPreview]);

  async function upload(selected: FileList | null) {
    if (!workspaceId || !selected?.length || activeTab?.taskId) return;
    setError("");
    try {
      const uploaded: StoredFile[] = [];
      for (const file of Array.from(selected)) {
        const data = new FormData();
        data.append("file", file);
        uploaded.push(await request<StoredFile>(`/workspaces/${workspaceId}/files`, { method: "POST", body: data }));
      }
      setFiles((current) => [...uploaded, ...current]);
      updateActiveTab({ selectedFileIds: [...selectedFileIds, ...uploaded.map((file) => file.id)] });
      if (fileInput.current) fileInput.current.value = "";
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed.");
    }
  }

  async function removeFile(file: StoredFile) {
    if (!window.confirm(`Remove ${file.display_name} from this workspace? Existing audit records are retained.`)) return;
    try {
      await request<void>(`/workspaces/${workspaceId}/files/${file.id}`, { method: "DELETE" });
      setFiles((current) => current.filter((item) => item.id !== file.id));
      updateActiveTab({ selectedFileIds: [...selectedFileIds].filter((id) => id !== file.id) });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not remove the file.");
    }
  }

  function dropFiles(event: DragEvent<HTMLDivElement>) {
    event.preventDefault(); setDragging(false); void upload(event.dataTransfer.files);
  }

  function toggleFile(id: string) {
    if (activeTab?.taskId) return;
    const next = new Set(selectedFileIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    updateActiveTab({ selectedFileIds: [...next], selectionInitialized: true });
  }

  function toggleKnowledgeBase(id: string) {
    if (activeTab?.taskId) return;
    const next = new Set(selectedKnowledgeBaseIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    updateActiveTab({ selectedKnowledgeBaseIds: [...next], selectionInitialized: true });
  }

  function addWorkflow() {
    const next = newWorkflow(workspaceId || workspaces[0]?.id || "");
    setTabs((current) => [...current, next]);
    setActiveTabId(next.id);
    submit.reset();
  }

  function openTask(taskToOpen: AgentTask) {
    const existing = tabs.find((item) => item.taskId === taskToOpen.id);
    if (existing) {
      setActiveTabId(existing.id);
      return;
    }
    const next = workflowFromTask(taskToOpen);
    setTabs((current) => [...current, next]);
    setActiveTabId(next.id);
  }

  function closeWorkflow(tab: WorkflowTab) {
    const taskStatus = tasksQuery.data?.find((item) => item.id === tab.taskId)?.status;
    if (isTaskActive(taskStatus) && !window.confirm("Close this tab? The workflow will keep processing and can be reopened from All workflows.")) return;
    const remaining = tabs.filter((item) => item.id !== tab.id);
    if (!remaining.length) {
      const next = newWorkflow(workspaceId || workspaces[0]?.id || "");
      setTabs([next]);
      setActiveTabId(next.id);
      return;
    }
    setTabs(remaining);
    if (activeTabId === tab.id) {
      setActiveTabId(remaining[Math.max(0, tabs.indexOf(tab) - 1)]?.id ?? remaining[0].id);
    }
  }

  const status = task?.status ?? (submit.isPending ? "queued" : "ready");
  const displayedError = error || (submit.error instanceof Error ? submit.error.message : "") || (taskQuery.error instanceof Error ? taskQuery.error.message : "") || (tasksQuery.error instanceof Error ? tasksQuery.error.message : "");
  const modelName = run?.route.selected_model_key ?? "Automatic";
  const workspace = workspaces.find((item) => item.id === workspaceId);
  const lastStep = run?.steps.at(-1);
  const agentMessage = activeAgentMessage(task?.status, lastStep?.kind, lastStep?.title, task?.task_type, modelName);

  return <>
    <Title eyebrow="MISSION CONTROL" title="Agentic Workbench" copy="Turn confidential files into verified decisions and deliverables—entirely inside your network." action={<button className="secondary" onClick={addWorkflow}><Archive size={15} /> New Workflow</button>} />
    <div className="workflow-tabs" role="tablist" aria-label="Open workflows">
      <select className="workflow-history" aria-label="All workflows" value="" onChange={(event) => { const selected = tasksQuery.data?.find((item) => item.id === event.target.value); if (selected) openTask(selected); }}>
        <option value="">All workflows ({tasksQuery.data?.length ?? 0})</option>
        {tasksQuery.data?.map((item) => <option value={item.id} key={item.id}>{workflowTitle(item.goal)} · {item.status}</option>)}
      </select>
      <div className="workflow-tab-scroll">
        {tabs.map((tab) => {
          const tabTask = tasksQuery.data?.find((item) => item.id === tab.taskId);
          const tabStatus = tabTask?.status ?? (tab.taskId ? "queued" : "draft");
          return <div className={`workflow-tab ${tab.id === activeTab?.id ? "active" : ""}`} key={tab.id}>
            <button role="tab" aria-selected={tab.id === activeTab?.id} onClick={() => setActiveTabId(tab.id)}>
              <i className={`workflow-status ${tabStatus}`} />
              <span>{tab.title}</span>
              <small>{tabStatus === "queued" && tabTask?.queue_position ? `QUEUE ${tabTask.queue_position}` : tabStatus.replaceAll("_", " ")}</small>
            </button>
            <button className="workflow-close" aria-label={`Close ${tab.title}`} onClick={() => closeWorkflow(tab)}><X size={13} /></button>
          </div>;
        })}
      </div>
      <button className="workflow-add" aria-label="New workflow" onClick={addWorkflow}><Plus size={15} /></button>
    </div>
    {displayedError && <div className="api-error" role="alert">{displayedError}</div>}
    <div className="workbench">
      <section className="panel files">
        <Head n="01" label="INPUTS" title="Workspace files" action={<button className="square" aria-label="Add files" disabled={Boolean(activeTab?.taskId)} onClick={() => fileInput.current?.click()}><Plus size={16} /></button>} />
        <input ref={fileInput} className="hidden-file" type="file" multiple accept={WORKBENCH_UPLOAD_ACCEPT} onChange={(event) => void upload(event.target.files)} />
        <div className={`drop ${dragging ? "dragging" : ""} ${activeTab?.taskId ? "locked" : ""}`} onClick={() => { if (!activeTab?.taskId) fileInput.current?.click(); }} onDragEnter={(event) => { event.preventDefault(); if (!activeTab?.taskId) setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={dropFiles}><Upload size={20} /><b>{activeTab?.taskId ? "Submitted input snapshot" : taskMode === "coding" ? "Drop a repository ZIP or source files" : "Drop confidential files"}</b><small>{activeTab?.taskId ? "Create a New Workflow to change files" : taskMode === "coding" ? "ZIP or common source-code formats · max 20 MB" : "Documents, images, source files or ZIP · max 20 MB"}</small>{!activeTab?.taskId && <button type="button">Browse local files</button>}</div>
        <label className="select-all-files"><input type="checkbox" checked={files.length > 0 && selectedFileIds.size === files.length} disabled={!files.length || Boolean(activeTab?.taskId)} onChange={(event) => updateActiveTab({ selectedFileIds: event.target.checked ? files.map((file) => file.id) : [], selectionInitialized: true })} /><span>Select all files</span><small>{selectedFileIds.size} / {files.length}</small></label>
        <div className="file-list all-files">{files.map((file) => <div className={`file-row ${selectedFileIds.has(file.id) ? "selected" : ""}`} key={file.id} role="checkbox" aria-checked={selectedFileIds.has(file.id)} tabIndex={activeTab?.taskId ? -1 : 0} onClick={() => toggleFile(file.id)} onKeyDown={(event) => { if (event.key === " " || event.key === "Enter") { event.preventDefault(); toggleFile(file.id); } }}><input type="checkbox" aria-label={`Include ${file.display_name}`} checked={selectedFileIds.has(file.id)} disabled={Boolean(activeTab?.taskId)} onChange={() => toggleFile(file.id)} onClick={(event) => event.stopPropagation()} /><i className={/\.(png|jpe?g)$/i.test(file.display_name) ? "blue" : "amber"}>{/\.(png|jpe?g)$/i.test(file.display_name) ? <ImageIcon size={18} /> : <FileText size={18} />}</i><div><b>{file.display_name}</b><small>{formatBytes(file.size_bytes)} · {file.indexed ? "indexed" : file.status}</small></div><em>LOCAL</em>{!activeTab?.taskId && <button className="file-remove" aria-label={`Remove ${file.display_name}`} onClick={(event) => { event.stopPropagation(); void removeFile(file); }}><X size={14} /></button>}</div>)}{!files.length && <p className="empty-copy">No local files uploaded yet.</p>}</div>
        {taskMode !== "coding" && readyBases.length > 0 && <div className="kb-picker"><span className="eyebrow">KNOWLEDGE CONTEXT</span>{readyBases.map((base) => <label key={base.id}><input type="checkbox" checked={selectedKnowledgeBaseIds.has(base.id)} disabled={Boolean(activeTab?.taskId)} onChange={() => toggleKnowledgeBase(base.id)} /><span>{base.name}</span><small>v{base.active_index_version}</small></label>)}</div>}
        <div className="isolated"><LockKeyhole size={14} /><span><b>Workspace isolated</b><small>{workspace ? `${workspace.name} · ${selectedKnowledgeBaseIds.size} knowledge ${selectedKnowledgeBaseIds.size === 1 ? "base" : "bases"} selected` : "Waiting for workspace"}</small></span></div>
      </section>
      <section className="panel task">
        <Head n="02" label="TASK" title="Describe the outcome" action={<Badge tone="blue">{selectedFileIds.size} OF {files.length} SELECTED</Badge>} />
        <textarea value={prompt} maxLength={8000} readOnly={Boolean(activeTab?.taskId)} onChange={(event) => updateActiveTab({ prompt: event.target.value, title: workflowTitle(event.target.value) })} />
        <div className="task-options"><label><span>WORKFLOW OVERRIDE</span><select value={taskMode} disabled={Boolean(activeTab?.taskId)} onChange={(event) => { const mode = event.target.value as WorkflowMode; const patch: Partial<WorkflowTab> = { taskMode: mode }; if (mode === "coding") { patch.selectedKnowledgeBaseIds = []; patch.selectedFileIds = files.filter(isCodingInput).map((file) => file.id); patch.prompt = "Fix the defect in this repository and verify the complete test suite."; } else if (mode === "procurement") { patch.selectedFileIds = files.filter((file) => !isCodingInput(file) || /\.(csv|md|txt|json)$/i.test(file.display_name)).map((file) => file.id); patch.prompt = "Compare the vendor quotations against the procurement policy and prepare a governed award recommendation."; } else if (mode === "document") { patch.prompt = DEFAULT_PROMPT; } if (patch.prompt) patch.title = workflowTitle(patch.prompt); updateActiveTab(patch); }}><option value="auto">Automatic (recommended)</option><option value="document">Document agent</option><option value="coding">Coding agent</option><option value="procurement">Procurement agent</option></select></label>{taskMode === "coding" && <label><span>VERIFICATION</span><select value={testCommand} disabled={Boolean(activeTab?.taskId)} onChange={(event) => updateActiveTab({ testCommand: event.target.value as TestCommand })}><option value="pytest">pytest -q</option><option value="unittest">unittest discover</option><option value="compile">compileall</option></select></label>}<Badge tone={taskMode === "coding" ? "amber" : "green"}>{taskMode === "auto" ? "AGENT + MODEL AUTO" : taskMode === "coding" ? "NO-NETWORK SANDBOX" : taskMode === "procurement" ? "XLSX + DOCX" : "GROUNDED LOCAL"}</Badge></div>
        <div className="hints"><span><Sparkles size={14} /> Bounded local agent</span><span><LockKeyhole size={14} /> Organization scoped</span></div>
        <div className="router"><i><Eye size={18} /></i><div><small>DETERMINISTIC ROUTING</small><b>{task?.task_type ? `${task.task_type.replaceAll("_", " ")} task` : "Capability-based route"}</b><span>{run?.agent_profile?.replaceAll("_", " ") ?? "Classified after submission"}</span></div><ArrowRight size={17} /><div className="model"><i>AI</i><span><small>SELECTED MODEL</small><b>{modelName}</b></span></div></div>
        <button className="run" onClick={() => activeTab && submit.mutate(activeTab)} disabled={submit.isPending || Boolean(activeTab?.taskId) || !workspaceId || !prompt.trim() || ((taskMode === "coding" || taskMode === "procurement") && selectedFileIds.size === 0)}><Play size={15} fill="currentColor" />{activeTab?.taskId ? "Workflow submitted" : submit.isPending ? "Submitting locally…" : taskMode === "coding" && selectedFileIds.size === 0 ? "Select repository files" : taskMode === "procurement" && selectedFileIds.size === 0 ? "Select quotation files" : "Run sovereign agent"}<kbd>LOCAL</kbd></button>
        {isTaskActive(task?.status) && activeTaskId && <button className="trace-link" onClick={() => cancel.mutate(activeTaskId)} disabled={cancel.isPending}>Cancel safely</button>}
      </section>
      <section className="panel execution">
        <Head n="03" label="EXECUTION" title="Live agent trace" action={<Badge tone={status === "completed" ? "green" : isTaskActive(status) ? "amber" : "neutral"}>{isTaskActive(status) ? <><i className="dot amber" /> {status.toUpperCase()}</> : status === "completed" ? <><Check size={12} /> COMPLETE</> : status.toUpperCase()}</Badge>} />
        <div className="run-meta"><span>{run ? `ATTEMPT ${run.attempt}` : "NO RUN"}</span><span>{task?.queue_position ? `QUEUE ${task.queue_position}` : elapsedSeconds(run?.started_at, run?.completed_at)}</span><span>{run?.step_count ?? 0} STEPS</span></div>
        <div className="steps">{run?.steps.map((step) => <div className={`step ${step.status === "completed" ? "done" : step.status === "failed" ? "current" : "pending"}`} key={step.id}><i>{step.status === "completed" ? <Check size={12} /> : <Zap size={12} />}</i><div><b>{step.title}</b><small>{step.detail}</small></div><time>{step.duration_ms == null ? "—" : `${(step.duration_ms / 1000).toFixed(1)}s`}</time></div>)}{isTaskActive(task?.status) && <div className="agent-working" role="status" aria-live="polite"><i className="agent-orbit"><Sparkles size={13} /></i><div><b>{agentMessage.title}</b><small>{agentMessage.detail}</small><span className="agent-progress"><i /></span></div><em aria-hidden="true"><i /><i /><i /></em></div>}{!run?.steps.length && !isTaskActive(task?.status) && <p className="empty-copy">Submit a task to see every governed step as it is committed.</p>}</div>
        <button className="trace-link" onClick={() => router.push(`/trace${task ? `?task=${task.id}` : ""}`)}>Open audit view <ChevronRight size={13} /></button>
      </section>
    </div>
    <div className="results">
      <section className="panel finding"><div><span className="eyebrow">AGENT RESULT</span><h2>{task ? `${modelName} · ${task.status}` : "Run a task to generate a governed response"}</h2></div>{task?.status === "completed" && <Badge tone="green">VERIFIED LOCAL</Badge>}<div className="response-text">{run?.error_message ? <span className="error-copy">{run.error_message}</span> : run?.result_text ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayableMarkdown(run.result_text)}</ReactMarkdown> : "The grounded result will appear here after routing, tool access, and local inference complete."}</div>{Boolean(run?.citations.length) && <div className="result-sources"><span className="eyebrow">USED SOURCES</span>{run?.citations.map((citation) => <div key={citation.source_id}><Badge tone="blue">{citation.source_id}</Badge><span><b>{citation.display_name}</b><small>Page {citation.page_start}{citation.page_end !== citation.page_start ? `–${citation.page_end}` : ""} · {citation.retrieval_mode.replaceAll("_", " ")}{citation.knowledge_base_name ? ` · ${citation.knowledge_base_name}` : ""}</small></span></div>)}</div>}</section>
      <section className="panel artifact artifact-list"><i><FileText size={25} /></i><div><span className="eyebrow">VALIDATED ARTIFACTS</span>{run?.artifacts.length ? run.artifacts.map((item) => <div className="artifact-item" key={item.id}><span><h2>{item.display_name}</h2><small>{formatBytes(item.size_bytes)} · {item.validation_status} · SHA-256 {item.sha256.slice(0, 12)}…</small></span><div className="artifact-actions"><button className="artifact-preview-button" disabled={artifactPreview.isPending} onClick={() => artifactPreview.mutate(item.id)}><Eye size={15} /> Preview</button><a className="artifact-download" href={`${new URL(API_URL).origin}${item.download_url}`}><Download size={16} /> Download</a></div></div>) : <><h2>No artifact generated yet</h2><small>Artifacts are generated atomically after a successful task.</small></>}</div></section>
    </div>
    {artifactPreview.data && <div className="artifact-preview-backdrop" role="presentation" onClick={() => artifactPreview.reset()}><section className="artifact-preview-panel" role="dialog" aria-modal="true" aria-labelledby="artifact-preview-title" onClick={(event) => event.stopPropagation()}><header><div><span className="eyebrow">SAFE READ-ONLY PREVIEW</span><h2 id="artifact-preview-title">{artifactPreview.data.display_name}</h2><small>{artifactPreview.data.preview_type} · generated locally{artifactPreview.data.truncated ? " · preview truncated" : ""}</small></div><button aria-label="Close artifact preview" onClick={() => artifactPreview.reset()}><X size={17} /></button></header><pre>{artifactPreview.data.content}</pre></section></div>}
    {artifactPreview.error instanceof Error && <div className="api-error" role="alert">{artifactPreview.error.message}</div>}
  </>;
}
