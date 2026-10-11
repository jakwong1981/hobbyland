// backend/src/middleware/error.middleware.ts
import type { NextFunction, Request, Response } from 'express';
import { randomUUID } from 'node:crypto';
import { ZodError } from 'zod';
import type { ApiErrorResponse } from '../types/index.js';
import { AppError } from '../utils/app-error.js';
import { logger } from '../utils/logger.js';

export function traceIdMiddleware(req: Request, res: Response, next: NextFunction): void {
  res.locals['traceId'] = (req.headers['x-trace-id'] as string | undefined) ?? randomUUID();
  res.setHeader('x-trace-id', res.locals['traceId']);
  next();
}

function traceIdOf(res: Response): string {
  return (res.locals['traceId'] as string | undefined) ?? 'unknown';
}

export function notFoundMiddleware(_req: Request, res: Response): void {
  const body: ApiErrorResponse = {
    code: 404,
    message: 'Resource not found',
    data: null,
    timestamp: new Date().toISOString(),
    traceId: traceIdOf(res),
  };
  res.status(404).json(body);
}

export function errorMiddleware(err: unknown, _req: Request, res: Response, _next: NextFunction): void {
  let status = 500;
  let message = 'Internal server error';
  if (err instanceof AppError) {
    status = err.statusCode;
    message = err.message;
  } else if (err instanceof ZodError) {
    status = 400;
    message = err.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join('; ');
  }
  if (status >= 500) {
    logger.error({ err, traceId: traceIdOf(res) }, 'unhandled error');
  }
  const body: ApiErrorResponse = {
    code: status,
    message,
    data: null,
    timestamp: new Date().toISOString(),
    traceId: traceIdOf(res),
  };
  res.status(status).json(body);
}
