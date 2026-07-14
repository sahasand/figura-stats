const { test, expect } = require("@playwright/test");

test("forest plot renders an SVG end to end", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /forest/i }).click();
  await page.getByLabel(/effect label/i).fill("Hazard Ratio");
  await page.getByRole("button", { name: /add row/i }).click();
  await page.getByLabel(/label/i).first().fill("Overall");
  await page.getByLabel(/estimate/i).first().fill("0.72");
  await page.getByLabel(/lower/i).first().fill("0.55");
  await page.getByLabel(/upper/i).first().fill("0.94");
  await page.getByRole("button", { name: /render/i }).click();
  // First run downloads the webR runtime + packages, so allow plenty of time.
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 200000 });
});
