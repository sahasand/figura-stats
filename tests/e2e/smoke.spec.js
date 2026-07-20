const { test, expect } = require("@playwright/test");

// Boot check only: the guided specs cover full webR renders. This guards the
// nav — exactly the six guided analyses, in DOM order, plus the empty state.
test("app boots with exactly the six guided analyses", async ({ page }) => {
  await page.goto("/");
  const nav = page.locator("nav button[data-figure]");
  await expect(nav).toHaveCount(6);
  const labels = nav.locator(".nav-label");
  await expect(labels.nth(0)).toHaveText("Summary statistics");
  await expect(labels.nth(1)).toHaveText("Kaplan-Meier");
  await expect(labels.nth(2)).toHaveText("Group comparison");
  await expect(labels.nth(3)).toHaveText("Cox regression");
  await expect(labels.nth(4)).toHaveText("Logistic regression");
  await expect(labels.nth(5)).toHaveText("Explore plot");
  await expect(page.getByText("Select an analysis on the left to begin.")).toBeVisible();
});
