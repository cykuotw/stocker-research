import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Plus, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  Empty,
  EmptyHeader,
  EmptyTitle,
  EmptyDescription,
} from "@/components/ui/empty";
import { Field, FieldLabel, FieldGroup } from "@/components/ui/field";
import { RuntimeClient } from "@/runtime/client";
import {
  isActive,
  mergeEvents,
  type Assistant,
  type Session,
  type Run,
  type RuntimeEvent,
  type StateView,
  type Submission,
} from "@/runtime/types";
import { Conversation } from "./conversation";
import { Inspection } from "./inspection";

function Failure({ error, retry }: { error: string; retry?: () => void }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>Unable to complete the request</AlertTitle>
      <AlertDescription>
        {error}
        {retry ? (
          <Button
            variant="outline"
            size="sm"
            onClick={retry}
          >
            Retry connection
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}
function sessionKey(client: RuntimeClient) {
  return `stocker.studio.v1.session:${client.base}`;
}
function remembered(client: RuntimeClient) {
  try {
    return localStorage.getItem(sessionKey(client));
  } catch {
    return null;
  }
}
function saveSelection(client: RuntimeClient, id: string) {
  try {
    localStorage.setItem(sessionKey(client), id);
  } catch {
    /* storage may be unavailable */
  }
}
function SessionWorkspace({
  client,
  session,
}: {
  client: RuntimeClient;
  session: Session;
}) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [events, setEvents] = useState<RuntimeEvent[]>([]);
  const [state, setState] = useState<StateView | null>(null);
  const [checkpoints, setCheckpoints] = useState<StateView[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [streamStatus, setStreamStatus] = useState("Saved");
  const [pending, setPending] = useState<Submission | null>(null);
  const version = useRef(0);
  const alive = useRef(true);
  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      const current = ++version.current;
      const [runRows, eventRows, snapshot, history] = await Promise.all([
        client.runs(session.session_id, signal),
        client.events(session.session_id, signal),
        client.state(session.session_id, signal),
        client.checkpoints(session.session_id, signal),
      ]);
      if (!alive.current || signal?.aborted || current !== version.current)
        return;
      setRuns(
        runRows.sort(
          (a, b) =>
            b.created_at.localeCompare(a.created_at) ||
            b.run_id.localeCompare(a.run_id),
        ),
      );
      setEvents((previous) => mergeEvents(previous, eventRows));
      setState(snapshot);
      setCheckpoints(history);
      setLoading(false);
    },
    [client, session.session_id],
  );
  useEffect(() => {
    alive.current = true;
    const controller = new AbortController();
    refresh(controller.signal).catch((error) => {
      if (!controller.signal.aborted) {
        setError(String(error));
        setLoading(false);
      }
    });
    return () => {
      alive.current = false;
      controller.abort();
    };
  }, [refresh]);
  const latest = runs[0];
  const activeId = isActive(latest) ? latest!.run_id : null;
  useEffect(() => {
    if (!activeId) return;
    const controller = new AbortController();
    const buffer: RuntimeEvent[] = [];
    const flush = () => {
      if (buffer.length) {
        const batch = buffer.splice(0);
        setEvents((previous) => mergeEvents(previous, batch));
      }
    };
    const interval = setInterval(flush, 100);
    void client
      .observe(
        activeId,
        0,
        controller.signal,
        (event) => {
          buffer.push(event);
        },
        (status) => {
          setStreamStatus(status);
          if (status === "Saved")
            void refresh(controller.signal).catch((error) => {
              if (!controller.signal.aborted) setError(String(error));
            });
        },
      )
      .catch((error) => {
        if (!controller.signal.aborted) {
          setError(String(error));
          setStreamStatus("Disconnected");
        }
      });
    // Checkpoints are authoritative for conversation content. Poll while active.
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        await refresh(controller.signal);
      } catch (error) {
        if (!controller.signal.aborted) setError(String(error));
      }
      if (!controller.signal.aborted)
        timer = setTimeout(() => void poll(), 1000);
    };
    timer = setTimeout(() => void poll(), 1000);
    return () => {
      controller.abort();
      clearInterval(interval);
      clearTimeout(timer);
      flush();
    };
  }, [activeId, client, refresh]);
  const submit = async (body: Submission): Promise<boolean> => {
    setBusy(true);
    setError("");
    setPending(body);
    try {
      const run = await client.submit(session.session_id, body);
      if (!alive.current) return false;
      setRuns((previous) => [
        run,
        ...previous.filter((item) => item.run_id !== run.run_id),
      ]);
      setPending(null);
      void refresh().catch((error) => {
        if (alive.current) setError(String(error));
      });
      return true;
    } catch (error) {
      if (alive.current) setError(String(error));
      return false;
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  const cancel = async () => {
    if (!latest) return;
    setBusy(true);
    setError("");
    try {
      await client.cancel(latest.run_id);
      await refresh();
    } catch (error) {
      if (alive.current) setError(String(error));
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  return (
    <div className="session-workspace">
      <header className="session-heading">
        <div>
          <h1>{session.title}</h1>
          <div className="session-identifiers">
            <Badge variant="outline">{session.graph_id}</Badge>
            <code title={session.session_id}>{session.session_id}</code>
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Refresh session"
          onClick={() => {
            setError("");
            void refresh().catch((error) => setError(String(error)));
          }}
        >
          <RefreshCw />
        </Button>
      </header>
      {error ? (
        <div className="session-error">
          <Failure error={error} />
        </div>
      ) : null}
      {loading ? (
        <div
          className="loading-session"
          aria-label="Loading session"
        >
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : (
        <div className="session-columns">
          <Conversation
            state={state}
            latest={latest}
            busy={busy}
            submit={submit}
            cancel={() => void cancel()}
            retry={pending ? () => submit(pending) : null}
          />
          <Inspection
            client={client}
            sessionId={session.session_id}
            runs={runs}
            events={events}
            state={state}
            checkpoints={checkpoints}
            streamStatus={activeId ? streamStatus : "Saved"}
          />
        </div>
      )}
    </div>
  );
}
export function Workspace({ url }: { url: string }) {
  const client = useMemo(() => new RuntimeClient(url), [url]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [graphs, setGraphs] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(() =>
    remembered(client),
  );
  const [graph, setGraph] = useState("");
  const [assistant, setAssistant] = useState("");
  const [title, setTitle] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      await client.connect(controller.signal);
      const [sessions, assistants, graphs] = await Promise.all([
        client.sessions(controller.signal),
        client.assistants(controller.signal),
        client.graphs(controller.signal),
      ]);
      if (controller.signal.aborted) return;
      setSessions(
        sessions.sort((a, b) => b.created_at.localeCompare(a.created_at)),
      );
      setAssistants(assistants);
      setGraphs(graphs);
      setGraph(graphs[0] ?? "");
      setSelected((previous) =>
        sessions.some((session) => session.session_id === previous)
          ? previous
          : null,
      );
      setLoading(false);
    };
    load().catch((error) => {
      if (!controller.signal.aborted) {
        setError(String(error));
        setLoading(false);
      }
    });
    return () => controller.abort();
  }, [client, attempt]);
  const reload = () => {
    setLoading(true);
    setError("");
    setAttempt((value) => value + 1);
  };
  const select = (id: string) => {
    setSelected(id);
    saveSelection(client, id);
  };
  const create = async () => {
    setBusy(true);
    setError("");
    try {
      let id = assistant;
      if (!id) {
        const created = await client.createAssistant(graph);
        id = created.assistant_id;
        setAssistants((previous) => [...previous, created]);
      }
      const session = await client.createSession(
        id,
        title.trim() || `New ${graph} session`,
      );
      setSessions((previous) => [session, ...previous]);
      select(session.session_id);
      setTitle("");
    } catch (error) {
      setError(String(error));
    } finally {
      setBusy(false);
    }
  };
  const session = sessions.find((item) => item.session_id === selected);
  return (
    <main className="workspace">
      <aside
        className="session-sidebar"
        aria-label="Sessions"
      >
        <div className="section-heading">
          <h2>Sessions</h2>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Refresh sessions"
            disabled={loading}
            onClick={reload}
          >
            <RefreshCw />
          </Button>
        </div>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="graph">Graph</FieldLabel>
            <select
              id="graph"
              value={graph}
              disabled={loading || busy}
              onChange={(event) => {
                setGraph(event.target.value);
                setAssistant("");
              }}
            >
              {graphs.map((id) => (
                <option
                  key={id}
                  value={id}
                >
                  {id}
                </option>
              ))}
            </select>
          </Field>
          <Field>
            <FieldLabel htmlFor="assistant">Assistant configuration</FieldLabel>
            <select
              id="assistant"
              value={assistant}
              onChange={(event) => setAssistant(event.target.value)}
            >
              <option value="">New default configuration</option>
              {assistants
                .filter((item) => item.graph_id === graph)
                .map((item) => (
                  <option
                    value={item.assistant_id}
                    key={item.assistant_id}
                  >
                    {item.name} · {item.assistant_id.slice(-6)}
                  </option>
                ))}
            </select>
          </Field>
          <Field>
            <FieldLabel htmlFor="session-title">Session name</FieldLabel>
            <Input
              id="session-title"
              placeholder="Optional name"
              maxLength={200}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </Field>
        </FieldGroup>
        <Button
          disabled={busy || loading || !graph}
          onClick={() => void create()}
        >
          <Plus data-icon="inline-start" />
          {busy ? "Creating…" : "New session"}
        </Button>
        <Input
          aria-label="Search sessions"
          placeholder="Search sessions…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        {loading ? (
          <div aria-label="Loading sessions">
            <Skeleton className="h-14 w-full" />
          </div>
        ) : null}
        {error ? (
          <Failure
            error={error}
            retry={reload}
          />
        ) : null}
        <nav
          className="session-list"
          aria-label="Saved sessions"
        >
          {sessions
            .filter((item) =>
              `${item.title} ${item.graph_id}`
                .toLowerCase()
                .includes(search.toLowerCase()),
            )
            .map((item) => (
              <button
                key={item.session_id}
                className="session-row"
                onClick={() => select(item.session_id)}
                aria-current={selected === item.session_id ? "page" : undefined}
              >
                <span>{item.title}</span>
                <small>
                  {item.graph_id} ·{" "}
                  {new Date(item.created_at).toLocaleDateString()}
                </small>
              </button>
            ))}
        </nav>
        {!loading && !sessions.length && !error ? (
          <p className="panel-note">
            Create a session to start testing. Saved sessions remain available
            after a server restart.
          </p>
        ) : null}
      </aside>
      {session ? (
        <SessionWorkspace
          key={session.session_id}
          client={client}
          session={session}
        />
      ) : (
        <section className="workspace-empty">
          <Empty>
            <EmptyHeader>
              <EmptyTitle>Your agent development workspace</EmptyTitle>
              <EmptyDescription>
                Create or select a session to chat with a LangGraph agent and
                inspect its execution.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        </section>
      )}
    </main>
  );
}
