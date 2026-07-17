// tests/e2e/cox-guided.spec.js
const { test, expect } = require("@playwright/test");

test("cox shows three tabs and syncs the hash", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /cox regression/i }).click();
  await expect(page.getByRole("tab", { name: "Understand" })).toBeVisible();
  await page.getByRole("tab", { name: "Try an Example" }).click();
  expect(page.url()).toContain("#cox/example");
});

test("demo fits a Table-3 + forest plot and enables the .R download", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#cox/example");
  await page.getByRole("button", { name: /cox regression/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 300000 });
  await expect(page.locator("#preview svg")).toBeVisible();
  await expect(page.locator("#stats")).toContainText(/adjusted/i);
  await expect(page.locator("#stats")).toContainText(/New treatment/);
  await expect(page.locator("#export-r")).toBeEnabled();
});

test("analyze stage fits an uploaded Cox model with adjusted HRs", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#cox/analyze");
  await page.getByRole("button", { name: /cox regression/i }).click();
  await expect(page.locator("#csv")).toBeVisible();
  await expect(page.locator("#cox-config")).toBeHidden();
  // Synthetic survival CSV: time, status (dead/alive), an arm, and a numeric age.
  const rows = Array.from({ length: 80 }, (_, i) => {
    const arm = i % 2 ? "Treated" : "Control";
    const age = 55 + (i % 20);
    const t = (2 + (i % 12) + (arm === "Treated" ? 6 : 0)).toFixed(1);
    const status = i % 3 === 0 ? "alive" : "dead";
    return `${t},${status},${arm},${age}`;
  });
  const csv = "time,status,arm,age\n" + rows.join("\n");
  await page.locator("#csv").setInputFiles({
    name: "cox.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await expect(page.locator("#cox-config")).toBeVisible();
  const analyze = page.locator("#panel-analyze");
  await analyze.locator("#cp_time").selectOption("time");
  await analyze.locator("#cp_status").selectOption("status");
  // covariates is a multi-select: choose arm + age
  await analyze.locator("#cp_covariates").selectOption(["arm", "age"]);
  await analyze.locator("#cox-event").selectOption("dead");
  await analyze.locator("#cox-render").click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 300000 });
  await expect(page.locator("#stats")).toContainText(/adjusted/i);
});
