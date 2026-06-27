import { test, expect, beforeAll, afterAll } from "bun:test"
import { mkdtempSync, writeFileSync, mkdirSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { applyConfig } from "./plugin"

let dir: string
let protocol: string
let skillsDir: string

beforeAll(() => {
  dir = mkdtempSync(join(tmpdir(), "ai-opencode-"))
  protocol = join(dir, "behaviour-protocol.md")
  skillsDir = join(dir, "skills")
  writeFileSync(protocol, "# protocol")
  mkdirSync(skillsDir)
})
afterAll(() => rmSync(dir, { recursive: true, force: true }))

test("applyConfig appends protocol to instructions and skills dir to skills.paths", () => {
  const cfg: any = {}
  applyConfig(cfg, { protocol, skillsDir })
  expect(cfg.instructions).toEqual([protocol])
  expect(cfg.skills.paths).toEqual([skillsDir])
})

test("applyConfig is non-destructive: existing entries are preserved", () => {
  const cfg: any = { instructions: ["existing.md"], skills: { paths: ["/other/skills"] }, customKey: 1 }
  applyConfig(cfg, { protocol, skillsDir })
  expect(cfg.instructions).toEqual(["existing.md", protocol])
  expect(cfg.skills.paths).toEqual(["/other/skills", skillsDir])
  expect(cfg.customKey).toBe(1)
})

test("applyConfig is idempotent: a second call adds no duplicates", () => {
  const cfg: any = {}
  applyConfig(cfg, { protocol, skillsDir })
  applyConfig(cfg, { protocol, skillsDir })
  expect(cfg.instructions).toEqual([protocol])
  expect(cfg.skills.paths).toEqual([skillsDir])
})

test("applyConfig no-ops for paths that do not exist", () => {
  const cfg: any = {}
  applyConfig(cfg, { protocol: join(dir, "missing.md"), skillsDir: join(dir, "missing") })
  expect(cfg.instructions).toBeUndefined()
  expect(cfg.skills).toBeUndefined()
})
