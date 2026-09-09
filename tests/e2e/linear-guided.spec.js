// tests/e2e/linear-guided.spec.js
// Deliberate near-clone of logistic-guided.spec.js — the duplication is intentional;
// do not extract shared helpers across the guided specs.
const { test, expect } = require("@playwright/test");
const path = require("path");

const DEMO_CSV = path.join(__dirname, "..", "testthat", "fixtures", "linear-demo.csv");

// Table cells read "-1.48 (-1.97 to -0.99, p<0.001)"; returns [est, lo, hi].
async function cellInRow(page, label, column) {
  const row = page.locator("#preview table tbody tr", { hasText: label }).first();
  await expect(row).toBeVisible();
  const text = (await row.locator("td").nth(column).innerText()).trim();
  const m = /^(-?\d+\.\d+) \((-?\d+\.\d+) to (-?\d+\.\d+),/.exec(text);
  expect(m, `cell "${text}" matches the coefficient format`).not.toBeNull();
  return m.slice(1).map(Number);
}

// The confounding story pinned by data-raw/linear-demo-generator.R's stopifnot
// block: the crude arm CI straddles 0; the adjusted arm CI lies entirely below 0.
async function expectConfoundingStory(page) {
  const [, uLo, uHi] = await cellInRow(page, "New treatment", 1);
  expect(uLo).toBeLessThan(0);
  expect(uHi).toBeGreaterThan(0);
  const [aEst, , aHi] = await cellInRow(page, "New treatment", 2);
  expect(aEst).toBeLessThan(-0.5);
  expect(aHi).toBeLessThan(0);
  // age is reported per 10 years; at the default increment of 1 the estimate
  // would be a tenth of this, so the lower bound also pins the increment.
  const [ageEst] = await cellInRow(page, "age (per 10 units)", 2);
  expect(ageEst).toBeGreaterThan(0.4);
}

test("linear shows three tabs and syncs the hash", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /linear regression/i }).click();
  await expect(page.getByRole("tab", { name: "Understand" })).toBeVisible();
  await page.getByRole("tab", { name: "Try an Example" }).click();
  expect(page.url()).toContain("#linear/example");
});

test("demo fits a Table-3, forest and diagnostics and enables the .R download", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#linear/example");
  await page.getByRole("button", { name: /linear regression/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 300000 });
  await expect(page.locator("#preview svg")).toHaveCount(3);
  await expectConfoundingStory(page);
  await expect(page.locator("#stats")).toContainText("Multivariable linear regression (n = 320) of los");
  await expect(page.locator("#stats")).toContainText(/R² = 0\.\d{3}/);
  await expect(page.locator("#stats")).not.toContainText("Shapiro");
  await expect(page.locator("#stats")).not.toContainText("Breusch");
  await expect(page.locator("#export-r")).toBeEnabled();
  await expect(page.locator("#cov-arm")).toBeDisabled();
  await expect(page.locator("#cov-age")).toBeEnabled();
  await expect(page.locator("#run-demo")).toBeEnabled();
});

test("analyze stage fits an uploaded linear model with adjusted coefficients", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#linear/analyze");
  await page.getByRole("button", { name: /linear regression/i }).click();
  await expect(page.locator("#csv")).toBeVisible();
  await expect(page.locator("#linear-config")).toBeHidden();
  await page.locator("#csv").setInputFiles(DEMO_CSV);
  await expect(page.locator("#linear-config")).toBeVisible();

  const analyze = page.locator("#panel-analyze");
  // The outcome dropdown is numeric-only: `arm` and `stage` must not be offered.
  await expect(analyze.locator("#cp_outcome option[value='arm']")).toHaveCount(0);
  await analyze.locator("#cp_outcome").selectOption("los");
  await analyze.locator("#cp_covariates").selectOption(["arm", "age", "stage"]);
  await analyze.locator("#linear-ref-arm").selectOption("Standard care");
  await analyze.locator("#linear-ref-stage").selectOption("I");
  await analyze.locator("#linear-incr-age").fill("10");
  await analyze.locator("#linear-render").click();

  await expect(page.locator("#preview table")).toBeVisible({ timeout: 300000 });
  await expectConfoundingStory(page);
  await expect(page.locator("#stats")).toContainText("(n = 320)");
});
