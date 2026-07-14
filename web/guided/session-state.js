// web/guided/session-state.js
// In-memory only — no localStorage/IndexedDB anywhere in this module (privacy
// invariant: reload starts a clean Analysis Session).
export const STAGES = ["understand", "example", "analyze"];
const DEFAULT_DEMO_OPTIONS = () => ({ conf_int: true, landmarks: [], horizon: null });

export function createKmSession() {
  return { stage: "understand", results: { demo: null, user: null },
           demoOptions: DEFAULT_DEMO_OPTIONS() };
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
  return { ...session, results: { ...session.results, demo: null },
           demoOptions: DEFAULT_DEMO_OPTIONS() };
}
