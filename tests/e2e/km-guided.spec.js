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

// ---------------------------------------------------------------------------
// THE HEAVY TESTS, ON ONE BOOTED webR RUNTIME.
//
// Each test below fits a real Cox/KM model in webR. The runtime lives in the
// page's Web Worker, so a fresh Playwright page per test means a fresh worker,
// which means re-downloading the wasm runtime and re-installing survival +
// cowplot for every one of them — the cost this block exists to pay once.
//
// MECHANISM: `describe.serial` + a page created in `beforeAll`, NOT a
// worker-scoped fixture. Both share one page; serial mode is simpler here
// because it needs no fixture file, keeps the page visible in the same file as
// the tests that use it, and adds the property a shared mutable page actually
// wants — if one test leaves the app in an unexpected state, the rest of the
// block is skipped rather than reporting cascading noise. A worker fixture
// would buy sharing ACROSS files, which these two suites do not need (each
// runs in its own worker anyway).
//
// ISOLATION, NOT COUPLING. A shared page is only safe if each test establishes
// its own starting state instead of inheriting the last one's. `beforeEach`
// does that explicitly and ASSERTS it: remount the analysis from the nav (which
// app.js clears #preview/#stats for), select the Example stage, then press the
// app's own Reset Example — which drops the stored demo result and restores the
// default experiment controls — and check all three facts. No test here reads a
// value another test produced.
//
// The one state a shared page cannot reset is the guided shell's `user`
// context: the session survives nav switches by design and there is no "clear
// my upload" control. That is fine here because exactly ONE test in this file
// renders into the user context, and it is the last in the block — its
// "user context empty" assertion is a property of the file, not an inheritance
// from a neighbour. A second user-rendering test added to this block would
// break that assertion loudly (which is the correct direction); give it its own
// page, or run it before this one.
test.describe.serial("KM example stage, on one booted webR runtime", () => {
  let page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    await page.goto("/");
  });

  test.afterAll(async () => {
    if (page) await page.close();
  });

  test.beforeEach(async () => {
    await page.getByRole("button", { name: /kaplan-meier/i }).click();
    await page.getByRole("tab", { name: "Try an Example" }).click();
    await page.getByRole("button", { name: "Reset Example" }).click();
    // Asserted, not assumed: this is the precondition every test below starts
    // from, so a failure to reach it must be a loud failure of its own.
    await expect(page.locator("#preview svg")).toHaveCount(0);
    await expect(page.locator("#stats")).toBeEmpty();
    await expect(page.locator("#exp-landmarks")).not.toBeChecked();
  });

  test("Run Example Analysis computes the real pinned demo result", async () => {
    test.setTimeout(360000); // first run installs survival+cowplot in webR
    await expect(page.getByText("Synthetic demonstration data")).toBeVisible();
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

  test("landmark experiment adds 12/24-month estimates and Reset restores defaults", async () => {
    test.setTimeout(360000);
    await page.getByRole("button", { name: "Run Example Analysis" }).click();
    await expect(page.locator("#preview svg")).toBeVisible({ timeout: 330000 });
    await page.locator("#exp-landmarks").check();
    await expect(page.locator("#stats")).toContainText("At 12.0 Months since randomization, survival was 73.5%",
      { timeout: 120000 });   // packages cached now; rerun is fast
    await page.getByRole("button", { name: "Reset Example" }).click();
    await expect(page.locator("#exp-landmarks")).not.toBeChecked();
    await expect(page.locator("#preview svg")).toHaveCount(0);   // demo result cleared
  });

  // LAST IN THE BLOCK ON PURPOSE: the only test here that renders into the
  // guided shell's `user` context, which nothing can reset without a reload.
  // See the block comment above before adding another one.
  test("demo and user results are separate contexts", async () => {
    test.setTimeout(360000);
    await page.getByRole("button", { name: "Run Example Analysis" }).click();
    await expect(page.locator("#stats")).toContainText("p = 0.108", { timeout: 330000 });
    await page.getByRole("tab", { name: "Analyze Your Data" }).click();
    await expect(page.locator("#preview svg")).toHaveCount(0);   // user context empty
    await page.locator("#csv").setInputFiles(path.join(__dirname, "fixtures", "km.csv"));
    await expect(page.locator("#km-config")).toBeVisible();       // progressive reveal
    await page.locator("#cp_time").selectOption("followup_months");
    await page.locator("#cp_status").selectOption("status");
    await page.locator("#cp_group").selectOption("group");
    await page.locator("#km-event").selectOption("Death");
    await page.getByRole("button", { name: /render/i }).click();
    await expect(page.locator("#preview svg")).toBeVisible({ timeout: 120000 });
    await page.getByRole("tab", { name: "Try an Example" }).click();
    await expect(page.locator("#stats")).toContainText("p = 0.108");  // demo restored
  });
});

test("Analyze tab explains the CSV and offers the example download", async ({ page }) => {
  await page.goto("/#km/analyze");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await expect(page.getByText("What your CSV should look like")).toBeVisible();
  await expect(page.locator("#example-csv")).toHaveAttribute("download", "example-survival.csv");
  const href = await page.locator("#example-csv").getAttribute("href");
  expect(href).toMatch(/^blob:/);                     // client-side Blob — no egress
  await expect(page.locator("#km-config")).toBeHidden();  // nothing before a file
});
