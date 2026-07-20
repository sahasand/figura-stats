// tests/e2e/logistic-guided.spec.js
// Deliberate near-clone of cox-guided.spec.js — the duplication is intentional;
// do not extract shared helpers across the guided specs.
const { test, expect } = require("@playwright/test");
const path = require("path");

const DEMO_CSV = path.join(__dirname, "..", "testthat", "fixtures", "logistic-demo.csv");

// Table cells read "1.02 (0.63–1.66, p=0.932)"; the leading number is the OR.
async function orInRow(page, label, column) {
  const row = page.locator("#preview table tbody tr", { hasText: label }).first();
  await expect(row).toBeVisible();
  const cell = row.locator("td").nth(column);
  const value = parseFloat((await cell.innerText()).trim());
  expect(Number.isFinite(value)).toBe(true);
  return value;
}

test("logistic shows three tabs and syncs the hash", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /logistic regression/i }).click();
  await expect(page.getByRole("tab", { name: "Understand" })).toBeVisible();
  await page.getByRole("tab", { name: "Try an Example" }).click();
  expect(page.url()).toContain("#logistic/example");
});

test("demo fits a Table-3 + forest plot and enables the .R download", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#logistic/example");
  await page.getByRole("button", { name: /logistic regression/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 300000 });
  await expect(page.locator("#preview svg")).toBeVisible();

  // The confounding story: the crude arm comparison looks null (OR ~1.02), and
  // adjusting for age + stage reveals a protective effect (OR ~0.50). A flipped
  // reference level, a dropped adjustment, or a lost event value all move these.
  const armUnadj = await orInRow(page, "New treatment", 1);
  const armAdj = await orInRow(page, "New treatment", 2);
  expect(armUnadj).toBeGreaterThan(0.99);
  expect(armUnadj).toBeLessThan(1.05);
  expect(armAdj).toBeGreaterThan(0.47);
  expect(armAdj).toBeLessThan(0.53);
  // age is reported per 10 years (increment 10). At the default increment of 1
  // this row reads ~1.05, so the window below also pins the increment.
  const ageAdj = await orInRow(page, "age (per 10 units)", 2);
  expect(ageAdj).toBeGreaterThan(1.63);
  expect(ageAdj).toBeLessThan(1.75);

  await expect(page.locator("#stats")).toContainText(/adjusted/i);
  await expect(page.locator("#stats")).toContainText(/New treatment/);
  await expect(page.locator("#stats")).toContainText(/C-statistic = 0\.6[5-9]/);
  await expect(page.locator("#stats")).toContainText("n = 320, 91 events");
  await expect(page.locator("#export-r")).toBeEnabled();
});

test("analyze stage fits an uploaded logistic model with adjusted ORs", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#logistic/analyze");
  await page.getByRole("button", { name: /logistic regression/i }).click();
  await expect(page.locator("#csv")).toBeVisible();
  await expect(page.locator("#logistic-config")).toBeHidden();
  await page.locator("#csv").setInputFiles(DEMO_CSV);
  await expect(page.locator("#logistic-config")).toBeVisible();

  const analyze = page.locator("#panel-analyze");
  await analyze.locator("#cp_outcome").selectOption("complication");
  // covariates is a multi-select; the event dropdown only fills once BOTH roles
  // are mapped, so this must come before touching #logistic-event.
  await analyze.locator("#cp_covariates").selectOption(["arm", "age", "stage"]);
  await analyze.locator("#logistic-event").selectOption("Yes");
  await analyze.locator("#logistic-ref-arm").selectOption("Standard care");
  await analyze.locator("#logistic-ref-stage").selectOption("I");
  await analyze.locator("#logistic-incr-age").fill("10");
  await analyze.locator("#logistic-render").click();

  await expect(page.locator("#preview table")).toBeVisible({ timeout: 300000 });
  // Same data and same model as the demo, so the same numbers must come back.
  const armUnadj = await orInRow(page, "New treatment", 1);
  const armAdj = await orInRow(page, "New treatment", 2);
  expect(armUnadj).toBeGreaterThan(0.99);
  expect(armUnadj).toBeLessThan(1.05);
  expect(armAdj).toBeGreaterThan(0.47);
  expect(armAdj).toBeLessThan(0.53);
  const ageAdj = await orInRow(page, "age (per 10 units)", 2);
  expect(ageAdj).toBeGreaterThan(1.63);
  expect(ageAdj).toBeLessThan(1.75);
  await expect(page.locator("#stats")).toContainText(/adjusted/i);
  await expect(page.locator("#stats")).toContainText("n = 320, 91 events");
});
