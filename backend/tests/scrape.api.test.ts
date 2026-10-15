// backend/tests/scrape.api.test.ts
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import request from 'supertest';
import { createApp } from '../src/app.js';
import { createInMemoryDatabase } from '../src/db/client.js';
import { ScrapeService } from '../src/services/scrape.service.js';

function writeScript(body: string): { scriptPath: string; cwd: string } {
  const cwd = mkdtempSync(join(tmpdir(), 'scrape-test-'));
  const scriptPath = join(cwd, 'scrape.sh');
  writeFileSync(scriptPath, body, { mode: 0o755 });
  return { scriptPath, cwd };
}

async function waitForState(
  app: ReturnType<typeof createApp>,
  states: string[],
): Promise<Record<string, unknown>> {
  for (let i = 0; i < 100; i += 1) {
    const res = await request(app).get('/api/scrape/status');
    if (states.includes(res.body.data.state as string)) {
      return res.body.data as Record<string, unknown>;
    }
    await new Promise((r) => setTimeout(r, 50));
  }
  throw new Error(`scrape job never reached state ${states.join('|')}`);
}

describe('scrape API', () => {
  it('starts with an idle status', async () => {
    const app = createApp(createInMemoryDatabase());
    const res = await request(app).get('/api/scrape/status');

    expect(res.status).toBe(200);
    expect(res.body.data.state).toBe('idle');
  });

  it('runs the script, rejects a concurrent run, and reports completion', async () => {
    const { scriptPath, cwd } = writeScript('#!/usr/bin/env bash\nsleep 0.3\necho done\n');
    const app = createApp(createInMemoryDatabase(), new ScrapeService(scriptPath, cwd));

    const start = await request(app).post('/api/scrape');
    expect(start.status).toBe(202);
    expect(start.body.data.state).toBe('running');

    const conflict = await request(app).post('/api/scrape');
    expect(conflict.status).toBe(409);

    const done = await waitForState(app, ['completed', 'failed']);
    expect(done.state).toBe('completed');
    expect(done.exitCode).toBe(0);
    expect(done.finishedAt).not.toBeNull();
  });

  it('reports failure when the script exits non-zero', async () => {
    const { scriptPath, cwd } = writeScript('#!/usr/bin/env bash\nexit 3\n');
    const app = createApp(createInMemoryDatabase(), new ScrapeService(scriptPath, cwd));

    await request(app).post('/api/scrape');
    const done = await waitForState(app, ['completed', 'failed']);

    expect(done.state).toBe('failed');
    expect(done.exitCode).toBe(3);
  });

  it('returns 500 when the script does not exist', async () => {
    const app = createApp(
      createInMemoryDatabase(),
      new ScrapeService('/nonexistent/scrape-and-import.sh'),
    );

    const res = await request(app).post('/api/scrape');
    expect(res.status).toBe(500);
    expect(res.body.message).toContain('Scrape script not found');
  });
});
