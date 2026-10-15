// backend/src/services/scrape.service.ts
import { spawn, type ChildProcess } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import type { ScrapeJobState, ScrapeJobStatus } from '../types/index.js';
import { AppError } from '../utils/app-error.js';
import { logger } from '../utils/logger.js';

const REPO_ROOT = resolve(import.meta.dirname, '../../..');
const SCRIPT_PATH = resolve(REPO_ROOT, 'scripts/scrape-and-import.sh');

export class ScrapeService {
  private state: ScrapeJobState = 'idle';
  private startedAt: string | null = null;
  private finishedAt: string | null = null;
  private exitCode: number | null = null;
  private child: ChildProcess | null = null;

  constructor(
    private readonly scriptPath: string = SCRIPT_PATH,
    private readonly cwd: string = REPO_ROOT,
  ) {}

  start(): ScrapeJobStatus {
    if (this.state === 'running') {
      throw new AppError(409, 'A scrape job is already running');
    }
    if (!existsSync(this.scriptPath)) {
      throw new AppError(500, `Scrape script not found: ${this.scriptPath}`);
    }
    this.state = 'running';
    this.startedAt = new Date().toISOString();
    this.finishedAt = null;
    this.exitCode = null;

    logger.info({ script: this.scriptPath }, 'scrape job started');
    const child = spawn('bash', [this.scriptPath], { cwd: this.cwd, env: process.env });
    this.child = child;

    child.stdout.on('data', (chunk: Buffer) => {
      logger.info({ out: chunk.toString().trimEnd() }, 'scrape');
    });
    child.stderr.on('data', (chunk: Buffer) => {
      logger.warn({ err: chunk.toString().trimEnd() }, 'scrape');
    });
    child.on('error', (err) => {
      this.finish('failed', null, err.message);
    });
    child.on('close', (code) => {
      this.finish(code === 0 ? 'completed' : 'failed', code);
    });

    return this.getStatus();
  }

  getStatus(): ScrapeJobStatus {
    return {
      state: this.state,
      startedAt: this.startedAt,
      finishedAt: this.finishedAt,
      exitCode: this.exitCode,
    };
  }

  private finish(state: ScrapeJobState, exitCode: number | null, reason?: string): void {
    this.state = state;
    this.exitCode = exitCode;
    this.finishedAt = new Date().toISOString();
    this.child = null;
    logger.info({ state, exitCode, reason }, 'scrape job finished');
  }
}
