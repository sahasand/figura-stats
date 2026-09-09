const { test, expect } = require("@playwright/test");

// The landing pages are static HTML; this checks the one thing that crosses
// into the app — the hash deep link — and that the page itself is served with
// its stylesheet and example. No webR render is awaited here; the guided
// specs own that.
test("Kaplan–Meier landing page opens the app on the example stage", async ({ page }) => {
  await page.goto("/kaplan-meier/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Kaplan–Meier survival curves");
  await expect(page.locator(".example svg")).toBeVisible();
  await expect(page.locator("link[rel=canonical]")).toHaveAttribute("href", "https://figurastats.org/kaplan-meier/");
  await page.getByRole("link", { name: "See the worked example" }).click();
  await expect(page).toHaveURL(/#km\/example$/);
  await expect(page.getByRole("button", { name: /kaplan-meier/i })).toHaveAttribute("aria-current", "true");
  await expect(page.getByRole("tab", { name: "Try an Example" })).toHaveAttribute("aria-selected", "true");
});

test("an unknown hash opens the app in its empty state", async ({ page }) => {
  await page.goto("/#nope/analyze");
  await expect(page.getByText("Select an analysis to begin.")).toBeVisible();
});
