import { lazy, Suspense, useState, type FormEvent } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { ArrowDown, Send, Square } from "lucide-react";
const MarkdownText = lazy(() =>
  import("@/components/thread/markdown-text").then((module) => ({
    default: module.MarkdownText,
  })),
);
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Field, FieldLabel, FieldGroup } from "@/components/ui/field";
import {
  Empty,
  EmptyHeader,
  EmptyTitle,
  EmptyDescription,
} from "@/components/ui/empty";
import { JsonView } from "./json-view";
import {
  object,
  isActive,
  type Json,
  type Run,
  type StateView,
  type Submission,
} from "@/runtime/types";

function JumpToLatest() {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();
  return !isAtBottom ? (
    <Button
      className="jump-to-latest"
      variant="outline"
      size="sm"
      onClick={() => void scrollToBottom()}
    >
      <ArrowDown data-icon="inline-start" />
      Latest message
    </Button>
  ) : null;
}
function textContent(value: Json | undefined): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value))
    return value
      .map((block) =>
        typeof block === "string" ? block : (object(block).text ?? ""),
      )
      .join("\n");
  return "";
}
export function Conversation({
  state,
  latest,
  busy,
  submit,
  cancel,
  retry,
}: {
  state: StateView | null;
  latest: Run | undefined;
  busy: boolean;
  submit: (body: Submission) => Promise<boolean>;
  cancel: () => void;
  retry: (() => Promise<boolean>) | null;
}) {
  const [message, setMessage] = useState("");
  const [resume, setResume] = useState("true");
  const [acknowledged, setAcknowledged] = useState(false);
  const messages = Array.isArray(state?.values.messages)
    ? state.values.messages
    : [];
  const active = isActive(latest);
  const interrupted = latest?.status === "interrupted";
  const recoverable = ["failed", "cancelled", "recovery_required"].includes(
    latest?.status ?? "",
  );
  const send = async (event: FormEvent) => {
    event.preventDefault();
    if (!message.trim() || busy || active || interrupted || recoverable) return;
    if (
      await submit({
        action: "input",
        input: { messages: [{ role: "user", content: message.trim() }] },
        idempotency_key: crypto.randomUUID(),
      })
    )
      setMessage("");
  };
  const resumeRun = async () => {
    let value: Json;
    try {
      value = JSON.parse(resume) as Json;
    } catch {
      value = resume;
    }
    await submit({
      action: "resume",
      resume: value,
      idempotency_key: crypto.randomUUID(),
    });
  };
  return (
    <section
      className="conversation"
      aria-label="Conversation"
    >
      <div className="conversation-heading">
        <h2>Conversation</h2>
        {latest ? (
          <Badge variant="secondary">
            {latest.status.replaceAll("_", " ")}
          </Badge>
        ) : null}
      </div>
      <StickToBottom
        className="conversation-scroll"
        initial="instant"
        resize="instant"
      >
        <StickToBottom.Content className="message-list">
          {messages.length ? (
            messages.map((value, index) => {
              const message = object(value);
              const role = String(message.type ?? message.role ?? "message");
              const text = textContent(message.content);
              return (
                <article
                  className="message"
                  data-role={role}
                  key={typeof message.id === "string" ? message.id : index}
                >
                  <header>
                    {role === "human" || role === "user"
                      ? "You"
                      : role === "ai" || role === "assistant"
                        ? "Agent"
                        : role === "tool"
                          ? `Tool · ${message.name ?? "result"}`
                          : role}
                  </header>
                  {text ? (
                    <Suspense fallback={<p>{text}</p>}>
                      <MarkdownText>{text}</MarkdownText>
                    </Suspense>
                  ) : (
                    <JsonView
                      value={message.content}
                      label="Message content"
                    />
                  )}
                  {Array.isArray(message.tool_calls) &&
                  message.tool_calls.length ? (
                    <details>
                      <summary>
                        Tool calls ({message.tool_calls.length})
                      </summary>
                      <JsonView
                        value={message.tool_calls}
                        label="Tool calls"
                      />
                    </details>
                  ) : null}
                </article>
              );
            })
          ) : (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>Start a conversation</EmptyTitle>
                <EmptyDescription>
                  Send a message to run this graph. Events, state, and
                  checkpoints will appear in the inspector.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
          {active ? (
            <p
              role="status"
              className="panel-note"
            >
              Graph running. Saved messages appear as checkpoints advance.
            </p>
          ) : null}
        </StickToBottom.Content>
        <JumpToLatest />
      </StickToBottom>
      {interrupted ? (
        <div className="review-controls">
          <h3>Waiting for input</h3>
          <JsonView
            value={state?.interrupts}
            label="Interrupt requests"
          />
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="resume">
                Resume value (JSON or text)
              </FieldLabel>
              <Textarea
                id="resume"
                value={resume}
                onChange={(event) => setResume(event.target.value)}
              />
            </Field>
          </FieldGroup>
          <Button
            disabled={busy}
            onClick={() => void resumeRun()}
          >
            Resume run
          </Button>
        </div>
      ) : null}
      {recoverable ? (
        <div className="review-controls">
          <h3>Recovery required</h3>
          {latest?.error ? (
            <Alert variant="destructive">
              <AlertTitle>
                {String(
                  latest.error.exception_type ??
                    latest.error.code ??
                    "Run failed",
                )}
              </AlertTitle>
              <AlertDescription>
                {latest.error.code === "model_configuration_missing" &&
                typeof latest.error.message === "string"
                  ? latest.error.message
                  : "The graph failed. Check the selected run and its events before recovering; retrying alone may fail again."}
                <code>
                  {String(latest.error.code ?? "graph_execution_failed")}
                </code>
              </AlertDescription>
            </Alert>
          ) : null}
          <p>
            Fix the failure cause before recovery. Unfinished nodes may run
            again.
          </p>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            I acknowledge that unfinished work may run again.
          </label>
          <Button
            variant="outline"
            disabled={busy || !acknowledged}
            onClick={() =>
              void submit({
                action: "recover",
                acknowledge_replay: true,
                idempotency_key: crypto.randomUUID(),
              })
            }
          >
            Recover run
          </Button>
        </div>
      ) : null}
      {retry ? (
        <Button
          className="retry-submission"
          variant="outline"
          disabled={busy}
          onClick={() => {
            void retry().then((ok) => {
              if (ok) setMessage("");
            });
          }}
        >
          Retry submission
        </Button>
      ) : null}
      <form
        className="composer"
        onSubmit={(event) => void send(event)}
      >
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="message">Message</FieldLabel>
            <Textarea
              id="message"
              placeholder="Message the agent…"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              disabled={busy || active || interrupted || recoverable}
              rows={3}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();
                  void send(event);
                }
              }}
            />
          </Field>
        </FieldGroup>
        <div className="composer-actions">
          <span>Enter to send · Shift + Enter for a new line</span>
          {active ? (
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={cancel}
            >
              <Square data-icon="inline-start" />
              Cancel run
            </Button>
          ) : (
            <Button
              type="submit"
              disabled={!message.trim() || busy || interrupted || recoverable}
            >
              <Send data-icon="inline-start" />
              {busy ? "Submitting…" : "Send"}
            </Button>
          )}
        </div>
      </form>
    </section>
  );
}
