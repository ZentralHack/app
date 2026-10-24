/* The developer menu must never reach a normal build. Builds once without VITE_DEV_TOOLS and searches the output. */
import { execFileSync } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const MARKERS = ["fundpilot.dev.lastRun", "Noch kein fertiger Lauf", "dev-menu"];

function files(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e => (e.isDirectory() ? files(join(dir, e.name)) : [join(dir, e.name)]));
}

it("production build contains no developer menu", { timeout: 180_000 }, () => {
  const out = mkdtempSync(join(tmpdir(), "fundpilot-build-"));
  try {
    const env = { ...process.env, VITE_DEV_TOOLS: "" };
    execFileSync(process.execPath, [join(ROOT, "node_modules/vite/bin/vite.js"), "build", "--outDir", out, "--emptyOutDir", "--logLevel", "error"], { cwd: ROOT, env, stdio: "pipe" });
    const text = files(out)
      .filter(f => /\.(js|html|css)$/.test(f))
      .map(f => readFileSync(f, "utf-8"))
      .join("\n");
    expect(text.length).toBeGreaterThan(1000);
    for (const marker of MARKERS) expect(text, marker).not.toContain(marker);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});
