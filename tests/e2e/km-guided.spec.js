const { test, expect } = require("@playwright/test");

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
