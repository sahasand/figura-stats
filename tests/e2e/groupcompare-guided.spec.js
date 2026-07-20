// tests/e2e/groupcompare-guided.spec.js
const { test, expect } = require("@playwright/test");

test("groupcompare shows three tabs and syncs the hash", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /group comparison/i }).click();
  await expect(page.getByRole("tab", { name: "Understand" })).toBeVisible();
  await page.getByRole("tab", { name: "Try an Example" }).click();
  expect(page.url()).toContain("#groupcompare/example");
});

test("demo: numeric outcome renders a plot with test + effect size; categorical switches to chi-square", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#groupcompare/example");
  await page.getByRole("button", { name: /group comparison/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 300000 });
  await expect(page.locator("#stats")).toContainText(/ANOVA|t-test/);
  await expect(page.locator("#stats")).toContainText("95% CI");

  // With a numeric outcome the Plot picker is a live Box/Violin control, so the
  // assertion after the switch below is not trivially true.
  await expect(page.locator("#demo-plot")).toBeEnabled();

  // Switch the outcome to the categorical responder column -> chi-square.
  await page.locator("#cp_outcome").selectOption("responder");
  await expect(page.locator("#stats")).toContainText(/chi-square|Fisher/, { timeout: 120000 });
  await expect(page.locator("#preview svg")).toBeVisible();

  // Shared-shell control lock (same code path logistic-guided.spec.js pins, but
  // reached differently): a categorical outcome always renders a stacked
  // proportion bar, so content.js replaces the Plot picker with a deliberately
  // disabled placeholder. The rerun here is triggered BY an experiment control
  // (not the Run button) and the locked node is a <select> created mid-change,
  // so this covers the element-keyed restore that the checkbox-on-Run-click
  // logistic assertion does not. A blanket re-enable after the run would leave
  // the user an inert Plot picker that cannot change the figure.
  await expect(page.locator("#demo-plot")).toBeDisabled();
  await expect(page.locator("#demo-test")).toBeEnabled();
  await expect(page.locator("#run-demo")).toBeEnabled();
  await expect(page.locator("#reset-demo")).toBeEnabled();
});

test("analyze stage renders an uploaded comparison with a real p-value", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#groupcompare/analyze");
  await page.getByRole("button", { name: /group comparison/i }).click();
  await expect(page.locator("#csv")).toBeVisible();
  await expect(page.locator("#gc-config")).toBeHidden();
  const csv = "arm,score\n" + Array.from({ length: 40 }, (_, i) =>
    `${i % 2 ? "A" : "B"},${(10 + (i % 2) * 4 + (i % 5)).toFixed(1)}`).join("\n");
  await page.locator("#csv").setInputFiles({
    name: "g.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await expect(page.locator("#gc-config")).toBeVisible();
  // The example (demo) panel renders its own builder with the same #cp_group/
  // #cp_outcome control ids (createGuidedShell mounts both stage panels up
  // front, hidden panel and all) — scope to the analyze panel so these
  // resolve unambiguously in strict mode, same fix explore-guided.spec.js
  // needed for #cp_x/#cp_y.
  const analyze = page.locator("#panel-analyze");
  await analyze.locator("#cp_group").selectOption("arm");
  await analyze.locator("#cp_outcome").selectOption("score");
  await page.locator("#gc-render").click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 300000 });
  await expect(page.locator("#stats")).toContainText(/p [=<]/);
});
