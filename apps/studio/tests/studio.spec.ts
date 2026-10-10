import { test, expect, type Page } from "@playwright/test";
import fixtures from "../../agent/tests/fixtures/runtime-events.json" with { type: "json" };
import type {
  Session,
  Run,
  StateView,
  RuntimeEvent,
  Submission,
} from "../src/runtime/types";

const sid = "00000000-0000-4000-8000-000000000001";
const aid = "00000000-0000-4000-8000-000000000010";
const time = "2026-10-09T12:00:00Z";
async function fixtureRuntime(page: Page) {
  const sessions: Session[] = [];
  const runs: Run[] = [];
  let events: RuntimeEvent[] = [];
  let state: StateView = {
    values: { messages: [] },
    next: [],
    checkpoint_id: null,
    created_at: null,
    metadata: {},
    interrupts: [],
  };
  const submitted: Submission[] = [];
  const assistant = {
    assistant_id: aid,
    graph_id: "echo",
    name: "echo",
    config: { recursion_limit: 25 },
    created_at: time,
  };
  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const body =
      route.request().method() === "POST"
        ? route.request().postDataJSON()
        : null;
    let result: unknown;
    if (path === "/info") result = { protocol: "stocker-runtime-v1" };
    else if (path === "/health") result = { status: "ok" };
    else if (path === "/api/graphs") result = ["echo"];
    else if (path === "/api/assistants") result = body ? assistant : [];
    else if (path === "/api/sessions") {
      if (body) {
        const session = {
          session_id: sid,
          assistant_id: aid,
          graph_id: "echo",
          config: { recursion_limit: 25 },
          title: body.title,
          created_at: time,
        };
        sessions.push(session);
        result = session;
      } else result = sessions;
    } else if (path === `/api/sessions/${sid}/runs`) {
      if (body) {
        submitted.push(body);
        const input = body.input?.messages?.[0]?.content;
        const messages = state.values.messages as unknown[];
        if (input)
          messages.push(
            { type: "human", content: input },
            { type: "ai", content: "reply: " + input },
          );
        state = {
          ...state,
          values: { messages } as StateView["values"],
          checkpoint_id: "checkpoint-" + submitted.length,
          created_at: time,
          interrupts: body.action === "resume" ? [] : state.interrupts,
        };
        const run = {
          run_id: crypto.randomUUID(),
          session_id: sid,
          action: body.action,
          status: "completed",
          idempotency_key: body.idempotency_key,
          created_at: time.replace("00Z", `0${submitted.length}Z`),
          updated_at: time,
          error: null,
        } as Run;
        runs.push(run);
        result = run;
        events = fixtures.slice(0, 4).map((event, index) => ({
          ...event,
          event_id: submitted.length * 10 + index,
          run_id: run.run_id,
        })) as RuntimeEvent[];
      } else result = runs;
    } else if (path === `/api/sessions/${sid}/state`) result = state;
    else if (path === `/api/sessions/${sid}/events`) result = events;
    else if (path === `/api/sessions/${sid}/checkpoints`)
      result = [
        state,
        {
          ...state,
          checkpoint_id: "older-checkpoint",
          values: { messages: [] },
        },
      ];
    else if (path === `/api/sessions/${sid}/checkpoints/compare`)
      result = {
        left: state,
        right: { ...state, values: { messages: [] } },
        changed_keys: ["messages"],
      };
    else if (path.startsWith(`/api/sessions/${sid}/checkpoints/`))
      result = state;
    else {
      await route.fulfill({
        status: 404,
        json: { error: { code: "not_found" } },
      });
      return;
    }
    await route.fulfill({
      json: result,
      status: body ? (path.endsWith("/runs") ? 202 : 201) : 200,
    });
  });
  return {
    submitted,
    fail: () => {
      runs[runs.length - 1].status = "failed";
      runs[runs.length - 1].error = {
        code: "model_configuration_missing",
        exception_type: "MissingModelSetting",
        setting: "GOOGLE_API_KEY",
        message:
          "Configure GOOGLE_API_KEY in apps/agent/.env (or the process environment), then restart the backend before recovery.",
      };
    },
    interrupt: () => {
      runs[runs.length - 1].status = "interrupted";
      state.interrupts = [{ id: "review", value: { question: "approve?" } }];
    },
  };
}

test("missing model configuration is explained before explicit recovery", async ({
  page,
}) => {
  const fixture = await fixtureRuntime(page);
  await page.goto("/");
  await page.getByRole("button", { name: "New session", exact: true }).click();
  await page.getByLabel("Message", { exact: true }).fill("hello");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("reply: hello", { exact: true })).toBeVisible();
  fixture.fail();
  await page
    .getByRole("button", { name: "Refresh session", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("GOOGLE_API_KEY");
  await expect(page.getByRole("alert")).toContainText("apps/agent/.env");
  await expect(page.getByRole("alert")).toContainText("restart the backend");
  await expect(
    page.getByRole("button", { name: "Recover run", exact: true }),
  ).toBeDisabled();
  expect(fixture.submitted).toHaveLength(1);
});

test("two turns, inspection, saved sessions, and responsive layouts", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const fixture = await fixtureRuntime(page);
  await page.goto("/");
  await page.getByLabel("Session name").fill("Echo debugging");
  await page.getByRole("button", { name: "New session", exact: true }).click();
  await page.getByLabel("Message", { exact: true }).fill("hello");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("reply: hello", { exact: true })).toBeVisible();
  await page.getByLabel("Message", { exact: true }).fill("again");
  await page.getByLabel("Message", { exact: true }).press("Enter");
  await expect(page.getByText("reply: again", { exact: true })).toBeVisible();
  expect(fixture.submitted).toHaveLength(2);
  await page
    .getByRole("button", { name: /on_tool_end/ })
    .last()
    .click();
  await expect(
    page.getByText("print_user_message", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Trace", exact: true }).click();
  await expect(page.getByLabel("Execution trace")).toBeVisible();
  await page.getByRole("tab", { name: "State", exact: true }).click();
  await expect(page.getByLabel("Current state")).toContainText("reply: again");
  await page.getByRole("tab", { name: "Checkpoints", exact: true }).click();
  await page.getByLabel("Inspect checkpoint").selectOption("checkpoint-2");
  await expect(page.getByLabel("Historical checkpoint")).toBeVisible();
  await page.getByLabel("Compare with").selectOption("older-checkpoint");
  await page
    .getByRole("button", { name: "Compare checkpoints", exact: true })
    .click();
  await expect(page.getByText("Changed keys: messages")).toBeVisible();
  await page.getByRole("tab", { name: "Events", exact: true }).click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "/tmp/stocker-studio-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "/tmp/stocker-studio-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.reload();
  await expect(page.getByText("reply: again", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("interrupt resumes with a typed JSON value", async ({ page }) => {
  const fixture = await fixtureRuntime(page);
  await page.goto("/");
  await page.getByRole("button", { name: "New session", exact: true }).click();
  await page.getByLabel("Message", { exact: true }).fill("review");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("reply: review", { exact: true })).toBeVisible();
  fixture.interrupt();
  await page
    .getByRole("button", { name: "Refresh session", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Waiting for input" }),
  ).toBeVisible();
  await page
    .getByLabel("Resume value (JSON or text)")
    .fill('{"approved":true}');
  await page.getByRole("button", { name: "Resume run", exact: true }).click();
  await expect.poll(() => fixture.submitted.at(-1)?.action).toBe("resume");
  expect(fixture.submitted.at(-1)).toMatchObject({
    resume: { approved: true },
  });
});

test("switching services clears selections and histories", async ({ page }) => {
  await fixtureRuntime(page);
  await page.goto("/");
  await page.getByLabel("Session name").fill("First server session");
  await page.getByRole("button", { name: "New session", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "First server session" }),
  ).toBeVisible();
  await page.route("http://other.local/**", (route) =>
    route.fulfill({
      json: route.request().url().endsWith("/info")
        ? { protocol: "stocker-runtime-v1" }
        : route.request().url().endsWith("/health")
          ? { status: "ok" }
          : [],
    }),
  );
  await page.getByLabel("Service", { exact: true }).fill("http://other.local");
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "First server session" }),
  ).not.toBeVisible();
  await expect(
    page.getByText("Your agent development workspace"),
  ).toBeVisible();
});

test("client parses chunked Unicode SSE and reconnects without duplicates", async ({
  page,
}) => {
  await fixtureRuntime(page);
  await page.goto("/");
  const result = await page.evaluate(async () => {
    const modulePath = "/src/runtime/client.ts";
    const { RuntimeClient, readEvents } = await import(
      /* @vite-ignore */ modulePath
    );
    const event = {
      event_id: 5,
      session_id: "session",
      run_id: "run",
      kind: "on_tool_end",
      created_at: "",
      payload: { text: "中文" },
      durable: true as const,
    };
    const bytes = new TextEncoder().encode(
      ": heartbeat\r\n\r\ndata: " + JSON.stringify(event) + "\r\n\r\n",
    );
    const chunks = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
        controller.close();
      },
    });
    const parsed = [];
    for await (const item of readEvents(chunks)) parsed.push(item);
    const original = window.fetch;
    const urls: string[] = [];
    let streams = 0;
    window.fetch = async (input) => {
      const url = String(input);
      urls.push(url);
      if (url.includes("/stream")) {
        streams++;
        const batch =
          streams === 1 ? [event] : [event, { ...event, event_id: 6 }];
        return new Response(
          batch
            .map((item) => "data: " + JSON.stringify(item) + "\n\n")
            .join(""),
          { headers: { "Content-Type": "text/event-stream" } },
        );
      }
      return Response.json({ status: streams === 1 ? "running" : "completed" });
    };
    const observed: number[] = [];
    const statuses: string[] = [];
    try {
      await new RuntimeClient("http://fixture.local").observe(
        "run",
        0,
        new AbortController().signal,
        (event: RuntimeEvent) => observed.push(event.event_id),
        (status: string) => statuses.push(status),
      );
    } finally {
      window.fetch = original;
    }
    return { parsed, observed, statuses, urls };
  });
  expect(result.parsed[0].payload).toEqual({ text: "中文" });
  expect(result.observed).toEqual([5, 6]);
  expect(result.urls.some((url: string) => url.endsWith("after=5"))).toBe(true);
  expect(result.statuses).toContain("Reconnecting");
  expect(result.statuses.at(-1)).toBe("Saved");
});

test("unavailable server has an actionable retry", async ({ page }) => {
  await page.route("http://127.0.0.1:8000/**", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { code: "worker_unavailable" } },
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("worker unavailable");
  await expect(
    page.getByRole("button", { name: "Retry connection" }),
  ).toBeVisible();
});

test("client follows pagination cursors and preserves API error codes", async ({
  page,
}) => {
  await fixtureRuntime(page);
  await page.goto("/");
  const result = await page.evaluate(async () => {
    const modulePath = "/src/runtime/client.ts";
    const { RuntimeClient } = await import(/* @vite-ignore */ modulePath);
    const original = window.fetch;
    const urls: string[] = [];
    window.fetch = async (input) => {
      const url = String(input);
      urls.push(url);
      if (url.includes("missing"))
        return Response.json({ error: { code: "not_found" } }, { status: 404 });
      if (url.includes("after="))
        return Response.json([{ session_id: "last" }]);
      return Response.json(
        Array.from({ length: 200 }, (_, i) => ({ session_id: String(i) })),
      );
    };
    const client = new RuntimeClient("http://fixture.local");
    try {
      const records = await client.sessions();
      let code = "";
      try {
        await client.run("missing");
      } catch (error) {
        code = (error as { code: string }).code;
      }
      return { count: records.length, urls, code };
    } finally {
      window.fetch = original;
    }
  });
  expect(result.count).toBe(201);
  expect(result.urls.some((url: string) => url.endsWith("after=199"))).toBe(
    true,
  );
  expect(result.code).toBe("not_found");
});

test("a failed submission retries with the same idempotency key", async ({
  page,
}) => {
  await fixtureRuntime(page);
  const bodies: Submission[] = [];
  await page.route(
    "http://127.0.0.1:8000/api/sessions/*/runs",
    async (route) => {
      if (route.request().method() !== "POST") {
        await route.fallback();
        return;
      }
      bodies.push(route.request().postDataJSON());
      if (bodies.length === 1) await route.abort();
      else await route.fallback();
    },
  );
  await page.goto("/");
  await page.getByRole("button", { name: "New session", exact: true }).click();
  await page.getByLabel("Message", { exact: true }).fill("retry safely");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page
    .getByRole("button", { name: "Retry submission", exact: true })
    .click();
  await expect(
    page.getByText("reply: retry safely", { exact: true }),
  ).toBeVisible();
  expect(bodies).toHaveLength(2);
  expect(bodies[0]).toEqual(bodies[1]);
});
