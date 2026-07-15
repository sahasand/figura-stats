// web/guided/session-state.js
// In-memory only — no localStorage/IndexedDB anywhere in this module (privacy
// invariant: reload starts a clean Analysis Session).
export const STAGES = ["understand", "example", "analyze"];
const DEFAULT_DEMO_OPTIONS = () => ({ conf_int: true, landmarks: [], horizon: null });

export function createKmSession() {
  return { stage: "understand", results: { demo: null, user: null },
           demoOptions: DEFAULT_DEMO_OPTIONS(), demoGeneration: 0 };
}
export function setStage(session, stage) {
  if (!STAGES.includes(stage)) throw new Error(`Unknown stage: ${stage}`);
  return { ...session, stage };
}
export function storeResult(session, context, result) {
  return { ...session, results: { ...session.results, [context]: result } };
}
export function getResult(session, context) {
  return session.results[context] ?? null;
}
export function setDemoOptions(session, patch) {
  return { ...session, demoOptions: { ...session.demoOptions, ...patch } };
}
export function resetDemo(session) {
  // Bumping the generation invalidates any demo run started before this reset:
  // its async result must neither store nor paint (see isDemoGenerationCurrent).
  return { ...session, results: { ...session.results, demo: null },
           demoOptions: DEFAULT_DEMO_OPTIONS(),
           demoGeneration: session.demoGeneration + 1 };
}

// Snapshot the demo generation at the moment a demo run is launched; compare it
// against the live session when the run resolves. A mismatch means Reset Example
// fired mid-run, so the in-flight result is stale and must be discarded.
export function getDemoGeneration(session) {
  return session.demoGeneration;
}
export function isDemoGenerationCurrent(session, generation) {
  return session.demoGeneration === generation;
}
