// web/guided/km/teaching-visual.js
export const TEACHING_VISUAL_ALT =
  "Annotated illustration of a Kaplan-Meier plot: downward steps are observed events; " +
  "small crosses are censored follow-up; the shaded band is the 95% pointwise confidence " +
  "interval; the dashed line at 50% shows where median survival is read; a number-at-risk " +
  "row underneath shows how many participants still support the curve.";

export const TEACHING_VISUAL_SVG = `
<svg viewBox="0 0 560 330" role="img" xmlns="http://www.w3.org/2000/svg"
     style="max-width:100%;height:auto;font-family:system-ui,sans-serif">
  <text x="16" y="20" font-size="13" font-weight="bold" fill="#88400a">Illustration — not computed data</text>
  <g stroke="#333" stroke-width="1">
    <line x1="50" y1="40" x2="50" y2="240"/><line x1="50" y1="240" x2="520" y2="240"/>
  </g>
  <text x="20" y="145" font-size="11" transform="rotate(-90 20 145)">Survival probability</text>
  <text x="260" y="262" font-size="11">Time since time zero</text>
  <path d="M50 60 L150 60 L150 95 L240 95 L240 140 L360 140 L360 185 L470 185"
        fill="none" stroke="#4477AA" stroke-width="2.5"/>
  <path d="M50 55 L150 55 L150 80 L240 80 L240 120 L360 120 L360 155 L470 155
           L470 215 L360 215 L360 165 L240 165 L240 112 L150 112 L150 68 L50 68 Z"
        fill="#4477AA" fill-opacity="0.14" stroke="none"/>
  <g stroke="#4477AA" stroke-width="2">
    <line x1="195" y1="90" x2="195" y2="100"/><line x1="200" y1="90" x2="200" y2="100"/>
    <line x1="300" y1="135" x2="300" y2="145"/>
  </g>
  <line x1="50" y1="150" x2="520" y2="150" stroke="#999" stroke-dasharray="5 4"/>
  <text x="474" y="147" font-size="10" fill="#666">50% → median</text>
  <g font-size="10.5" fill="#88400a">
    <text x="155" y="52">↓ step = observed event</text>
    <text x="255" y="112">+ = censored (follow-up ended, no event)</text>
    <text x="368" y="132">shaded band = 95% CI</text>
  </g>
  <g font-size="11">
    <text x="16" y="292" font-weight="bold">Number at risk</text>
    <text x="50" y="310">120</text><text x="150" y="310">96</text><text x="240" y="310">71</text>
    <text x="360" y="310">38</text><text x="470" y="310">9</text>
    <text x="490" y="310" font-size="10" fill="#88400a">← sparse tail: read cautiously</text>
  </g>
</svg>`;
