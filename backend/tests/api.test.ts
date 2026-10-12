// backend/tests/api.test.ts
import { beforeEach, describe, expect, it } from 'vitest';
import request from 'supertest';
import type { Express } from 'express';
import { createApp } from '../src/app.js';
import { createInMemoryDatabase } from '../src/db/client.js';
import { ProductRepository } from '../src/repositories/product.repository.js';
import { importProducts, parseProductCsv } from '../src/services/import.service.js';

const HEADER = 'title,price,url,regular_price,sku,stock,sell_type';

let app: Express;
let repo: ProductRepository;

beforeEach(() => {
  const db = createInMemoryDatabase();
  repo = new ProductRepository(db);
  app = createApp(db);
  const hobbylandCsv = `${HEADER}\nKit A,140,https://h.example/a,178,111,5,現貨\nKit B,300,https://h.example/b,300,222,2,現貨\n`;
  const animesCsv = `${HEADER}\nKit A,118,https://a.example/a,178,111,,現貨\n`;
  const h = parseProductCsv(hobbylandCsv);
  const a = parseProductCsv(animesCsv);
  importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', h.records, 0);
  importProducts(repo, 'animes-pro', 'hg', 'animes-pro_hg.csv', a.records, 0);
});

describe('GET /api/comparisons', () => {
  it('groups by sku and flags the cheaper shop', async () => {
    const res = await request(app).get('/api/comparisons?grade=hg');

    expect(res.status).toBe(200);
    expect(res.body.code).toBe(0);
    const rows = res.body.data as Array<{
      sku: string;
      cheapestShop: string;
      saving: number | null;
      exclusiveShop: string | null;
      offers: unknown[];
    }>;
    const kitA = rows.find((r) => r.sku === '111')!;
    expect(kitA.cheapestShop).toBe('animes-pro');
    expect(kitA.saving).toBe(22);
    expect(kitA.exclusiveShop).toBeNull();
    expect(kitA.offers).toHaveLength(2);
    const kitB = rows.find((r) => r.sku === '222')!;
    expect(kitB.cheapestShop).toBe('hobbyland');
    expect(kitB.saving).toBeNull();
    expect(kitB.exclusiveShop).toBe('hobbyland');
  });

  it('filters by cheaper shop', async () => {
    const res = await request(app).get('/api/comparisons?cheaper=animes-pro');

    expect(res.body.data).toHaveLength(1);
  });

  it('rejects an invalid grade', async () => {
    const res = await request(app).get('/api/comparisons?grade=pg');

    expect(res.status).toBe(400);
    expect(res.body.traceId).toBeDefined();
  });
});

describe('POST /api/import', () => {
  it('imports an uploaded csv', async () => {
    const csv = `${HEADER}\nKit C,50,https://h.example/c,60,333,1,預訂\n`;
    const res = await request(app)
      .post('/api/import')
      .field('shop', 'hobbyland')
      .field('grade', 'mg')
      .attach('file', Buffer.from(csv), 'hobbyland_mg.csv');

    expect(res.status).toBe(201);
    expect(res.body.data.rowCount).toBe(1);
    expect(repo.findProducts({ grade: 'mg' })).toHaveLength(1);
  });

  it('rejects a request without a file', async () => {
    const res = await request(app).post('/api/import').field('shop', 'hobbyland').field('grade', 'mg');

    expect(res.status).toBe(400);
  });

  it('rejects a csv with no valid rows', async () => {
    const res = await request(app)
      .post('/api/import')
      .field('shop', 'hobbyland')
      .field('grade', 'mg')
      .attach('file', Buffer.from(`${HEADER}\n,,,,,,\n`), 'bad.csv');

    expect(res.status).toBe(422);
  });
});

describe('GET /api/imports', () => {
  it('lists recent batches', async () => {
    const res = await request(app).get('/api/imports');

    expect(res.status).toBe(200);
    expect(res.body.data).toHaveLength(2);
  });
});

describe('GET /api/imports/freshness', () => {
  it('reports the latest import per shop for a grade', async () => {
    const res = await request(app).get('/api/imports/freshness?grade=hg');

    expect(res.status).toBe(200);
    expect(res.body.code).toBe(0);
    const data = res.body.data as {
      grade: string;
      overall: string | null;
      byShop: Record<string, string | null>;
    };
    expect(data.grade).toBe('hg');
    expect(data.byShop.hobbyland).not.toBeNull();
    expect(data.byShop['animes-pro']).not.toBeNull();
    expect(data.overall).toBe(
      [data.byShop.hobbyland, data.byShop['animes-pro']].sort().at(-1),
    );
  });

  it('reports nulls for a grade that has never been imported', async () => {
    const res = await request(app).get('/api/imports/freshness?grade=mg');

    expect(res.status).toBe(200);
    expect(res.body.data).toEqual({
      grade: 'mg',
      overall: null,
      byShop: { hobbyland: null, 'animes-pro': null, hobbydigi: null },
    });
  });

  it('omits the grade scope when no grade is given', async () => {
    const res = await request(app).get('/api/imports/freshness');

    expect(res.status).toBe(200);
    expect(res.body.data.grade).toBeNull();
    expect(res.body.data.overall).not.toBeNull();
  });

  it('rejects an invalid grade', async () => {
    const res = await request(app).get('/api/imports/freshness?grade=pg');

    expect(res.status).toBe(400);
    expect(res.body.traceId).toBeDefined();
  });
});
