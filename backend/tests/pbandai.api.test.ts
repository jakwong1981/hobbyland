// backend/tests/pbandai.api.test.ts
import { beforeEach, describe, expect, it } from 'vitest';
import request from 'supertest';
import type { Express } from 'express';
import { createApp } from '../src/app.js';
import { createInMemoryDatabase } from '../src/db/client.js';
import { PbandaiRepository } from '../src/repositories/pbandai.repository.js';
import { importPbandaiItems, parsePbandaiCsv } from '../src/services/pbandai.service.js';

const HEADER = 'name,tc_name,price,status,url,image';

let app: Express;
let repo: PbandaiRepository;

beforeEach(() => {
  const db = createInMemoryDatabase();
  repo = new PbandaiRepository(db);
  app = createApp(db);
  const csv = `${HEADER}
HG 1/144 Kit A,HG 1/144 甲,HK$450.00,PRE-ORDER,https://p-bandai.com/hk/item/A1,https://p-bandai.com/img/a.jpg
MG 1/100 Kit B,MG 1/100 乙,HK$1200.00,,https://p-bandai.com/hk/item/B2,
`;
  importPbandaiItems(repo, parsePbandaiCsv(csv).records);
});

describe('GET /api/pbandai', () => {
  it('returns the snapshot in import order with the shared envelope', async () => {
    const res = await request(app).get('/api/pbandai');

    expect(res.status).toBe(200);
    expect(res.body.code).toBe(0);
    const items = res.body.data as Array<Record<string, unknown>>;
    expect(items.map((i) => i.name)).toEqual(['HG 1/144 Kit A', 'MG 1/100 Kit B']);
    expect(items[0]).toMatchObject({
      tcName: 'HG 1/144 甲',
      price: 450,
      status: 'PRE-ORDER',
      url: 'https://p-bandai.com/hk/item/A1',
      imageUrl: 'https://p-bandai.com/img/a.jpg',
    });
    expect(items[1]!.imageUrl).toBeNull();
  });

  it('returns an empty list before any import', async () => {
    const emptyApp = createApp(createInMemoryDatabase());

    const res = await request(emptyApp).get('/api/pbandai');

    expect(res.status).toBe(200);
    expect(res.body.data).toEqual([]);
  });

  it('filters by the q parameter', async () => {
    const res = await request(app).get('/api/pbandai?q=%E4%B9%99');

    expect(res.status).toBe(200);
    const items = res.body.data as Array<{ name: string }>;
    expect(items).toHaveLength(1);
    expect(items[0]!.name).toBe('MG 1/100 Kit B');
  });
});
