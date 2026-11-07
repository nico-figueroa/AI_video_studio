import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const require = createRequire(import.meta.url);
const compiler = join(dirname(require.resolve("typescript/package.json")), "bin", "tsc");
const directory = await mkdtemp(join(tmpdir(),"studio-loading-test-"));
let javascript;
try {
  execFileSync(process.execPath,[compiler,"--ignoreConfig","--skipLibCheck","--target","es2022","--module","es2022","--outDir",directory,
    fileURLToPath(new URL("../services/loading-message-service.ts",import.meta.url))]);
  javascript = await readFile(join(directory,"loading-message-service.js"),"utf8");
} finally {
  await rm(directory,{ recursive:true });
}
const { LoadingMessageService, loadingMessages } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

for (const [locale, workflows] of Object.entries(loadingMessages)) {
  for (const [workflow, messages] of Object.entries(workflows)) {
    test(`${locale}/${workflow}: twenty unique messages, exhaust before repeat, randomized cycles`, () => {
      assert.ok(messages.length >= 20);
      assert.equal(new Set(messages).size, messages.length);
      const bag = new LoadingMessageService(messages, () => .3);
      const first = Array.from({ length:messages.length }, () => bag.next());
      const second = Array.from({ length:messages.length }, () => bag.next());
      assert.equal(new Set(first).size,messages.length);
      assert.equal(new Set(second).size,messages.length);
      assert.notEqual(first.at(-1),second[0]);
      assert.notDeepEqual(first,messages);
      const different = new LoadingMessageService(messages, () => .8);
      assert.notDeepEqual(first,Array.from({ length:messages.length }, () => different.next()));
    });
  }
}
