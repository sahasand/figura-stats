// tests/e2e/summary-guided.spec.js
const { test, expect } = require("@playwright/test");
const path = require("path");
const fs = require("fs");

test("guided summary shows three tabs, syncs the hash, starts on Understand", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /summary statistics/i }).click();
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
  await page.getByRole("button", { name: /summary statistics/i }).click();
  await expect(page.getByRole("heading", { name: /Mean .* median/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /no p-values/i })).toBeVisible();
  await expect(page.getByText("SD, never SEM")).toBeVisible();
});

test("Analyze tab is progressive: no checklist or Render before a file is chosen", async ({ page }) => {
  await page.goto("/#summary/analyze");
  await page.getByRole("button", { name: /summary statistics/i }).click();
  await expect(page.locator("#csv")).toBeVisible();
  await expect(page.locator("#summary-vars")).toBeHidden();
  await expect(page.locator("#render")).toBeHidden();
});

test("malformed CSV shows a styled error and keeps the form pre-upload", async ({ page }) => {
  await page.goto("/#summary/analyze");
  await page.getByRole("button", { name: /summary statistics/i }).click();
  await page.locator("#csv").setInputFiles({
    name: "bad.csv", mimeType: "text/csv",
    buffer: Buffer.from("a,b\n1,2,3\n"),   // row wider than header -> parseCsv throws
  });
  await expect(page.locator("#stats")).toHaveClass(/error/);
  await expect(page.locator("#render")).toBeHidden();
});

// ---------------------------------------------------------------------------
// THE HEAVY TESTS, ON ONE BOOTED webR RUNTIME.
//
// Same mechanism and the same reasoning as tests/e2e/km-guided.spec.js — read
// the long comment there for why `describe.serial` + a `beforeAll` page beats a
// worker-scoped fixture here, and for the isolation rule this block follows.
// In short: the webR runtime lives in the page's Web Worker, so one page per
// test is one cold runtime download per test; `beforeEach` re-establishes and
// ASSERTS the starting state (remount from the nav, select the Example stage,
// press the app's own Reset Example) instead of letting a test inherit
// whatever the previous one left behind.
//
// As in the KM suite, exactly one test here renders into the guided shell's
// `user` context — the one state a shared page cannot reset — and its
// "user context empty" assertion is a property of this file rather than an
// inheritance from a neighbour. A second user-rendering test added to this
// block would break it loudly; give that test its own page.
test.describe.serial("Summary example stage, on one booted webR runtime", () => {
  let page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    // Deep-linked, for the same reason the KM block is: this is the only
    // direct navigation to "#summary/example" left in the suite now that the
    // heavy tests share one page, and the hash → stage path deserves the same
    // coverage the other two stages get from the light tests above and below.
    // The nav click is what makes the shell read the hash.
    await page.goto("/#summary/example");
    await page.getByRole("button", { name: /summary statistics/i }).click();
    await expect(page.getByRole("tab", { name: "Try an Example" }))
      .toHaveAttribute("aria-selected", "true");
  });

  test.afterAll(async () => {
    if (page) await page.close();
  });

  test.beforeEach(async () => {
    await page.getByRole("button", { name: /summary statistics/i }).click();
    await page.getByRole("tab", { name: "Try an Example" }).click();
    await page.getByRole("button", { name: "Reset Example" }).click();
    await expect(page.locator("#preview table")).toHaveCount(0);
    await expect(page.locator("#stats")).toBeEmpty();
    // All four experiment controls, not only the two these tests flip — same
    // rule as the KM block. Reset Example restores the whole
    // defaultDemoOptions object (`web/guided/summary/guided-summary.js`:
    // group by arm ON, plots ON, force-mean off, Q–Q off), so a reset that
    // quietly stopped restoring one of them would change what the next test
    // is actually running without failing anything.
    await expect(page.locator("#exp-group")).toBeChecked();
    await expect(page.locator("#exp-plots")).toBeChecked();
    await expect(page.locator("#exp-forcemean")).not.toBeChecked();
    await expect(page.locator("#exp-qq")).not.toBeChecked();
  });

  test("Run Example computes the real Table 1 with the right decisions, plot, and legend", async () => {
    test.setTimeout(360000);
    await expect(page.getByText("Synthetic demonstration data")).toBeVisible();
    await expect(page.locator("#preview table")).toHaveCount(0);
    await page.getByRole("button", { name: "Run Example Analysis" }).click();
    await expect(page.locator("#preview table")).toBeVisible({ timeout: 330000 });
    const preview = page.locator("#preview");
    await expect(preview).toContainText("Age, mean ± SD");                // normal -> mean±SD
    await expect(preview).toContainText("Length of stay, median (IQR)"); // skewed -> median
    await expect(preview).toContainText("Missing");
    await expect(page.locator("#preview svg")).toHaveCount(2);            // histogram+density and box+jitter rows
    await expect(page.locator("#preview .plot-legend")).toContainText("dashed = mean");
    await expect(preview).not.toContainText("p-value");                  // Table 1 fallacy guardrail
  });

  test("Force mean ± SD experiment rewrites the skewed row", async () => {
    test.setTimeout(360000);
    await page.getByRole("button", { name: "Run Example Analysis" }).click();
    await expect(page.locator("#preview table")).toBeVisible({ timeout: 330000 });
    await page.locator("#exp-forcemean").check();
    await expect(page.locator("#preview")).toContainText("Length of stay, mean ± SD",
      { timeout: 120000 });
    await expect(page.locator("#preview")).toContainText("you selected mean ± SD");
  });

  test("Q–Q experiment adds a third distribution panel and its legend", async () => {
    test.setTimeout(360000);
    await page.getByRole("button", { name: "Run Example Analysis" }).click();
    await expect(page.locator("#preview table")).toBeVisible({ timeout: 330000 });
    await expect(page.locator("#preview svg")).toHaveCount(2);
    await expect(page.locator("#exp-qq")).not.toBeChecked();       // default off
    await page.locator("#exp-qq").check();
    await expect(page.locator("#preview svg")).toHaveCount(3, { timeout: 120000 });
    await expect(page.locator("#preview .plot-legend")).toContainText("curved tail");
  });

  test("example run enables the .R script download", async () => {
    test.setTimeout(360000);
    await page.getByRole("button", { name: "Run Example Analysis" }).click();
    await expect(page.locator("#export-r")).toBeEnabled({ timeout: 330000 });
    const code = await page.evaluate(
      () => document.getElementById("stats").dataset.rCode);
    expect(code).toContain("R script generated by Figura");
    expect(code).toContain("Example data embedded");
    // clicking the button performs a real download: journal filename, and the
    // file's bytes are exactly the staged script
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.locator("#export-r").click(),
    ]);
    expect(download.suggestedFilename()).toBe("summary-script.R");
    const saved = fs.readFileSync(await download.path(), "utf8");
    expect(saved).toBe(code);
    // switching analyses clears the stale script
    await page.getByRole("button", { name: "Kaplan-Meier" }).click();
    await expect(page.locator("#export-r")).toBeDisabled();
  });

  // LAST IN THE BLOCK ON PURPOSE: the only test here that renders into the
  // guided shell's `user` context. See the block comment above.
  test("demo and user results are separate contexts; checklist controls the table", async () => {
    test.setTimeout(360000);
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
});

test("Analyze tab explains the expected CSV and offers an example download", async ({ page }) => {
  await page.goto("/#summary/analyze");
  await page.getByRole("button", { name: /summary statistics/i }).click();
  await expect(page.getByText("What your CSV should look like")).toBeVisible();
  await expect(page.locator("#example-csv")).toHaveAttribute("download", "example-baseline.csv");
  const href = await page.locator("#example-csv").getAttribute("href");
  expect(href).toMatch(/^blob:/);                       // client-side Blob — no network egress
});

test("upload form has the Q–Q toggle, default off", async ({ page }) => {
  await page.goto("/#summary/analyze");
  await page.getByRole("button", { name: /summary statistics/i }).click();
  await page.locator("#csv").setInputFiles(
    path.join(__dirname, "..", "testthat", "fixtures", "summary-demo.csv"));
  await expect(page.locator("#summary-vars")).toBeVisible();
  await expect(page.locator("#showqq")).not.toBeChecked();
});
