import { spawnSync } from "node:child_process";

process.env.DEEPSEEK_API_KEY = "sk-test-not-real";
process.env.GH_TOKEN = "gh-test-not-real";
process.env.GITHUB_TOKEN = "gh-test-not-real";
process.env.NORMAL_TEST_VAR = "visible";

const mod = await import("../../dsh-runtime/node_modules/@deepseek-ai/dsh-subprocess/lib/index.js");
const env = mod.scrubbedParentEnv();
if (env.DEEPSEEK_API_KEY || env.GH_TOKEN || env.GITHUB_TOKEN) throw new Error("credential leaked in scrub");
if (env.NORMAL_TEST_VAR !== "visible") throw new Error("normal variable not forwarded");
const child = spawnSync(process.execPath, ["-e", "console.log(JSON.stringify({key:!!process.env.DEEPSEEK_API_KEY,gh:!!process.env.GH_TOKEN,normal:process.env.NORMAL_TEST_VAR}))"], { env, encoding: "utf8" });
if (child.status !== 0) throw new Error(child.stderr);
const data = JSON.parse(child.stdout);
if (data.key || data.gh || data.normal !== "visible") throw new Error("child env mismatch");
console.log("DSH_SUBPROCESS_ENV_OK");
