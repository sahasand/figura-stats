// web/guided/explore/content.js
export function renderUnderstand(panel) {
  panel.innerHTML = `
    <h3>Map columns to a picture</h3>
    <p>Every ggplot2 chart answers one question: <em>which column goes where?</em>
      The x and y positions, the colors, and the small-multiple panels (facets)
      are each fed by one column of your data. That mapping — not the chart
      type — is the core idea.</p>
    <h3>Six chart types cover most manuscripts</h3>
    <ul>
      <li><strong>Scatter</strong> — two numeric measures per participant.</li>
      <li><strong>Line</strong> — a measure over time; one line per participant
        needs a <em>Line per</em> column (usually the patient ID).</li>
      <li><strong>Boxplot / Violin</strong> — a numeric measure compared across groups.</li>
      <li><strong>Bar</strong> — counts or proportions of a category.</li>
      <li><strong>Histogram</strong> — the shape of one numeric measure.</li>
    </ul>
    <h3>The code pane is yours to keep</h3>
    <p>Every plot comes with the exact ggplot2 code that drew it. Paste it into
      your own R session with your CSV and you get the same figure — the
      explorer doubles as a ggplot2 tutor.</p>`;
}

export const EXAMPLE_INTRO_HTML = `
  <p>This synthetic trial follows 40 patients over three visits
    (months 0, 3, 6) with a biomarker, age, BMI, ECOG status, and study arm.
    Change anything below — the plot redraws as you explore.</p>`;
