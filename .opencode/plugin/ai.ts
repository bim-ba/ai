// Dogfood: load the opencode adapter from the in-repo package so the repo itself
// runs as an opencode project (used by the Phase B smoke test). config() is
// existence-guarded and the package's synced assets are absent in-repo, so only
// the session.idle drift-log hook activates here; instructions + skills come from
// the canonical paths in ../../opencode.json.
export { default } from "../../packages/ai-opencode/src/plugin"
