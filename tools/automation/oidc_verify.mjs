import { createPublicKey, verify } from "node:crypto";
import { readFileSync } from "node:fs";

const input = JSON.parse(readFileSync(0, "utf8"));
const { token, jwks } = input;
const parts = String(token).split(".");
if (parts.length !== 3) { console.log(JSON.stringify({ ok: false, error: "MALFORMED_JWT" })); process.exit(0); }
const [h, p, s] = parts;
const header = JSON.parse(Buffer.from(h, "base64url"));
if (header.alg !== "RS256") { console.log(JSON.stringify({ ok: false, error: "BAD_ALG" })); process.exit(0); }
const keyJwk = (jwks.keys || []).find((k) => k.kid === header.kid);
if (!keyJwk) { console.log(JSON.stringify({ ok: false, error: "UNKNOWN_KID" })); process.exit(0); }
const key = createPublicKey({ key: keyJwk, format: "jwk" });
const ok = verify("RSA-SHA256", Buffer.from(`${h}.${p}`), key, Buffer.from(s, "base64url"));
if (!ok) { console.log(JSON.stringify({ ok: false, error: "BAD_SIGNATURE" })); process.exit(0); }
const claims = JSON.parse(Buffer.from(p, "base64url"));
const now = Math.floor(Date.now() / 1000);
if (claims.iss !== "https://token.actions.githubusercontent.com") { console.log(JSON.stringify({ ok: false, error: "BAD_ISSUER" })); process.exit(0); }
if (claims.exp <= now || (claims.nbf && claims.nbf > now)) { console.log(JSON.stringify({ ok: false, error: "EXPIRED" })); process.exit(0); }
const aud = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
if (!aud.includes("dsh-publisher")) { console.log(JSON.stringify({ ok: false, error: "BAD_AUDIENCE" })); process.exit(0); }
if (claims.repository !== "wijouyang-lab/us") { console.log(JSON.stringify({ ok: false, error: "BAD_REPOSITORY" })); process.exit(0); }
if (claims.workflow_ref !== "wijouyang-lab/us/.github/workflows/dsh-task.yml@refs/heads/deploy/dsh-automation-p0") { console.log(JSON.stringify({ ok: false, error: "BAD_WORKFLOW_REF" })); process.exit(0); }
if (claims.ref !== "refs/heads/deploy/dsh-automation-p0") { console.log(JSON.stringify({ ok: false, error: "BAD_REF" })); process.exit(0); }
if (claims.event_name !== "workflow_dispatch") { console.log(JSON.stringify({ ok: false, error: "BAD_EVENT" })); process.exit(0); }
if (String(claims.run_id) !== "123456") { console.log(JSON.stringify({ ok: false, error: "BAD_RUN_ID" })); process.exit(0); }
console.log(JSON.stringify({ ok: true, claims }));
