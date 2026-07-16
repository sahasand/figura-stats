const { test, expect } = require("@playwright/test");

// Boot check only: the guided specs cover full webR renders. This guards the
// nav — exactly the three guided analyses, in order, plus the empty state.
test("app boots with exactly the three guided analyses", async ({ page }) => {
  await page.goto("/");
  const nav = page.locator("nav button[data-figure]");
  await expect(nav).toHaveCount(3);
  await expect(nav.nth(0)).toHaveText("Summary statistics");
  await expect(nav.nth(1)).toHaveText("Kaplan-Meier");
  await expect(nav.nth(2)).toHaveText("Explore plot");
  await expect(page.getByText("Select an analysis on the left to begin.")).toBeVisible();
});
