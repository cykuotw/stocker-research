import { useDeferredValue, useEffect, useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Empty,
  EmptyHeader,
  EmptyTitle,
  EmptyDescription,
} from "@/components/ui/empty";
import { JsonView } from "./json-view";
import { RuntimeClient } from "@/runtime/client";
import {
  object,
  type Run,
  type RuntimeEvent,
  type StateView,
  type Comparison,
} from "@/runtime/types";

function EmptyPanel({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}
function EventDetail({ event }: { event: RuntimeEvent }) {
  const payload = object(event.payload);
  const data = object(payload.data);
  const inspection = object(payload.inspection);
  return (
    <section
      className="event-detail"
      aria-label="Event detail"
    >
      <div className="section-heading">
        <h3>{event.kind}</h3>
        <Badge variant="outline">#{event.event_id}</Badge>
      </div>
      <dl className="metadata">
        {["node", "model", "skill", "tool", "duration_ms", "usage"].map(
          (key) => (
            <div key={key}>
              <dt>{key.replaceAll("_", " ")}</dt>
              <dd>
                {inspection[key] == null
                  ? "Unavailable"
                  : typeof inspection[key] === "object"
                    ? JSON.stringify(inspection[key])
                    : String(inspection[key])}
              </dd>
            </div>
          ),
        )}
        <div>
          <dt>Recorded</dt>
          <dd>{new Date(event.created_at).toLocaleString()}</dd>
        </div>
        <div>
          <dt>Run</dt>
          <dd className="identifier">{event.run_id}</dd>
        </div>
      </dl>
      <Tabs defaultValue="event">
        <TabsList>
          <TabsTrigger value="event">Event</TabsTrigger>
          <TabsTrigger value="request">Request</TabsTrigger>
          <TabsTrigger value="response">Response</TabsTrigger>
        </TabsList>
        <TabsContent value="event">
          <JsonView
            value={event}
            label="Event payload"
          />
        </TabsContent>
        <TabsContent value="request">
          <JsonView
            value={data.input ?? null}
            label="Recorded input"
          />
        </TabsContent>
        <TabsContent value="response">
          <JsonView
            value={data.output ?? null}
            label="Recorded output"
          />
        </TabsContent>
      </Tabs>
    </section>
  );
}
function EventInspector({
  events,
  trace,
}: {
  events: RuntimeEvent[];
  trace: boolean;
}) {
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [visibleLimit, setVisibleLimit] = useState(200);
  const deferred = useDeferredValue(filter.toLowerCase());
  const spans = new Map<string, RuntimeEvent>();
  events.forEach((event) => {
    const payload = object(event.payload);
    if (typeof payload.run_id === "string") {
      const spanId = event.run_id + ":" + payload.run_id;
      const previous = spans.get(spanId);
      if (!previous || event.kind.endsWith("_end")) spans.set(spanId, event);
    }
  });
  const visible = (trace ? [...spans.values()] : events).filter((event) =>
    JSON.stringify({
      kind: event.kind,
      ...(object(event.payload).inspection as object),
      name: object(event.payload).name,
    })
      .toLowerCase()
      .includes(deferred),
  );
  const selectedEvent = events.find((event) => event.event_id === selected);
  return (
    <div className="event-inspector">
      <Input
        aria-label={trace ? "Filter trace" : "Filter events"}
        placeholder="Filter by node, tool, model, or event…"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
      />
      <p className="panel-note">
        {trace
          ? "Observed execution hierarchy · one row per span"
          : `${events.length} durable events · ordered by event ID`}
      </p>
      <div
        className="event-list"
        aria-label={trace ? "Execution trace" : "Execution events"}
      >
        {visible.length === 0 ? (
          <EmptyPanel
            title={events.length ? "No matching events" : "No events yet"}
            description="Execution events appear here when a run starts."
          />
        ) : (
          visible.slice(-visibleLimit).map((event) => {
            const payload = object(event.payload);
            const inspection = object(payload.inspection);
            const parents = Array.isArray(payload.parent_ids)
              ? payload.parent_ids.length
              : 0;
            return (
              <button
                className="event-row"
                style={
                  trace
                    ? { paddingLeft: `${12 + Math.min(parents, 6) * 14}px` }
                    : undefined
                }
                key={event.event_id}
                onClick={() => setSelected(event.event_id)}
                aria-pressed={selected === event.event_id}
              >
                <span className="event-name">
                  {trace ? String(payload.name ?? event.kind) : event.kind}
                </span>
                <span className="event-context">
                  {String(inspection.node ?? inspection.tool ?? "runtime")}
                </span>
                <span className="event-time">
                  {trace && inspection.duration_ms != null
                    ? `${inspection.duration_ms} ms`
                    : new Date(event.created_at).toLocaleTimeString()}
                </span>
              </button>
            );
          })
        )}
      </div>
      {visible.length > visibleLimit ? (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setVisibleLimit((value) => value + 200)}
        >
          Load earlier events ({visible.length - visibleLimit})
        </Button>
      ) : null}
      {selectedEvent ? (
        <EventDetail event={selectedEvent} />
      ) : (
        <p className="panel-note">
          Select an event to inspect its payload, input, and output.
        </p>
      )}
    </div>
  );
}
function Checkpoints({
  client,
  sessionId,
  checkpoints,
}: {
  client: RuntimeClient;
  sessionId: string;
  checkpoints: StateView[];
}) {
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [detail, setDetail] = useState<StateView | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!left) return;
    const controller = new AbortController();
    client
      .checkpoint(sessionId, left, controller.signal)
      .then(setDetail)
      .catch((error) => {
        if (!controller.signal.aborted) setError(String(error));
      });
    return () => controller.abort();
  }, [client, sessionId, left]);
  const compare = async () => {
    setLoading(true);
    setError("");
    try {
      setComparison(await client.compare(sessionId, left, right));
    } catch (error) {
      setError(String(error));
    } finally {
      setLoading(false);
    }
  };
  if (!checkpoints.length)
    return (
      <EmptyPanel
        title="No checkpoints yet"
        description="Checkpoints appear as LangGraph executes a session."
      />
    );
  const options = checkpoints
    .filter((item) => item.checkpoint_id)
    .map((item) => (
      <option
        key={item.checkpoint_id!}
        value={item.checkpoint_id!}
      >
        {item.created_at
          ? new Date(item.created_at).toLocaleString()
          : "Checkpoint"}{" "}
        · {item.checkpoint_id!.slice(-8)}
      </option>
    ));
  return (
    <div className="checkpoint-inspector">
      <p className="panel-note">
        Read-only snapshots · newest first. The conversation shows current
        state.
      </p>
      <label>
        Inspect checkpoint
        <select
          value={left}
          onChange={(event) => {
            setLeft(event.target.value);
            setDetail(null);
            setComparison(null);
          }}
        >
          <option value="">Select a checkpoint</option>
          {options}
        </select>
      </label>
      {detail ? (
        <JsonView
          value={detail}
          label="Historical checkpoint"
        />
      ) : null}
      <label>
        Compare with
        <select
          value={right}
          onChange={(event) => {
            setRight(event.target.value);
            setComparison(null);
          }}
        >
          <option value="">Select another checkpoint</option>
          {options}
        </select>
      </label>
      <Button
        variant="outline"
        disabled={!left || !right || left === right || loading}
        onClick={() => void compare()}
      >
        {loading ? "Comparing…" : "Compare checkpoints"}
      </Button>
      {error ? <p role="alert">{error}</p> : null}
      {comparison ? (
        <>
          <p>Changed keys: {comparison.changed_keys.join(", ") || "None"}</p>
          <JsonView
            value={comparison}
            label="Checkpoint comparison"
          />
        </>
      ) : null}
    </div>
  );
}
export function Inspection({
  client,
  sessionId,
  runs,
  events,
  state,
  checkpoints,
  streamStatus,
}: {
  client: RuntimeClient;
  sessionId: string;
  runs: Run[];
  events: RuntimeEvent[];
  state: StateView | null;
  checkpoints: StateView[];
  streamStatus: string;
}) {
  const [runId, setRunId] = useState("all");
  const visible =
    runId === "all" ? events : events.filter((event) => event.run_id === runId);
  const selectedRun = runs.find((run) => run.run_id === runId);
  return (
    <aside
      className="inspection"
      aria-label="Runtime inspector"
    >
      <div className="section-heading">
        <h2>Inspector</h2>
        <Badge variant="outline">{streamStatus}</Badge>
      </div>
      <label className="run-picker">
        Run
        <select
          aria-label="Inspect run"
          value={runId}
          onChange={(event) => setRunId(event.target.value)}
        >
          <option value="all">All runs ({runs.length})</option>
          {runs.map((run, index) => (
            <option
              key={run.run_id}
              value={run.run_id}
            >
              Run {runs.length - index} · {run.action} · {run.status}
            </option>
          ))}
        </select>
      </label>
      {selectedRun ? (
        <details className="run-detail">
          <summary>Run record</summary>
          <JsonView
            value={selectedRun}
            label="Run record"
          />
        </details>
      ) : null}
      <Tabs
        defaultValue="events"
        className="inspector-tabs"
      >
        <TabsList className="inspection-tab-list">
          <TabsTrigger value="events">Events</TabsTrigger>
          <TabsTrigger value="trace">Trace</TabsTrigger>
          <TabsTrigger value="state">State</TabsTrigger>
          <TabsTrigger value="checkpoints">Checkpoints</TabsTrigger>
        </TabsList>
        <TabsContent value="events">
          <EventInspector
            events={visible}
            trace={false}
          />
        </TabsContent>
        <TabsContent value="trace">
          <EventInspector
            events={visible}
            trace
          />
        </TabsContent>
        <TabsContent value="state">
          <p className="panel-note">
            Current LangGraph checkpoint · messages, next nodes, and interrupts.
          </p>
          <JsonView
            value={state}
            label="Current state"
          />
        </TabsContent>
        <TabsContent value="checkpoints">
          <Checkpoints
            client={client}
            sessionId={sessionId}
            checkpoints={checkpoints}
          />
        </TabsContent>
      </Tabs>
    </aside>
  );
}
