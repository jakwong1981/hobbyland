// backend/tests/import.service.test.ts
import { describe, expect, it } from 'vitest';
import { createInMemoryDatabase, migrate } from '../src/db/client.js';
import { ProductRepository } from '../src/repositories/product.repository.js';
import { buildFreshness, importProducts, parseProductCsv } from '../src/services/import.service.js';
import type { ShopCode } from '../src/types/index.js';

const HEADER = 'title,price,url,regular_price,sku,stock,sell_type';

describe('parseProductCsv', () => {
  it('parses rows with a BOM header and empty stock', () => {
    const csv = `﻿${HEADER}\nKit A,140.00,https://a.example/p1,178.00,4573102663849,,現貨\n`;

    const { records, skipped } = parseProductCsv(csv);

    expect(skipped).toBe(0);
    expect(records).toHaveLength(1);
    expect(records[0]).toMatchObject({
      title: 'Kit A',
      price: 140,
      sku: '4573102663849',
      regularPrice: 178,
      stock: null,
      sellType: '現貨',
    });
  });

  it('skips rows missing title, sku, or a numeric price', () => {
    const csv = `${HEADER}\n,10,https://x,10,111,,\nKit,,https://x,10,111,,\nKit,abc,https://x,10,111,,\n`;

    const { records, skipped } = parseProductCsv(csv);

    expect(records).toHaveLength(0);
    expect(skipped).toBe(3);
  });
});

describe('importProducts', () => {
  it('inserts new products and records a batch', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const { records } = parseProductCsv(`${HEADER}\nKit A,100,https://x,120,111,5,現貨\n`);

    const result = importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', records, 0);

    expect(result.rowCount).toBe(1);
    const products = repo.findProducts({ shop: 'hobbyland' });
    expect(products).toHaveLength(1);
    expect(products[0]).toMatchObject({ sku: '111', price: 100, stock: '5' });
    expect(repo.listBatches(10)[0]).toMatchObject({ sourceFile: 'hobbyland_hg.csv', rowCount: 1 });
  });

  it('updates price on re-import of the same sku', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const first = parseProductCsv(`${HEADER}\nKit A,100,https://x,120,111,5,現貨\n`).records;
    const second = parseProductCsv(`${HEADER}\nKit A,88,https://x,120,111,3,現貨\n`).records;

    importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', first, 0);
    importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', second, 0);

    const products = repo.findProducts({ shop: 'hobbyland' });
    expect(products).toHaveLength(1);
    expect(products[0]!.price).toBe(88);
    expect(products[0]!.stock).toBe('3');
    expect(repo.listBatches(10)).toHaveLength(2);
  });

  it('keeps the same sku from both shops as separate rows', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const { records } = parseProductCsv(`${HEADER}\nKit A,100,https://x,120,111,5,現貨\n`);

    importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', records, 0);
    importProducts(repo, 'animes-pro', 'hg', 'animes-pro_hg.csv', records, 0);

    expect(repo.findProducts({})).toHaveLength(2);
  });

  it('maps the image_url column through to the stored product', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const csv = `${HEADER},image_url\nKit A,100,https://x,120,111,5,現貨,https://static.example/pic1.jpeg\n`;

    const { records } = parseProductCsv(csv);
    expect(records[0]!.imageUrl).toBe('https://static.example/pic1.jpeg');

    importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', records, 0);

    expect(repo.findProducts({ shop: 'hobbyland' })[0]!.imageUrl).toBe('https://static.example/pic1.jpeg');
  });

  it('stores null imageUrl when the CSV has no image_url column', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const { records } = parseProductCsv(`${HEADER}\nKit A,100,https://x,120,111,5,現貨\n`);

    expect(records[0]!.imageUrl).toBeNull();

    importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', records, 0);

    expect(repo.findProducts({ shop: 'hobbyland' })[0]!.imageUrl).toBeNull();
  });

  it('keeps the stored image when a stale re-import has no image_url column', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const withImage = parseProductCsv(
      `${HEADER},image_url\nKit A,100,https://x,120,111,5,現貨,https://static.example/pic1.jpeg\n`,
    ).records;
    const stale = parseProductCsv(`${HEADER}\nKit A,88,https://x,120,111,3,現貨\n`).records;

    importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', withImage, 0);
    importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', stale, 0);

    const product = repo.findProducts({ shop: 'hobbyland' })[0]!;
    expect(product.imageUrl).toBe('https://static.example/pic1.jpeg');
    expect(product.price).toBe(88);
    expect(product.stock).toBe('3');
  });

  it('maps the series column through to the stored product', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const { records } = parseProductCsv(
      `${HEADER},series\nKit A,100,https://x,120,111,5,現貨,zeta\n`,
    );

    expect(records[0]!.series).toBe('zeta');

    importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', records, 0);

    expect(repo.findProducts({ shop: 'hobbyland' })[0]!.series).toBe('zeta');
  });

  it('stores null series when the CSV has no series column and keeps it on stale re-import', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const withSeries = parseProductCsv(
      `${HEADER},series\nKit A,100,https://x,120,111,5,現貨,seed\n`,
    ).records;
    const stale = parseProductCsv(`${HEADER}\nKit A,88,https://x,120,111,3,現貨\n`).records;

    importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', withSeries, 0);
    importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', stale, 0);

    const product = repo.findProducts({ shop: 'hobbyland' })[0]!;
    expect(product.series).toBe('seed');
    expect(product.price).toBe(88);
  });

  it('filters products by series', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const { records } = parseProductCsv(
      `${HEADER},series\nKit A,100,https://x,120,111,5,現貨,zeta\nKit B,90,https://y,90,222,1,現貨,seed\n`,
    );

    importProducts(repo, 'hobbyland', 'hg', 'hobbyland_hg.csv', records, 0);

    const filtered = repo.findProducts({ series: 'zeta' });
    expect(filtered).toHaveLength(1);
    expect(filtered[0]!.sku).toBe('111');
  });
});

describe('buildFreshness', () => {
  it('reports each shop separately and takes the latest as overall', () => {
    const freshness = buildFreshness(
      [
        { shopCode: 'hobbyland', importedAt: '2026-10-11T09:00:00.000Z' },
        { shopCode: 'animes-pro', importedAt: '2026-10-11T11:00:00.000Z' },
      ],
      'hg',
    );

    expect(freshness).toEqual({
      grade: 'hg',
      overall: '2026-10-11T11:00:00.000Z',
      byShop: {
        hobbyland: '2026-10-11T09:00:00.000Z',
        'animes-pro': '2026-10-11T11:00:00.000Z',
        hobbydigi: null,
        fookle: null,
        twinnermodel: null,
      },
    });
  });

  it('picks the earlier shop as overall when it was imported last', () => {
    const freshness = buildFreshness(
      [
        { shopCode: 'hobbyland', importedAt: '2026-10-11T17:00:00.000Z' },
        { shopCode: 'animes-pro', importedAt: '2026-10-11T09:00:00.000Z' },
      ],
      'rg',
    );

    expect(freshness.overall).toBe('2026-10-11T17:00:00.000Z');
  });

  it('leaves a shop with no rows as null', () => {
    const freshness = buildFreshness(
      [{ shopCode: 'hobbyland', importedAt: '2026-10-11T09:00:00.000Z' }],
      null,
    );

    expect(freshness.grade).toBeNull();
    expect(freshness.byShop['animes-pro']).toBeNull();
    expect(freshness.overall).toBe('2026-10-11T09:00:00.000Z');
  });

  it('reports a null overall when nothing has been imported', () => {
    const freshness = buildFreshness([], 'mg');

    expect(freshness.overall).toBeNull();
    expect(freshness.byShop).toEqual({ hobbyland: null, 'animes-pro': null, hobbydigi: null, fookle: null, twinnermodel: null });
  });

  it('counts a shop the union does not know about towards overall', () => {
    // mapProductRow casts the database's shop_code without checking it, so a
    // shop present in the `shops` table but not yet in SHOP_CODES reaches here
    // at runtime. Deriving `overall` from the populated map keeps the readout
    // honest; iterating a hardcoded shop list reported a stale time instead.
    const unknownShop = 'hobbydigi' as ShopCode;
    const freshness = buildFreshness(
      [
        { shopCode: 'hobbyland', importedAt: '2026-10-01T09:00:00.000Z' },
        { shopCode: unknownShop, importedAt: '2026-10-09T09:00:00.000Z' },
      ],
      'hg',
    );

    expect(freshness.overall).toBe('2026-10-09T09:00:00.000Z');
  });

  it('replaces a provisional HD: row by URL once the kit gets a real JAN', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const url = 'https://www.hobbydigi.com/p/gaplant';
    const provisional = parseProductCsv(`${HEADER}\nKit,100,${url},,HD:gaplant,,\n`).records;
    importProducts(repo, 'hobbydigi', 'hg', 'hobbydigi_hg.csv', provisional, 0);

    const linked = parseProductCsv(`${HEADER}\nKit,100,${url},,4573102663849,,\n`).records;
    importProducts(repo, 'hobbydigi', 'hg', 'hobbydigi_hg.csv', linked, 0);

    const skus = repo.findProducts({ shop: 'hobbydigi' }).map((product) => product.sku);
    expect(skus).toEqual(['4573102663849']);
  });

  it('replaces a provisional FM: row by URL once the kit gets a real JAN', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const url = 'https://fooklemodel.com/product/astaroth';
    const provisional = parseProductCsv(`${HEADER}\nKit,100,${url},,FM:astaroth,,\n`).records;
    importProducts(repo, 'fookle', 'hg', 'fookle_hg.csv', provisional, 0);

    const linked = parseProductCsv(`${HEADER}\nKit,100,${url},,4573102663849,,\n`).records;
    importProducts(repo, 'fookle', 'hg', 'fookle_hg.csv', linked, 0);

    const skus = repo.findProducts({ shop: 'fookle' }).map((product) => product.sku);
    expect(skus).toEqual(['4573102663849']);
  });

  it('replaces a provisional TM: row by URL once the kit gets a real JAN', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const url = 'https://twinnermodel.com/products/some-slug';
    const provisional = parseProductCsv(`${HEADER}\nKit,100,${url},,TM:some-slug,,\n`).records;
    importProducts(repo, 'twinnermodel', 'hg', 'twinnermodel_hg.csv', provisional, 0);

    const linked = parseProductCsv(`${HEADER}\nKit,100,${url},,4573102663849,,\n`).records;
    importProducts(repo, 'twinnermodel', 'hg', 'twinnermodel_hg.csv', linked, 0);

    const skus = repo.findProducts({ shop: 'twinnermodel' }).map((product) => product.sku);
    expect(skus).toEqual(['4573102663849']);
  });

  it('keeps a provisional HD: row when re-imported unchanged', () => {
    const repo = new ProductRepository(createInMemoryDatabase());
    const records = parseProductCsv(`${HEADER}\nKit,100,https://x/p,,HD:p,,\n`).records;

    importProducts(repo, 'hobbydigi', 'hg', 'a.csv', records, 0);
    importProducts(repo, 'hobbydigi', 'hg', 'a.csv', records, 0);

    expect(repo.findProducts({ shop: 'hobbydigi' })).toHaveLength(1);
  });

  it('migrates a legacy products table that predates image_url and series before indexing', () => {
    const db = createInMemoryDatabase();
    db.exec('DROP INDEX IF EXISTS idx_products_series');
    db.exec('DROP TABLE products');
    db.exec(`
      CREATE TABLE products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id INTEGER NOT NULL REFERENCES shops(id),
        sku TEXT NOT NULL,
        grade TEXT NOT NULL,
        title TEXT NOT NULL,
        price REAL NOT NULL,
        regular_price REAL,
        url TEXT NOT NULL,
        stock TEXT,
        sell_type TEXT,
        batch_id INTEGER REFERENCES import_batches(id),
        imported_at TEXT NOT NULL,
        UNIQUE (shop_id, sku, grade)
      )
    `);

    migrate(db);

    const columns = db.prepare("SELECT name FROM pragma_table_info('products')").all() as { name: string }[];
    expect(columns.map((c) => c.name)).toEqual(expect.arrayContaining(['image_url', 'series']));
    const indexes = db.prepare("SELECT name FROM pragma_index_list('products')").all() as { name: string }[];
    expect(indexes.map((i) => i.name)).toContain('idx_products_series');
  });
});
