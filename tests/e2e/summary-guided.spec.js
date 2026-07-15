// tests/e2e/summary-guided.spec.js
const { test, expect } = require("@playwright/test");
const path = require("path");

test("guided summary shows three tabs, syncs the hash, starts on Understand", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /table 1/i }).click();
  await expect(page.getByRole("tab", { name: "Understand" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Try an Example" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Analyze Your Data" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Understand" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Try an Example" }).click();
  expect(page.url()).toContain("#summary/example");
  expect(page.url()).not.toContain("csv");
});

test("Understand teaches the Table 1 fallacy and mean-vs-median", async ({ page }) => {
  await page.goto("/#summary/understand");
  await page.getByRole("button", { name: /table 1/i }).click();
  await expect(page.getByRole("heading", { name: /Mean .* median/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /no p-values/i })).toBeVisible();
  await expect(page.getByText("SD, never SEM")).toBeVisible();
});

test("Analyze tab is progressive: no checklist or Render before a file is chosen", async ({ page }) => {
  await page.goto("/#summary/analyze");
  await page.getByRole("button", { name: /table 1/i }).click();
  await expect(page.locator("#csv")).toBeVisible();
  await expect(page.locator("#summary-vars")).toBeHidden();
  await expect(page.locator("#render")).toBeHidden();
});

test("malformed CSV shows a styled error and keeps the form pre-upload", async ({ page }) => {
  await page.goto("/#summary/analyze");
  await page.getByRole("button", { name: /table 1/i }).click();
  await page.locator("#csv").setInputFiles({
    name: "bad.csv", mimeType: "text/csv",
    buffer: Buffer.from("a,b\n1,2,3\n"),   // row wider than header -> parseCsv throws
  });
  await expect(page.locator("#stats")).toHaveClass(/error/);
  await expect(page.locator("#render")).toBeHidden();
});

test("Run Example computes the real Table 1 with the right decisions, plot, and legend", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#summary/example");
  await page.getByRole("button", { name: /table 1/i }).click();
  await expect(page.getByText("Synthetic demonstration data — not for clinical use.")).toBeVisible();
  await expect(page.locator("#preview table")).toHaveCount(0);
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 330000 });
  const preview = page.locator("#preview");
  await expect(preview).toContainText("Age, mean ± SD");                // normal -> mean±SD
  await expect(preview).toContainText("Length of stay, median (IQR)"); // skewed -> median
  await expect(preview).toContainText("Missing");
  await expect(page.locator("#preview svg")).toBeVisible();             // bundled distribution plot
  await expect(page.locator("#preview .plot-legend")).toContainText("dashed = mean");
  await expect(preview).not.toContainText("p-value");                  // Table 1 fallacy guardrail
});

test("Force mean ± SD experiment rewrites the skewed row", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#summary/example");
  await page.getByRole("button", { name: /table 1/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 330000 });
  await page.locator("#exp-forcemean").check();
  await expect(page.locator("#preview")).toContainText("Length of stay, mean ± SD",
    { timeout: 120000 });
  await expect(page.locator("#preview")).toContainText("you selected mean ± SD");
});

test("demo and user results are separate contexts; checklist controls the table", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#summary/example");
  await page.getByRole("button", { name: /table 1/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 330000 });
  await page.getByRole("tab", { name: "Analyze Your Data" }).click();
  await expect(page.locator("#preview table")).toHaveCount(0);   // user context empty
  await page.locator("#csv").setInputFiles(
    path.join(__dirname, "..", "testthat", "fixtures", "summary-demo.csv"));
  await expect(page.locator("#summary-vars")).toBeVisible();     // progressive reveal
  // Checklist a11y: each checkbox is described by its note.
  await expect(page.locator("#var-age")).toHaveAttribute("aria-describedby", "var-age-note");
  // Untick a variable -> its row must not render.
  await page.locator("#var-crp").uncheck();
  await page.locator("#render").click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 120000 });
  await expect(page.locator("#preview")).not.toContainText("crp");
  await page.getByRole("tab", { name: "Try an Example" }).click();
  await expect(page.locator("#preview")).toContainText("Age, mean ± SD");  // demo restored
});
