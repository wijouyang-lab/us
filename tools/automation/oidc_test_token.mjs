import { generateKeyPairSync, createSign } from "node:crypto";
import { readFileSync } from "node:fs";

let input = {};
try { input = JSON.parse(readFileSync(0, "utf8") || "{}"); } catch { input = {}; }

const { publicKey, privateKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const jwk = publicKey.export({ format: "jwk" });
jwk.kid = "test-kid";
jwk.alg = "RS256";
jwk.use = "sig";
const header = { alg: input.alg || "RS256", typ: "JWT", kid: input.kid || "test-kid" };
const now = Math.floor(Date.now() / 1000);
const claims = {
  iss: "https://token.actions.githubusercontent.com",
  aud: "dsh-publisher",
  exp: now + 600,
  nbf: now - 10,
  iat: now - 10,
  repository: "wijouyang-lab/us",
  repository_id: "1250878532",
  workflow_ref: "wijouyang-lab/us/.github/workflows/dsh-task.yml@refs/heads/deploy/dsh-automation-p0",
  ref: "refs/heads/deploy/dsh-automation-p0",
  event_name: "workflow_dispatch",
  run_id: "123456",
  job_workflow_ref: "wijouyang-lab/us/.github/workflows/dsh-task.yml@refs/heads/deploy/dsh-automation-p0",
  ...(input.claims || {}),
};
for (const k of input.remove || []) delete claims[k];
const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
const unsigned = `${b64(header)}.${b64(claims)}`;
const signer = createSign("RSA-SHA256");
signer.update(unsigned);
const token = `${unsigned}.${signer.sign(privateKey).toString("base64url")}`;
console.log(JSON.stringify({ token, jwks: { keys: [jwk] } }));
