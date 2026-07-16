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

  // Switch the outcome to the categorical responder column -> chi-square.
  await page.locator("#cp_outcome").selectOption("responder");
  await expect(page.locator("#stats")).toContainText(/chi-square|Fisher/, { timeout: 120000 });
  await expect(page.locator("#preview svg")).toBeVisible();
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
