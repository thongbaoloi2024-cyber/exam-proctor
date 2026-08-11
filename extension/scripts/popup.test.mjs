import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { constants } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const extensionRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

test("toolbar action opens setup as its popup", async () => {
  const manifest = JSON.parse(await readFile(join(extensionRoot, "manifest.base.json"), "utf8"));
  assert.equal(manifest.action.default_popup, "setup.html");

  const background = await readFile(join(extensionRoot, "src", "background.js"), "utf8");
  assert.doesNotMatch(background, /action\.onClicked/);
  assert.doesNotMatch(background, /getURL\(["']setup\.html["']\)/);

  const setupScript = await readFile(join(extensionRoot, "src", "setup.js"), "utf8");
  assert.match(setupScript, /type:\s*["']DATT_GOOGLE_LOGIN["']/);
  assert.doesNotMatch(setupScript, /launchWebAuthFlow/);
});

test("setup is panel-sized and legacy monitor pages are not shipped", async () => {
  const setupHtml = await readFile(join(extensionRoot, "src", "setup.html"), "utf8");
  const setupScript = await readFile(join(extensionRoot, "src", "setup.js"), "utf8");
  const styles = await readFile(join(extensionRoot, "src", "styles.css"), "utf8");
  assert.match(setupHtml, /<html lang="vi" class="setup-page">/);
  assert.match(setupHtml, /<body class="setup-body">/);
  assert.doesNotMatch(setupHtml, /backend-url|Địa chỉ backend/);
  assert.match(setupScript, /const BACKEND_URL = "http:\/\/localhost:8000"/);
  assert.doesNotMatch(setupScript, /element\(["']backend-url["']\)/);
  assert.match(styles, /\.setup-page\s*\{[^}]*width:\s*400px/s);
  assert.match(styles, /\.setup-body\s*\{[^}]*width:\s*100%/s);

  for (const filename of ["monitor.html", "monitor.js"]) {
    await assert.rejects(access(join(extensionRoot, "src", filename), constants.F_OK));
  }
});

test("valid join code advances to candidate authentication before exam details", async () => {
  const setupHtml = await readFile(join(extensionRoot, "src", "setup.html"), "utf8");
  const setupScript = await readFile(join(extensionRoot, "src", "setup.js"), "utf8");

  assert.ok(setupHtml.indexOf('id="manual-fields"') < setupHtml.indexOf('id="policy-list"'));
  assert.ok(setupHtml.indexOf('id="google-fields"') < setupHtml.indexOf('id="policy-list"'));
  assert.match(setupHtml, /id="change-code"/);
  assert.match(setupScript, /element\(["']join-card["']\)\.classList\.add\(["']hidden["']\)/);
  assert.match(setupScript, /element\(["']change-code["']\)\.addEventListener/);
});

test("setup header includes a UI-only issue report button", async () => {
  const setupHtml = await readFile(join(extensionRoot, "src", "setup.html"), "utf8");
  const setupScript = await readFile(join(extensionRoot, "src", "setup.js"), "utf8");
  const styles = await readFile(join(extensionRoot, "src", "styles.css"), "utf8");

  assert.match(setupHtml, /id="report-issue"/);
  assert.match(setupHtml, /aria-label="Báo cáo sự cố"/);
  assert.match(setupHtml, /class="report-issue-button"[\s\S]*?<svg/);
  assert.match(styles, /\.report-issue-button\s*\{/);
  assert.doesNotMatch(setupScript, /element\(["']report-issue["']\)\.addEventListener/);
});
