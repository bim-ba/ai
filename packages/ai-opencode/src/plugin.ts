import type { Plugin } from "@opencode-ai/plugin"
import { existsSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { join } from "node:path"

// Package root = parent of this src/ dir. After publish the bundled assets sit here.
const PKG_ROOT = fileURLToPath(new URL("../", import.meta.url))
const PROTOCOL = join(PKG_ROOT, "behaviour-protocol.md")
const SKILLS_DIR = join(PKG_ROOT, "skills")

/**
 * Append the behaviour-protocol path to `instructions` and the skills dir to
 * `skills.paths`, only if each exists on disk. Idempotent and non-destructive:
 * existing entries are preserved, duplicates are not added.
 */
export function applyConfig(cfg: any, paths: { protocol: string; skillsDir: string }): any {
  if (existsSync(paths.protocol)) {
    cfg.instructions ??= []
    if (!cfg.instructions.includes(paths.protocol)) cfg.instructions.push(paths.protocol)
  }
  if (existsSync(paths.skillsDir)) {
    cfg.skills ??= {}
    cfg.skills.paths ??= []
    if (!cfg.skills.paths.includes(paths.skillsDir)) cfg.skills.paths.push(paths.skillsDir)
  }
  return cfg
}

export const AiOpencode: Plugin = async () => {
  return {
    config(cfg: any) {
      applyConfig(cfg, { protocol: PROTOCOL, skillsDir: SKILLS_DIR })
    },
  }
}

export default AiOpencode
