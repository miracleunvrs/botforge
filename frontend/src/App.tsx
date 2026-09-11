import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  Check,
  ChevronRight,
  CircleStop,
  MessageSquare,
  MousePointerClick,
  Play,
  Plus,
  Save,
  Send,
  UserRound,
  GitBranch,
  LayoutTemplate,
  BarChart3,
  Pause,
  KeyRound,
  Trash2,
  Flag,
  FolderOpen,
  Copy,
  Users,
} from "lucide-react";

type NodeKind = "message" | "choice" | "input" | "end" | "condition";
type Choice = { label: string; next_id: string | null };
type FlowNode = {
  id: string;
  kind: NodeKind;
  title: string;
  text: string;
  next_id: string | null;
  choices: Choice[];
  condition_value: string;
  true_next_id: string | null;
  false_next_id: string | null;
  variable_name?: string;
};
type ChatLine = { from: "bot" | "user"; text: string };
type TemplateApi = {
  id: string;
  title: string;
  description: string;
  definition: {
    start_id: string;
    nodes: {
      id: string;
      type: string;
      title: string;
      text: string;
      next_id: string | null;
      choices: { label: string; next_id: string }[];
      condition_value: string;
      true_next_id: string | null;
      false_next_id: string | null;
      variable_name?: string | null;
    }[];
  };
};

type WorkflowItem = {
  id: number;
  name: string;
  description: string;
  is_published: boolean;
  has_token: boolean;
  updated_at: string;
  definition: TemplateApi["definition"];
};

type BotUserItem = {
  id: number;
  telegram_user_id: number;
  username: string | null;
  current_node_id: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
};

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

const kindMeta: Record<NodeKind, { title: string; titleRu: string; icon: typeof MessageSquare; color: string }> = {
  message: { title: "Message", titleRu: "Сообщение", icon: MessageSquare, color: "" },
  choice: { title: "Buttons", titleRu: "Кнопки", icon: MousePointerClick, color: "" },
  condition: { title: "Condition", titleRu: "Условие", icon: GitBranch, color: "" },
  input: { title: "User input", titleRu: "Запрос данных", icon: UserRound, color: "" },
  end: { title: "Complete", titleRu: "Завершение", icon: CircleStop, color: "" },
};

function toFlowDefinition(nodes: FlowNode[], startId: string) {
  return {
    start_id: startId,
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.kind,
      title: n.title,
      text: n.text,
      next_id: n.kind === "choice" || n.kind === "condition" ? null : n.next_id,
      choices:
        n.kind === "choice"
          ? n.choices
              .map((c) => ({ label: c.label, next_id: c.next_id ?? "" }))
              .filter((c) => c.label && c.next_id)
          : [],
      condition_value: n.condition_value ?? "",
      true_next_id: n.true_next_id,
      false_next_id: n.false_next_id,
      variable_name: n.variable_name?.trim() || null,
    })),
  };
}

function fromDefinition(def: TemplateApi["definition"]): FlowNode[] {
  return def.nodes.map((n) => ({
    id: String(n.id),
    kind: n.type as NodeKind,
    title: n.title,
    text: n.text,
    next_id: n.next_id ?? null,
    choices: (n.choices ?? []).map((c) => ({ label: c.label, next_id: c.next_id ?? null })),
    condition_value: (n as unknown as { condition_value?: string }).condition_value ?? "",
    true_next_id: (n as unknown as { true_next_id?: string | null }).true_next_id ?? null,
    false_next_id: (n as unknown as { false_next_id?: string | null }).false_next_id ?? null,
    variable_name: n.variable_name ?? "",
  }));
}

const initialNodes: FlowNode[] = [
  { id: "1", kind: "message", title: "Приветствие", text: "Привет! Я бот студии Northwind 👋 Чем могу помочь?", next_id: "2", choices: [], condition_value: "", true_next_id: null, false_next_id: null },
  { id: "2", kind: "choice", title: "Главное меню", text: "Выберите действие:", next_id: null, choices: [{ label: "Услуги", next_id: "3" }, { label: "Связаться", next_id: "4" }], condition_value: "", true_next_id: null, false_next_id: null },
  { id: "3", kind: "message", title: "Услуги", text: "Делаем сайты, ботов и дизайн. Напишите, что вам нужно.", next_id: "4", choices: [], condition_value: "", true_next_id: null, false_next_id: null },
  { id: "4", kind: "input", title: "Сбор контакта", text: "Оставьте email или телефон — ответим за 15 минут.", next_id: "5", choices: [], condition_value: "", true_next_id: null, false_next_id: null },
  { id: "5", kind: "condition", title: "Проверка контакта", text: "Проверяем формат…", next_id: null, choices: [], condition_value: "@", true_next_id: "6", false_next_id: "7" },
  { id: "6", kind: "end", title: "Успех", text: "Спасибо! Мы получили ваш контакт и скоро свяжемся.", next_id: null, choices: [], condition_value: "", true_next_id: null, false_next_id: null },
  { id: "7", kind: "end", title: "Уточнение", text: "Приняли! Уточним детали и отпишемся.", next_id: null, choices: [], condition_value: "", true_next_id: null, false_next_id: null },
];

export function App() {
  const [nodes, setNodes] = useState<FlowNode[]>(initialNodes);
  const [startNodeId, setStartNodeId] = useState<string>("1");
  const [activeId, setActiveId] = useState<string>("2");
  const [workflowId, setWorkflowId] = useState<number | null>(null);
  const [workflowName, setWorkflowName] = useState("Northwind assistant");
  const [isPublished, setIsPublished] = useState(false);
  const [hasToken, setHasToken] = useState(false);
  const [tokenInput, setTokenInput] = useState("");
  const [showTokenModal, setShowTokenModal] = useState(false);
  const [showWorkflowsModal, setShowWorkflowsModal] = useState(false);
  const [savedWorkflows, setSavedWorkflows] = useState<WorkflowItem[]>([]);
  const [chat, setChat] = useState<ChatLine[]>([]);
  const [simNodeId, setSimNodeId] = useState<string | null>(null);
  const [simChoices, setSimChoices] = useState<string[]>([]);
  const [simComplete, setSimComplete] = useState(false);
  const [draft, setDraft] = useState("");
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [publishStatus, setPublishStatus] = useState<"idle" | "loading">("idle");
  const [templates, setTemplates] = useState<TemplateApi[]>([]);
  const [tab, setTab] = useState<"edit" | "test" | "analytics">("edit");
  const [analytics, setAnalytics] = useState<{
    users_total: number;
    messages_total: number;
    recent_messages: { direction: string; text: string; created_at: string | null }[];
  } | null>(null);
  const [usersList, setUsersList] = useState<BotUserItem[]>([]);
  const [copiedUrl, setCopiedUrl] = useState(false);

  const chatContainerRef = useRef<HTMLDivElement>(null);

  const active = useMemo(() => nodes.find((n) => n.id === activeId) ?? nodes[0] ?? initialNodes[0], [nodes, activeId]);

  // Fetch templates & saved workflows
  useEffect(() => {
    fetch(`${API_URL}/api/templates`)
      .then((r) => r.json())
      .then(setTemplates)
      .catch(() => undefined);
    fetchWorkflows();
  }, []);

  const fetchWorkflows = async () => {
    try {
      const res = await fetch(`${API_URL}/api/workflows`);
      if (res.ok) setSavedWorkflows(await res.json());
    } catch {
      /* ignore */
    }
  };

  // Scroll phone chat to bottom on new messages
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chat]);

  const [simState, setSimState] = useState<Record<string, unknown>>({});

  // Init chat in simulator
  const initChat = async (startId: string, currentNodes = nodes) => {
    try {
      const currentStart = currentNodes.some((n) => n.id === startId) ? startId : currentNodes[0]?.id ?? "1";
      const def = toFlowDefinition(currentNodes, currentStart);
      const res = await fetch(`${API_URL}/api/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ definition: def, message: "", current_node_id: currentStart, state: {} }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setChat(data.messages.map((t: string) => ({ from: "bot" as const, text: t })));
      setSimNodeId(data.current_node_id);
      setSimChoices(data.choices ?? []);
      setSimComplete(data.complete);
      setSimState(data.state ?? {});
    } catch {
      const startNode = currentNodes.find((n) => n.id === startId) ?? currentNodes[0];
      setChat([{ from: "bot", text: startNode?.text || "Запуск сценария…" }]);
    }
  };

  useEffect(() => {
    if (chat.length === 0) {
      initChat(startNodeId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startNodeId]);

  const addNode = (kind: NodeKind) => {
    const meta = kindMeta[kind];
    const numericIds = nodes.map((n) => parseInt(n.id, 10)).filter((x) => !Number.isNaN(x));
    const id = String((numericIds.length ? Math.max(...numericIds) : 0) + 1);
    const base: FlowNode = {
      id,
      kind,
      title: meta.titleRu,
      text:
        kind === "end"
          ? "Спасибо!"
          : kind === "condition"
          ? "Проверяем ответ…"
          : kind === "choice"
          ? "Выберите вариант:"
          : kind === "input"
          ? "Введите данные:"
          : "Новый текст",
      next_id: null,
      choices:
        kind === "choice"
          ? [
              { label: "Вариант 1", next_id: null },
              { label: "Вариант 2", next_id: null },
            ]
          : [],
      condition_value: "",
      true_next_id: null,
      false_next_id: null,
      variable_name: "",
    };
    setNodes([...nodes, base]);
    setActiveId(id);
    setSaveStatus("idle");
  };

  const updateActive = (patch: Partial<FlowNode>) => {
    setNodes(nodes.map((n) => (n.id === activeId ? { ...n, ...patch } : n)));
    setSaveStatus("idle");
  };

  const removeActive = () => {
    if (nodes.length <= 1) return;
    const nextNodes = nodes.filter((n) => n.id !== activeId);
    const cleaned = nextNodes.map((n) => ({
      ...n,
      next_id: n.next_id === activeId ? null : n.next_id,
      choices: n.choices.map((c) => (c.next_id === activeId ? { ...c, next_id: null } : c)),
      true_next_id: n.true_next_id === activeId ? null : n.true_next_id,
      false_next_id: n.false_next_id === activeId ? null : n.false_next_id,
    }));
    setNodes(cleaned);
    const newActive = cleaned[0].id;
    setActiveId(newActive);
    if (startNodeId === activeId) {
      setStartNodeId(newActive);
    }
  };

  const saveWorkflow = async () => {
    setSaveStatus("saving");
    const currentStart = nodes.some((n) => n.id === startNodeId) ? startNodeId : nodes[0].id;
    const def = toFlowDefinition(nodes, currentStart);
    try {
      const url = workflowId ? `${API_URL}/api/workflows/${workflowId}` : `${API_URL}/api/workflows`;
      const method = workflowId ? "PUT" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: workflowName,
          description: "BotForge scenario",
          definition: def,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setWorkflowId(data.id);
      setIsPublished(data.is_published);
      setHasToken(data.has_token);
      setSaveStatus("saved");
      fetchWorkflows();
      setTimeout(() => setSaveStatus("idle"), 1800);
      await initChat(currentStart, nodes);
      if (tab === "analytics") fetchAnalytics(data.id);
    } catch {
      setSaveStatus("error");
    }
  };

  const publishToggle = async () => {
    if (!workflowId) {
      alert("Сначала сохраните сценарий.");
      return;
    }
    setPublishStatus("loading");
    try {
      if (!isPublished) {
        const body: Record<string, string | null> = {};
        if (tokenInput.trim()) body.telegram_bot_token = tokenInput.trim();
        const res = await fetch(`${API_URL}/api/workflows/${workflowId}/publish`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error();
        const data = await res.json();
        setIsPublished(true);
        setHasToken(data.has_token);
        if (data.has_token) setTokenInput("");
      } else {
        const res = await fetch(`${API_URL}/api/workflows/${workflowId}/stop`, { method: "POST" });
        if (!res.ok) throw new Error();
        setIsPublished(false);
      }
      fetchWorkflows();
    } catch {
      alert("Не удалось переключить публикацию — проверьте токен и API.");
    } finally {
      setPublishStatus("idle");
    }
  };

  const loadTemplate = (tpl: TemplateApi) => {
    const mapped = fromDefinition(tpl.definition);
    setNodes(mapped);
    const startId = tpl.definition.start_id || mapped[0]?.id || "1";
    setStartNodeId(startId);
    setActiveId(startId);
    setWorkflowId(null);
    setIsPublished(false);
    setWorkflowName(tpl.title);
    setChat([]);
    setSimChoices([]);
    setSimComplete(false);
    setSimState({});
    setSaveStatus("idle");
    initChat(startId, mapped);
  };

  const loadExistingWorkflow = (wf: WorkflowItem) => {
    const mapped = fromDefinition(wf.definition);
    setNodes(mapped);
    const startId = wf.definition.start_id || mapped[0]?.id || "1";
    setStartNodeId(startId);
    setActiveId(startId);
    setWorkflowId(wf.id);
    setIsPublished(wf.is_published);
    setHasToken(wf.has_token);
    setWorkflowName(wf.name);
    setShowWorkflowsModal(false);
    setChat([]);
    setSimState({});
    setSaveStatus("idle");
    initChat(startId, mapped);
  };

  const createNewWorkflow = () => {
    setNodes(initialNodes);
    setStartNodeId("1");
    setActiveId("1");
    setWorkflowId(null);
    setIsPublished(false);
    setHasToken(false);
    setWorkflowName("Новый бот");
    setShowWorkflowsModal(false);
    setChat([]);
    setSimState({});
    setSaveStatus("idle");
    initChat("1", initialNodes);
  };

  const deleteCurrentWorkflow = async (id: number) => {
    if (!confirm("Вы уверены, что хотите удалить этот сценарий?")) return;
    try {
      const res = await fetch(`${API_URL}/api/workflows/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      fetchWorkflows();
      if (workflowId === id) {
        createNewWorkflow();
      }
    } catch {
      alert("Не удалось удалить сценарий.");
    }
  };

  const fetchAnalytics = async (wid?: number | null) => {
    const id = wid ?? workflowId;
    if (!id) return;
    try {
      const res = await fetch(`${API_URL}/api/workflows/${id}/analytics`);
      if (res.ok) setAnalytics(await res.json());

      const usersRes = await fetch(`${API_URL}/api/workflows/${id}/users`);
      if (usersRes.ok) setUsersList(await usersRes.json());
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    if (tab === "analytics") fetchAnalytics();
  }, [tab, workflowId]);

  const send = async (value = draft) => {
    const text = value.trim();
    if (!text) return;
    setChat((c) => [...c, { from: "user", text }]);
    setDraft("");
    try {
      const currentStart = nodes.some((n) => n.id === startNodeId) ? startNodeId : nodes[0]?.id ?? "1";
      const def = toFlowDefinition(nodes, currentStart);
      const res = await fetch(`${API_URL}/api/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ definition: def, message: text, current_node_id: simNodeId, state: simState }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setChat((c) => [...c, ...data.messages.map((t: string) => ({ from: "bot" as const, text: t }))]);
      setSimNodeId(data.current_node_id);
      setSimChoices(data.choices ?? []);
      setSimComplete(data.complete);
      setSimState(data.state ?? {});
    } catch {
      setChat((c) => [...c, { from: "bot", text: "Ошибка симулятора — проверьте связь с API." }]);
    }
  };

  const resetChat = () => {
    setSimState({});
    initChat(startNodeId, nodes);
  };

  const webhookUrl = workflowId
    ? `${API_URL}/api/telegram/webhook/${workflowId}`
    : `${API_URL}/api/telegram/webhook`;

  const copyWebhookUrl = () => {
    navigator.clipboard.writeText(webhookUrl);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark"><Bot size={20} /></span>
          <span>BotForge</span>
          <span className="muted" style={{ fontWeight: 500, marginLeft: 8, fontSize: 12 }}>v0.1.0</span>
        </div>
        <div className="project-name">
          <button
            className="button ghost"
            style={{ height: 32, padding: "0 8px", fontSize: 12 }}
            onClick={() => setShowWorkflowsModal(true)}
            title="Открыть список сценариев"
          >
            <FolderOpen size={14} /> Мои боты ({savedWorkflows.length})
          </button>
          <span className="status-dot" style={{ background: isPublished ? "#22c55e" : "#f2a13a" }} />
          <input
            value={workflowName}
            onChange={(e) => setWorkflowName(e.target.value)}
            style={{ border: 0, background: "transparent", fontWeight: 600, width: 170, outline: "none" }}
          />
          <span className="muted">{isPublished ? "Опубликован" : "Черновик"}{workflowId ? ` · #${workflowId}` : ""}</span>
        </div>
        <div className="actions">
          <button className="button ghost" onClick={saveWorkflow}>
            {saveStatus === "saved" ? <Check size={17} /> : <Save size={17} />}
            {saveStatus === "saving" ? "Сохранение…" : saveStatus === "saved" ? "Сохранено" : saveStatus === "error" ? "Повторить" : "Сохранить"}
          </button>
          <button className="button primary" onClick={publishToggle} disabled={publishStatus === "loading"} title={hasToken ? "Токен подключён" : "Подключите токен в карточке Telegram"}>
            {isPublished ? <Pause size={16} /> : <Play size={16} fill="currentColor" />} {isPublished ? "Остановить" : "Опубликовать"}
          </button>
        </div>
      </header>

      <section className="workspace">
        <aside className="palette">
          <div>
            <p className="eyebrow">Блоки</p>
            <h1>Соберите сценарий</h1>
            <p className="muted copy">Добавляйте узлы и настраивайте переходы в инспекторе.</p>
          </div>
          <div className="block-list">
            {(Object.keys(kindMeta) as NodeKind[]).map((kind) => {
              const { titleRu, icon: Icon } = kindMeta[kind];
              return (
                <button className="palette-item" key={kind} onClick={() => addNode(kind)}>
                  <span><Icon size={18} /></span><strong>{titleRu}</strong><Plus size={16} />
                </button>
              );
            })}
          </div>

          <div style={{ marginTop: 18 }}>
            <p className="eyebrow"><LayoutTemplate size={12} style={{ verticalAlign: -2, marginRight: 6 }} />Шаблоны</p>
            <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
              {templates.length === 0 ? (
                <small className="muted">Загрузка…</small>
              ) : (
                templates.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => loadTemplate(t)}
                    className="palette-item"
                    style={{ height: "auto", padding: "10px 12px", gridTemplateColumns: "1fr auto" }}
                  >
                    <span style={{ display: "grid", gap: 2, background: "transparent", width: "auto", height: "auto", placeItems: "start" }}>
                      <strong style={{ fontSize: 13 }}>{t.title}</strong>
                      <small style={{ color: "#737c90", fontSize: 11 }}>{t.description}</small>
                    </span>
                    <ChevronRight size={16} />
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="telegram-card" onClick={() => setShowTokenModal(true)} style={{ cursor: "pointer", marginTop: 18 }}>
            <span className="tg-icon"><Send size={17} /></span>
            <div>
              <strong>{hasToken ? "Telegram подключён" : "Подключить Telegram"}</strong>
              <small>{hasToken ? "токен сохранён" : "по токену @BotFather"} · {isPublished ? "опубликован" : "черновик"}</small>
            </div>
            {hasToken ? <Check size={17} /> : <KeyRound size={17} />}
          </div>
        </aside>

        <section className="canvas" aria-label="Conversation workflow">
          <div className="canvas-toolbar">
            <span>{workflowName} · {nodes.length} блоков</span>
            <span className="muted">Стартовый блок: #{startNodeId}</span>
          </div>
          <div className="flow">
            {nodes.map((node, index) => {
              const Meta = kindMeta[node.kind];
              const Icon = Meta.icon;
              const isStart = node.id === startNodeId;
              return (
                <div className="flow-row" key={node.id}>
                  <button className={`node ${activeId === node.id ? "active" : ""}`} onClick={() => setActiveId(node.id)}>
                    <span className={`node-type ${node.kind}`}><Icon size={16} /></span>
                    <span className="node-body">
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <small>{Meta.titleRu} · #{node.id}</small>
                        {isStart && (
                          <span style={{ fontSize: 10, background: "#dbeafe", color: "#1e40af", padding: "2px 6px", borderRadius: 4, fontWeight: 700 }}>
                            СТАРТ
                          </span>
                        )}
                      </div>
                      <strong>{node.title}</strong>
                      <span>{node.text}</span>
                      {node.kind === "choice" && node.choices.length > 0 && (
                        <em>{node.choices.map((c) => `${c.label} → ${c.next_id ?? "—"}`).join(" · ")}</em>
                      )}
                      {node.kind === "condition" && (
                        <em>если “{node.condition_value || "…"}” → #{node.true_next_id ?? "—"} / иначе #{node.false_next_id ?? "—"}</em>
                      )}
                      {node.kind !== "choice" && node.kind !== "condition" && node.next_id && <em>→ #{node.next_id}</em>}
                    </span>
                    <ChevronRight size={18} />
                  </button>
                  {index < nodes.length - 1 && <span className="connector" />}
                </div>
              );
            })}
          </div>
        </section>

        <aside className="inspector">
          <div className="tabs">
            <button className={tab === "edit" ? "selected" : ""} onClick={() => setTab("edit")}>Редактор</button>
            <button className={tab === "test" ? "selected" : ""} onClick={() => setTab("test")}>Тест</button>
            <button className={tab === "analytics" ? "selected" : ""} onClick={() => setTab("analytics")}>
              <BarChart3 size={14} style={{ verticalAlign: -2, marginRight: 4 }} />Аналитика
            </button>
          </div>

          {tab === "edit" && active && (
            <div className="form-panel">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <p className="eyebrow">Выбранный блок</p>
                  <h2>{active.title} <small style={{ color: "#8a92a6", fontWeight: 500 }}>· #{active.id}</small></h2>
                </div>
                {active.id !== startNodeId ? (
                  <button
                    className="button ghost"
                    style={{ height: 30, padding: "0 8px", fontSize: 11 }}
                    onClick={() => setStartNodeId(active.id)}
                  >
                    <Flag size={12} /> Сделать стартом
                  </button>
                ) : (
                  <span style={{ fontSize: 11, color: "#2563eb", fontWeight: 600 }}>🚩 Стартовый блок</span>
                )}
              </div>

              <label>
                Заголовок
                <input
                  value={active.title}
                  onChange={(e) => updateActive({ title: e.target.value })}
                  maxLength={80}
                  style={{ width: "100%", border: "1px solid #dfe3ed", borderRadius: 9, padding: "10px 11px" }}
                />
              </label>
              <label>
                Текст бота
                <textarea
                  value={active.text}
                  onChange={(e) => updateActive({ text: e.target.value })}
                  maxLength={1000}
                />
              </label>

              {active.kind === "message" && (
                <label>
                  Следующий шаг
                  <select value={active.next_id ?? ""} onChange={(e) => updateActive({ next_id: e.target.value || null })}>
                    <option value="">Завершить</option>
                    {nodes.filter((n) => n.id !== active.id).map((n) => <option key={n.id} value={n.id}>#{n.id} · {n.title}</option>)}
                  </select>
                </label>
              )}
              {active.kind === "input" && (
                <>
                  <label>
                    Имя переменной
                    <input
                      value={active.variable_name ?? ""}
                      onChange={(e) => updateActive({ variable_name: e.target.value })}
                      placeholder="например, name"
                      maxLength={80}
                      style={{ width: "100%", border: "1px solid #dfe3ed", borderRadius: 9, padding: "10px 11px" }}
                    />
                  </label>
                  <small className="muted">Используйте значение дальше как {"{{name}}"}.</small>
                  <label>
                    Куда дальше
                    <select value={active.next_id ?? ""} onChange={(e) => updateActive({ next_id: e.target.value || null })}>
                      <option value="">Завершить</option>
                      {nodes.filter((n) => n.id !== active.id).map((n) => <option key={n.id} value={n.id}>#{n.id} · {n.title}</option>)}
                    </select>
                  </label>
                </>
              )}
              {active.kind === "end" && <p className="muted" style={{ fontSize: 13, marginTop: 8 }}>Завершает ветку сценария.</p>}

              {active.kind === "choice" && (
                <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
                  <strong style={{ fontSize: 13 }}>Кнопки выбора</strong>
                  {active.choices.map((c, i) => (
                    <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 110px auto", gap: 6 }}>
                      <input
                        placeholder="Текст кнопки"
                        value={c.label}
                        onChange={(e) => {
                          const next = [...active.choices];
                          next[i] = { ...c, label: e.target.value };
                          updateActive({ choices: next });
                        }}
                        style={{ border: "1px solid #dfe3ed", borderRadius: 8, padding: "8px 9px" }}
                      />
                      <select
                        value={c.next_id ?? ""}
                        onChange={(e) => {
                          const next = [...active.choices];
                          next[i] = { ...c, next_id: e.target.value || null };
                          updateActive({ choices: next });
                        }}
                      >
                        <option value="">—</option>
                        {nodes.filter((n) => n.id !== active.id).map((n) => <option key={n.id} value={n.id}>#{n.id}</option>)}
                      </select>
                      <button onClick={() => updateActive({ choices: active.choices.filter((_, idx) => idx !== i) })} style={{ border: 0, background: "transparent" }}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                  <button className="button ghost" style={{ height: 36 }} onClick={() => updateActive({ choices: [...active.choices, { label: "Новый вариант", next_id: null }] })}>
                    <Plus size={14} /> Добавить кнопку
                  </button>
                </div>
              )}

              {active.kind === "condition" && (
                <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
                  <label>
                    Подстрока для проверки
                    <input
                      value={active.condition_value}
                      onChange={(e) => updateActive({ condition_value: e.target.value })}
                      placeholder="напр. @, +, да"
                      style={{ width: "100%", border: "1px solid #dfe3ed", borderRadius: 9, padding: "10px 11px" }}
                    />
                  </label>
                  <label>
                    Если содержит →
                    <select value={active.true_next_id ?? ""} onChange={(e) => updateActive({ true_next_id: e.target.value || null })}>
                      <option value="">Завершить</option>
                      {nodes.filter((n) => n.id !== active.id).map((n) => <option key={n.id} value={n.id}>#{n.id} · {n.title}</option>)}
                    </select>
                  </label>
                  <label>
                    Иначе →
                    <select value={active.false_next_id ?? ""} onChange={(e) => updateActive({ false_next_id: e.target.value || null })}>
                      <option value="">Завершить</option>
                      {nodes.filter((n) => n.id !== active.id).map((n) => <option key={n.id} value={n.id}>#{n.id} · {n.title}</option>)}
                    </select>
                  </label>
                  <small className="muted">Проверяет предыдущий ввод пользователя или текущее сообщение.</small>
                </div>
              )}

              <button className="button ghost" onClick={removeActive} style={{ marginTop: 16, color: "#a33" }}>
                <Trash2 size={14} /> Удалить блок
              </button>
            </div>
          )}

          {tab === "test" && (
            <div className="phone">
              <div className="phone-head">
                <span className="avatar"><Bot size={17} /></span>
                <div>
                  <strong>{workflowName}</strong>
                  <small>{isPublished ? "опубликован" : "черновик"} · {workflowId ? `id #${workflowId}` : "не сохранён"}</small>
                </div>
                <button onClick={resetChat} style={{ marginLeft: "auto", border: 0, background: "#f4f6f9", borderRadius: 8, padding: "6px 10px", fontSize: 12 }}>
                  Сброс
                </button>
              </div>
              <div className="chat" ref={chatContainerRef}>
                {chat.map((line, idx) => <div key={idx} className={`bubble ${line.from}`}>{line.text}</div>)}
                {!workflowId && <div className="muted" style={{ fontSize: 11, textAlign: "center", padding: 6 }}>Сохраните сценарий для запуска через движок.</div>}
                {simChoices.length > 0 && !simComplete && (
                  <div className="quick-actions">
                    {simChoices.map((c) => <button key={c} onClick={() => send(c)}>{c}</button>)}
                  </div>
                )}
                {simComplete && <div className="muted" style={{ fontSize: 11, textAlign: "center" }}>Диалог завершён — нажмите Сброс.</div>}
              </div>
              <div className="composer">
                <input
                  aria-label="Message"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder="Введите сообщение…"
                  disabled={simComplete}
                />
                <button aria-label="Send" onClick={() => send()}><Send size={17} /></button>
              </div>
            </div>
          )}

          {tab === "analytics" && (
            <div className="form-panel">
              <p className="eyebrow">Аналитика и пользователи</p>
              {!workflowId ? (
                <p className="muted" style={{ fontSize: 13 }}>Сохраните сценарий — аналитика появится после первых диалогов в Telegram.</p>
              ) : !analytics ? (
                <p className="muted">Загрузка…</p>
              ) : (
                <div style={{ display: "grid", gap: 14 }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    <div style={{ background: "#f4f6f9", borderRadius: 10, padding: 12 }}>
                      <small className="muted">Пользователей</small>
                      <div style={{ fontWeight: 700, fontSize: 22 }}>{analytics.users_total}</div>
                    </div>
                    <div style={{ background: "#f4f6f9", borderRadius: 10, padding: 12 }}>
                      <small className="muted">Сообщений</small>
                      <div style={{ fontWeight: 700, fontSize: 22 }}>{analytics.messages_total}</div>
                    </div>
                  </div>

                  {usersList.length > 0 && (
                    <div>
                      <strong style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 5 }}>
                        <Users size={14} /> Пользователи ({usersList.length})
                      </strong>
                      <div style={{ display: "grid", gap: 5, marginTop: 6, maxHeight: 110, overflowY: "auto" }}>
                        {usersList.map((u) => (
                          <div key={u.id} style={{ fontSize: 11, padding: "6px 8px", background: "#f8fafc", borderRadius: 6, display: "flex", justifyContent: "space-between" }}>
                            <span>@{u.username || `id:${u.telegram_user_id}`}</span>
                            <span className="muted">{u.last_seen_at ? new Date(u.last_seen_at).toLocaleTimeString() : ""}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div>
                    <strong style={{ fontSize: 13 }}>Последние сообщения</strong>
                    {analytics.recent_messages.length === 0 ? (
                      <p className="muted" style={{ fontSize: 12 }}>Пока нет данных — запустите бота в Telegram и напишите /start.</p>
                    ) : (
                      <div style={{ display: "grid", gap: 6, marginTop: 8, maxHeight: 180, overflowY: "auto" }}>
                        {analytics.recent_messages.slice(0, 10).map((m, i) => (
                          <div key={i} style={{ fontSize: 12, padding: "8px 10px", background: m.direction === "in" ? "#eef1ff" : "#f0fdf4", borderRadius: 8 }}>
                            <small className="muted">{m.direction === "in" ? "Входящее" : "Исходящее"} · {m.created_at ? new Date(m.created_at).toLocaleTimeString() : ""}</small>
                            <div>{m.text.slice(0, 120)}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === "edit" && active && (
            <div className="phone" style={{ marginTop: 0, borderTop: "1px solid #e4e8f1", borderRadius: 0 }}>
              <div className="phone-head">
                <span className="avatar"><Bot size={17} /></span>
                <div><strong>Предпросмотр блока</strong><small>#{active.id} · {active.title}</small></div>
              </div>
              <div className="chat"><div className="bubble bot">{active.text || "Текст блока…"}</div></div>
            </div>
          )}
        </aside>
      </section>

      {/* Workflows Modal */}
      {showWorkflowsModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(16,20,35,.45)", display: "grid", placeItems: "center", zIndex: 50 }} onClick={() => setShowWorkflowsModal(false)}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 480, background: "#fff", borderRadius: 14, padding: 22, boxShadow: "0 18px 40px rgba(0,0,0,.18)", maxHeight: "80vh", overflowY: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <h3 style={{ margin: 0, fontFamily: "Manrope" }}>Сохраненные сценарии</h3>
              <button className="button primary" style={{ height: 32, fontSize: 12 }} onClick={createNewWorkflow}>
                <Plus size={14} /> Создать новый
              </button>
            </div>
            {savedWorkflows.length === 0 ? (
              <p className="muted" style={{ fontSize: 13 }}>Нет сохранённых сценариев. Нажмите «Сохранить» в правом верхнем углу.</p>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {savedWorkflows.map((wf) => (
                  <div
                    key={wf.id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "10px 12px",
                      border: "1px solid #e4e8f1",
                      borderRadius: 10,
                      background: wf.id === workflowId ? "#f5f3ff" : "#fff",
                      borderColor: wf.id === workflowId ? "#8476f8" : "#e4e8f1",
                    }}
                  >
                    <div style={{ cursor: "pointer", flex: 1 }} onClick={() => loadExistingWorkflow(wf)}>
                      <strong>{wf.name}</strong>
                      <div style={{ fontSize: 11, color: "#8a92a6", marginTop: 2 }}>
                        #{wf.id} · {wf.is_published ? "🟢 Опубликован" : "🟡 Черновик"} · {wf.updated_at ? new Date(wf.updated_at).toLocaleDateString() : ""}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="button ghost" style={{ height: 30, padding: "0 8px", fontSize: 11 }} onClick={() => loadExistingWorkflow(wf)}>
                        Открыть
                      </button>
                      <button onClick={() => deleteCurrentWorkflow(wf.id)} style={{ border: 0, background: "transparent", color: "#b33", cursor: "pointer" }} title="Удалить">
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
              <button className="button ghost" onClick={() => setShowWorkflowsModal(false)}>Закрыть</button>
            </div>
          </div>
        </div>
      )}

      {/* Telegram Token Modal */}
      {showTokenModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(16,20,35,.45)", display: "grid", placeItems: "center", zIndex: 50 }} onClick={() => setShowTokenModal(false)}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 460, background: "#fff", borderRadius: 14, padding: 22, boxShadow: "0 18px 40px rgba(0,0,0,.18)" }}>
            <h3 style={{ margin: "0 0 6px", fontFamily: "Manrope" }}>Подключение Telegram</h3>
            <p className="muted" style={{ fontSize: 13, margin: 0 }}>Вставьте токен бота от @BotFather. Токен сохранится для текущего сценария.</p>
            <input
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="123456789:AAH..."
              style={{ width: "100%", marginTop: 14, border: "1px solid #dfe3ed", borderRadius: 9, padding: "10px 11px" }}
            />

            <div style={{ marginTop: 14, background: "#f8fafc", padding: "10px 12px", borderRadius: 8, fontSize: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>URL для Webhook:</div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <code style={{ fontSize: 11, wordBreak: "break-all", background: "#e2e8f0", padding: "2px 6px", borderRadius: 4, flex: 1 }}>
                  {webhookUrl}
                </code>
                <button className="button ghost" style={{ height: 28, padding: "0 6px" }} onClick={copyWebhookUrl} title="Скопировать URL">
                  {copiedUrl ? <Check size={13} color="green" /> : <Copy size={13} />}
                </button>
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 18 }}>
              <button className="button ghost" onClick={() => setShowTokenModal(false)}>Отмена</button>
              <button
                className="button primary"
                onClick={async () => {
                  if (workflowId && tokenInput.trim()) {
                    try {
                      const res = await fetch(`${API_URL}/api/workflows/${workflowId}/publish`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ telegram_bot_token: tokenInput.trim() }),
                      });
                      if (!res.ok) throw new Error(`HTTP ${res.status}`);
                      const data = await res.json();
                      setHasToken(data.has_token);
                      setIsPublished(data.is_published);
                      setTokenInput("");
                      setShowTokenModal(false);
                      fetchWorkflows();
                    } catch {
                      alert("Не удалось сохранить токен. Проверьте сценарий, токен и API.");
                    }
                  }
                }}
              >
                <KeyRound size={16} /> Сохранить токен
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
