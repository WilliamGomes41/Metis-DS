const { spawnSync } = require('node:child_process');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

const LOOPBACK = new Set(['127.0.0.1', 'localhost', '[::1]']);
const MARKERS = new Set(['trace-too-large', 'trace-unusable']);

function validateFixture(base) {
  try {
    const { hostname, protocol, username, password } = new URL(base);
    if (LOOPBACK.has(hostname) && ['http:', 'https:'].includes(protocol) && !username && !password) {
      return;
    }
  } catch {
    // Invalid and unsupported addresses are reported without echoing input.
  }
  throw Error('browser-evidence-loopback-required');
}

function validateContextOptions(options) {
  if (typeof options.storageState === 'string') {
    throw Error('browser-evidence-storage-state-file');
  }
  if (options.recordHar !== undefined) {
    throw Error('browser-evidence-har-disabled');
  }
}

async function exportFailure(context, temporary, output, prefix) {
  const raw = path.join(temporary, prefix + '.raw.zip');
  const safe = path.join(temporary, prefix + '.trace.zip');
  let outcome = 'trace-unusable';
  try {
    if (context) {
      await context.tracing.stop({ path: raw });
      const projection = spawnSync('python3', [
        path.join(__dirname, 'browser_evidence_archive.py'), raw, safe,
      ], { encoding: 'utf8', timeout: 15000, maxBuffer: 1024 });
      if (projection.status === 0) {
        const answer = projection.stdout.trim();
        if (answer === 'ok' || MARKERS.has(answer)) outcome = answer;
      }
    }
  } catch {
    // A missing trace must never replace the original test failure.
  }
  const evidence = path.join(output, 'evidence');
  await fs.mkdir(evidence, { recursive: true });
  if (outcome === 'ok') {
    await fs.copyFile(safe, path.join(evidence, prefix + '.trace.zip'));
  } else {
    await fs.writeFile(path.join(evidence, prefix + '.trace-status'), outcome + '\n');
  }
}

async function withBrowserEvidence(chromium, { base, output, label, launchOptions }, exercise) {
  validateFixture(base);
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'metis-playwright-'));
  let browser;
  const traced = [];
  let failed = false;
  try {
    browser = await chromium.launch({ ...launchOptions, tracesDir: temporary });
    const newContext = async (options = {}, trace = false) => {
      validateContextOptions(options);
      const context = await browser.newContext({ ...options, serviceWorkers: 'block' });
      await context.route('**/*', route => (
        LOOPBACK.has(new URL(route.request().url()).hostname) ? route.continue() : route.abort()
      ));
      if (trace) {
        try {
          await context.tracing.start({ screenshots: false, snapshots: false, sources: false });
          traced.push(context);
        } catch {
          traced.push(null);
          console.error('browser-evidence-start-failed');
        }
      }
      return context;
    };
    return await exercise({ newContext });
  } catch (error) {
    failed = true;
    for (const [index, context] of traced.entries()) {
      try {
        await exportFailure(context, temporary, output, label + '-' + (index + 1));
      } catch {
        console.error('browser-evidence-export-failed');
      }
    }
    throw error;
  } finally {
    try {
      try {
        await browser?.close();
      } finally {
        await fs.rm(temporary, { recursive: true, force: true });
      }
    } catch (cleanupError) {
      if (!failed) throw cleanupError;
      console.error('browser-evidence-cleanup-failed');
    }
  }
}

module.exports = { withBrowserEvidence };
