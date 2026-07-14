const { test, expect } = require("@playwright/test");
const path = require("path");

// The first KM render triggers the LAZY survminer download in webR (survminer
// plus its dependency tree — ggpubr, rstatix, car, …) which is large and slow,
// hence the very generous timeouts.
test("kaplan-meier plot renders an SVG from an uploaded CSV", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await page.locator("#csv").setInputFiles(path.join(__dirname, "fixtures", "km.csv"));
  await page.getByRole("button", { name: /render/i }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 330000 });
});
