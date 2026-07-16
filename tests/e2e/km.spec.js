const { test, expect } = require("@playwright/test");
const path = require("path");

// The first KM render triggers the LAZY survival+cowplot download in webR,
// which is slow, hence the very generous timeouts.
test("kaplan-meier plot renders an SVG from an uploaded CSV", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await page.getByRole("tab", { name: "Analyze Your Data" }).click();
  await page.locator("#csv").setInputFiles(path.join(__dirname, "fixtures", "km.csv"));
  await expect(page.locator("#km-config")).toBeVisible();       // progressive reveal
  await page.locator("#cp_time").selectOption("followup_months");
  await page.locator("#cp_status").selectOption("status");
  await page.locator("#cp_group").selectOption("group");
  await page.locator("#km-event").selectOption("Death");
  await page.getByRole("button", { name: /render/i }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 330000 });
});
