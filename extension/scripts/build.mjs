import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const sourceDir = join(root, "src");
const distDir = join(root, "dist");
const baseManifest = JSON.parse(await readFile(join(root, "manifest.base.json"), "utf8"));

await rm(distDir, { recursive: true, force: true });

for (const browserName of ["chrome", "firefox"]) {
  const output = join(distDir, browserName);
  await mkdir(output, { recursive: true });
  await cp(sourceDir, output, { recursive: true });

  const manifest = structuredClone(baseManifest);
  if (browserName === "chrome") {
    manifest.minimum_chrome_version = "116";
    manifest.background = { service_worker: "background.js" };
  } else {
    manifest.background = { scripts: ["common.js", "background.js"] };
    manifest.browser_specific_settings = {
      gecko: {
        id: "exam-guard@datt.local",
        strict_min_version: "140.0",
        data_collection_permissions: {
          required: [
            "personallyIdentifyingInfo",
            "authenticationInfo",
            "browsingActivity",
            "websiteActivity"
          ],
          optional: ["technicalAndInteraction"]
        }
      },
      gecko_android: {
        strict_min_version: "999.0"
      }
    };
  }
  await writeFile(join(output, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
}

console.log("Built dist/chrome and dist/firefox");
