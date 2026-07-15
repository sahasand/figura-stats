const { test, expect } = require("@playwright/test");
const path = require("path");

test("guided KM shows three stage tabs, syncs the hash, and starts on Understand", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await expect(page.getByRole("tab", { name: "Understand" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Try an Example" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Analyze Your Data" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Understand" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Try an Example" }).click();
  expect(page.url()).toContain("#km/example");
  expect(page.url()).not.toContain("csv");           // no data in URL, ever
  // keyboard reachable
  await page.getByRole("tab", { name: "Understand" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("tab", { name: "Understand" })).toHaveAttribute("aria-selected", "true");
});

test("Understand teaches the method with a labeled non-data visual", async ({ page }) => {
  await page.goto("/#km/understand");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await expect(page.getByRole("heading", { name: "Estimate survival over time" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /appropriate/i })).toBeVisible();
  await expect(page.getByText("Illustration—not computed data")).toBeVisible();
  await expect(page.getByText("Sources and methodology")).toBeVisible();
});

test("Run Example Analysis computes the real pinned demo result", async ({ page }) => {
  test.setTimeout(360000); // first run installs survival+cowplot in webR
  await page.goto("/#km/example");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await expect(page.getByText("Synthetic demonstration data — not for clinical use.")).toBeVisible();
  await expect(page.locator("#preview svg")).toHaveCount(0);   // nothing before the click
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 330000 });
  const stats = page.locator("#stats");
  await expect(stats).toContainText("p = 0.108");              // pinned log-rank
  await expect(stats).toContainText("HR 0.64 (New treatment vs Standard care");
  await expect(stats).toContainText("not reached");            // New treatment median
  await expect(page.locator("#preview")).toContainText("Number at risk");
  await expect(page.locator("#preview")).toContainText("Synthetic demonstration data");
});

test("landmark experiment adds 12/24-month estimates and Reset restores defaults", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#km/example");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 330000 });
  await page.locator("#exp-landmarks").check();
  await expect(page.locator("#stats")).toContainText("At 12.0 Months since randomization, survival was 73.5%",
    { timeout: 120000 });   // packages cached now; rerun is fast
  await page.getByRole("button", { name: "Reset Example" }).click();
  await expect(page.locator("#exp-landmarks")).not.toBeChecked();
  await expect(page.locator("#preview svg")).toHaveCount(0);   // demo result cleared
});

test("demo and user results are separate contexts", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#km/example");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#stats")).toContainText("p = 0.108", { timeout: 330000 });
  await page.getByRole("tab", { name: "Analyze Your Data" }).click();
  await expect(page.locator("#preview svg")).toHaveCount(0);   // user context empty
  await page.locator("#csv").setInputFiles(path.join(__dirname, "fixtures", "km.csv"));
  await page.getByRole("button", { name: /render/i }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 120000 });
  await page.getByRole("tab", { name: "Try an Example" }).click();
  await expect(page.locator("#stats")).toContainText("p = 0.108");  // demo restored
});
