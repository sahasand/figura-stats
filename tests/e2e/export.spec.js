// tests/e2e/export.spec.js — the download feature exists FOR JOURNAL
// SUBMISSION: the PNG must carry a real pHYs DPI stamp (journals read
// unstamped canvas PNGs as 72 dpi), filenames must be submission-friendly,
// and tables must export as editable text.
const { test, expect } = require("@playwright/test");

test.use({ permissions: ["clipboard-read", "clipboard-write"] });

function pngDpi(buf) {
  for (let pos = 8; pos + 12 <= buf.length;) {
    const len = buf.readUInt32BE(pos);
    const type = buf.toString("ascii", pos + 4, pos + 8);
    if (type === "pHYs") return Math.round(buf.readUInt32BE(pos + 8) / 39.3701);
    pos += 12 + len;
  }
  return null;
}

async function downloadBuffer(page, trigger) {
  const [download] = await Promise.all([page.waitForEvent("download"), trigger()]);
  const chunks = [];
  for await (const c of await download.createReadStream()) chunks.push(c);
  return { name: download.suggestedFilename(), buf: Buffer.concat(chunks) };
}

test("export toolbars start disabled with journal-ready framing", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Journal-ready download:")).toBeVisible();
  await expect(page.locator("#export-dpi")).toHaveValue("600");   // journal default
  for (const id of ["#export-png", "#export-svg", "#export-copy", "#export-tsv"])
    await expect(page.locator(id)).toBeDisabled();
  await expect(page.locator("#export-panels")).toBeHidden();
});

test("journal-grade exports: 600dpi-stamped PNG, stitched SVG, per-panel row, tsv, copy", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#summary/example");
  await page.getByRole("button", { name: /summary statistics/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 330000 });
  await expect(page.locator("#export-png")).toBeEnabled();

  // PNG: journal filename, PNG magic bytes, true 600 dpi in the pHYs chunk.
  const png = await downloadBuffer(page, () => page.locator("#export-png").click());
  expect(png.name).toBe("summary-figure-600dpi.png");
  expect(png.buf.subarray(0, 8)).toEqual(
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
  expect(pngDpi(png.buf)).toBe(600);

  // DPI picker changes both the raster and the filename.
  await page.locator("#export-dpi").selectOption("300");
  const png300 = await downloadBuffer(page, () => page.locator("#export-png").click());
  expect(png300.name).toBe("summary-figure-300dpi.png");
  expect(pngDpi(png300.buf)).toBe(300);
  expect(png300.buf.length).toBeLessThan(png.buf.length);

  // SVG: one stitched file wrapping both panels.
  const svg = await downloadBuffer(page, () => page.locator("#export-svg").click());
  expect(svg.name).toBe("summary-figure.svg");
  const svgText = svg.buf.toString("utf8");
  expect(svgText.startsWith("<svg")).toBe(true);
  expect((svgText.match(/<svg/g) || []).length).toBeGreaterThanOrEqual(3); // wrapper + 2 panels

  // Per-panel row: visible with 2 panels, panel-numbered filename.
  await expect(page.locator("#export-panels")).toBeVisible();
  const panel2 = await downloadBuffer(page,
    () => page.locator("#export-panels button", { hasText: "SVG" }).nth(1).click());
  expect(panel2.name).toBe("summary-panel-2.svg");

  // Table + methods text: .tsv download and clipboard copy (editable text —
  // what journals require for tables).
  const tsv = await downloadBuffer(page, () => page.locator("#export-tsv").click());
  expect(tsv.name).toBe("summary-output.tsv");
  expect(tsv.buf.toString("utf8")).toMatch(/^Characteristic\t/);
  await page.locator("#export-copy").click();
  await expect(page.locator("#export-feedback-console")).toHaveText("Copied as a table for Word");
  const clip = await page.evaluate(() => navigator.clipboard.readText());
  expect(clip).toMatch(/^Characteristic\t/);

  // The same copy carries an HTML flavour, so a paste into Word is a real
  // table rather than tab-separated text: one table, the on-screen header,
  // indented factor levels, the methods text as paragraphs, and none of the
  // on-screen ".why" teaching notes.
  const rich = await page.evaluate(async () => {
    for (const item of await navigator.clipboard.read())
      if (item.types.includes("text/html"))
        return (await item.getType("text/html")).text();
    return null;
  });
  expect(rich).not.toBeNull();
  const pasted = await page.evaluate((html) => {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const rows = [...doc.querySelectorAll("tbody tr")];
    return {
      tables: doc.querySelectorAll("table").length,
      header: [...doc.querySelectorAll("thead th")].map((th) => th.textContent),
      bodyRows: rows.length,
      firstCells: rows.map((tr) => tr.children[0].textContent),
      paragraphs: [...doc.querySelectorAll("p")].map((p) => p.textContent),
    };
  }, rich);
  const screen = await page.evaluate(() => ({
    header: [...document.querySelectorAll("#preview table.table1 thead th")].map((th) => th.textContent),
    bodyRows: document.querySelectorAll("#preview table.table1 tbody tr").length,
    why: document.querySelector("#preview table.table1 .why").textContent,
  }));
  expect(pasted.tables).toBe(1);
  expect(pasted.header).toEqual(screen.header);
  expect(pasted.bodyRows).toBe(screen.bodyRows);
  expect(pasted.firstCells).toContain("\u00a0\u00a0\u00a0\u00a0Female");
  expect(pasted.firstCells.join("|")).not.toContain(screen.why);
  expect(pasted.paragraphs.length).toBeGreaterThanOrEqual(2);
  expect(pasted.paragraphs.join(" ")).toContain("figurastats.org");

  // Switching analyses clears the shared output — a stale figure must never
  // export under the new analysis's filename (journal correctness).
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await expect(page.locator("#preview svg")).toHaveCount(0);
  await expect(page.locator("#export-png")).toBeDisabled();
  await expect(page.locator("#export-tsv")).toBeDisabled();
});
