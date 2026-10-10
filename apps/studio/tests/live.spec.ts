import { test, expect } from "@playwright/test";

const service = process.env.STUDIO_LIVE_API_URL;
test.describe("deterministic live FastAPI runtime", () => {
  test.skip(
    !service,
    "Set STUDIO_LIVE_API_URL to a deterministic runtime; this test must not target a live model.",
  );
  test("built UI, two-turn state, events and saved history", async ({
    page,
  }) => {
    await page.goto(service!);
    await page
      .getByLabel("Session name")
      .fill("Browser verification " + Date.now());
    await page
      .getByRole("button", { name: "New session", exact: true })
      .click();
    await page
      .getByLabel("Message", { exact: true })
      .fill("browser first turn");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(
      page.getByText("reply: browser first turn", { exact: true }),
    ).toBeVisible();
    await page
      .getByLabel("Message", { exact: true })
      .fill("browser second turn");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(
      page.getByText("reply: browser second turn", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /on_chain_end/ }).first(),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByText("reply: browser first turn", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("reply: browser second turn", { exact: true }),
    ).toBeVisible();
    await page.getByRole("tab", { name: "State", exact: true }).click();
    await expect(page.getByLabel("Current state")).toContainText(
      "browser second turn",
    );
    await page.goto(service! + "/session/debug");
    await expect(
      page.getByText("reply: browser second turn", { exact: true }),
    ).toBeVisible();
  });
  test("LangGraph interrupt and resume", async ({ page }) => {
    await page.goto(service!);
    await page.getByLabel("Graph", { exact: true }).selectOption("review");
    await page
      .getByRole("button", { name: "New session", exact: true })
      .click();
    await page.getByLabel("Message", { exact: true }).fill("ask for approval");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Waiting for input" }),
    ).toBeVisible();
    await page.getByLabel("Resume value (JSON or text)").fill("true");
    await page.getByRole("button", { name: "Resume run", exact: true }).click();
    await expect(page.getByText("True", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Waiting for input" }),
    ).not.toBeVisible();
  });
  test("cancel and acknowledge recovery", async ({ page }) => {
    await page.goto(service!);
    await page
      .getByRole("button", { name: "New session", exact: true })
      .click();
    await page.getByLabel("Message", { exact: true }).fill("slow");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await page.getByRole("button", { name: "Cancel run", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Recovery required" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Recover run" }),
    ).toBeDisabled();
    await page
      .getByLabel("I acknowledge that unfinished work may run again.")
      .check();
    await page.getByRole("button", { name: "Recover run" }).click();
    await page.getByRole("button", { name: "Cancel run", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Recovery required" }),
    ).toBeVisible();
  });
});
