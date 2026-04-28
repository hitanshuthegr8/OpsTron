import { promises as fs } from "node:fs";
import path from "node:path";

const projectRoot = process.cwd();
const clientDir = path.join(projectRoot, "dist", "client");
const assetsDir = path.join(clientDir, "assets");

async function findBootstrapEntry() {
  const entries = await fs.readdir(assetsDir, { withFileTypes: true });
  const jsFiles = entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".js"))
    .map((entry) => entry.name);

  for (const file of jsFiles) {
    const fullPath = path.join(assetsDir, file);
    const contents = await fs.readFile(fullPath, "utf8");

    if (
      contents.includes("hydrateRoot(document") &&
      contents.includes("window.__TSS_START_OPTIONS__")
    ) {
      return file;
    }
  }

  throw new Error(
    `Could not find the client bootstrap bundle in ${assetsDir}. Checked: ${jsFiles.join(", ")}`,
  );
}

async function findStylesheet() {
  const entries = await fs.readdir(assetsDir, { withFileTypes: true });
  const cssFile = entries.find((entry) => entry.isFile() && /^styles-.*\.css$/.test(entry.name));

  if (!cssFile) {
    throw new Error(`Could not find the built stylesheet in ${assetsDir}`);
  }

  return cssFile.name;
}

async function writePagesShell(jsFile, cssFile) {
  const html = `<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>OpsTron - Autonomous Incident Response</title>
    <meta
      name="description"
      content="AI-powered root cause analysis for production incidents."
    />
    <link rel="stylesheet" href="/OpsTron/assets/${cssFile}" />
  </head>
  <body class="min-h-screen bg-background text-foreground antialiased">
    <script type="module" src="/OpsTron/assets/${jsFile}"></script>
  </body>
</html>
`;

  await fs.writeFile(path.join(clientDir, "index.html"), html, "utf8");
  await fs.writeFile(path.join(clientDir, "404.html"), html, "utf8");
}

const jsFile = await findBootstrapEntry();
const cssFile = await findStylesheet();
await writePagesShell(jsFile, cssFile);

console.log(`GitHub Pages shell created with JS=${jsFile} CSS=${cssFile}`);
