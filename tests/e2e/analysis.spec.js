const { test, expect } = require("@playwright/test");
const path = require("path");

test("group comparison renders an SVG via the column picker", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /group comparison/i }).click();
  await page.setInputFiles("#csv", path.join(__dirname, "fixtures/groupcompare.csv"));
  // Column picker appears after parse; choose value + group.
  await page.locator("#picker select").first().selectOption("value");
  await page.locator("#picker select").nth(1).selectOption("arm");
  await page.getByRole("button", { name: /render/i }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 200000 });
});
