export function renderConsortForm(container, onSubmit) {
  container.innerHTML = `
    <h2>CONSORT diagram</h2>
    <p>One node per line (main flow):</p>
    <textarea id="nodes" rows="6" cols="40">Assessed for eligibility (n=200)
Randomized (n=150)
Allocated to treatment (n=75)</textarea>
    <p>Exclusions (one per line, optional):</p>
    <textarea id="excl" rows="3" cols="40">Excluded (n=50)</textarea>
    <button type="button" id="render">Render</button>`;
  const lines = (id) => container.querySelector(id).value
    .split("\n").map((s) => s.trim()).filter(Boolean).map((t) => ({ text: t }));
  container.querySelector("#render").onclick = () =>
    onSubmit({ figure: "consort", nodes: lines("#nodes"), exclusions: lines("#excl") });
}
