const { test, expect } = require("@playwright/test");

test("explore shows three tabs and syncs the hash", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /explore plot/i }).click();
  await expect(page.getByRole("tab", { name: "Understand" })).toBeVisible();
  await page.getByRole("tab", { name: "Try an Example" }).click();
  expect(page.url()).toContain("#explore/example");
});

test("demo renders live: geom switch re-renders and code follows", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#explore/example");
  await page.getByRole("button", { name: /explore plot/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 300000 });
  await expect(page.locator("#stats")).toContainText("geom_point");
  await expect(page.locator("#stats")).toContainText("library(ggplot2)");

  // Switch to boxplot: controls stay enabled, plot + code update.
  await page.locator("#explore-geom").selectOption("boxplot");
  await page.locator("#cp_x").selectOption("arm");
  await page.locator("#cp_y").selectOption("biomarker");
  await expect(page.locator("#stats")).toContainText("geom_boxplot", { timeout: 120000 });
  await expect(page.locator("#preview svg")).toBeVisible();

  // Rapid-fire two option changes: final state matches the LAST change.
  // force: the live boxplot SVG landing in the sibling #preview reflows the page
  // mid-click, so an ordinary .check() hit-test can land on the wrapping div; the
  // checkbox nodes themselves are never rebuilt between these toggles.
  await page.locator("#opt-jitter").check({ force: true });
  await page.locator("#opt-notch").check({ force: true });
  await expect(page.locator("#stats")).toContainText("notch = TRUE", { timeout: 120000 });

  // Reverse cross-type switch (Task 7 reconcile fix): boxplot's categorical
  // x=arm is invalid for scatter's numeric x picker, so switching back to
  // scatter must reset #cp_x to "" and fire NO render until x is re-picked.
  await page.locator("#explore-geom").selectOption("scatter");
  await expect(page.locator("#cp_x")).toHaveValue("");
  await page.locator("#cp_x").selectOption("age");
  await page.locator("#cp_y").selectOption("biomarker");
  await expect(page.locator("#stats")).toContainText("geom_point", { timeout: 120000 });
});

test("text toolbar is R-aware on explore and tsv elsewhere", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /explore plot/i }).click();
  await expect(page.locator("#export-tsv")).toHaveText(".R");
  await expect(page.locator("#export-copy")).toHaveText("Copy R code");
  await page.getByRole("button", { name: /summary statistics/i }).click();
  await expect(page.locator("#export-tsv")).toHaveText(".tsv");
  await expect(page.locator("#export-copy")).toHaveText("Copy");
});

test("analyze stage is progressive and renders an uploaded CSV live", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#explore/analyze");
  await page.getByRole("button", { name: /explore plot/i }).click();
  await expect(page.locator("#csv")).toBeVisible();
  await expect(page.locator("#explore-config")).toBeHidden();
  const csv = "age,bmi,arm\n" + Array.from({ length: 20 }, (_, i) =>
    `${40 + i},${(22 + (i % 6)).toFixed(1)},${i % 2 ? "T" : "C"}`).join("\n");
  await page.locator("#csv").setInputFiles({
    name: "mini.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await expect(page.locator("#explore-config")).toBeVisible();
  // The example panel renders its own builder with the same control ids, so
  // scope to the analyze panel to keep #cp_x/#cp_y unambiguous in strict mode.
  const analyze = page.locator("#panel-analyze");
  await analyze.locator("#cp_x").selectOption("age");
  await analyze.locator("#cp_y").selectOption("bmi");
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 300000 });
  await expect(page.locator("#stats")).toContainText('.data[["age"]]');
});
