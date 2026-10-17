// backend/tests/pbandai.service.test.ts
import { describe, expect, it } from 'vitest';
import { createInMemoryDatabase } from '../src/db/client.js';
import { PbandaiRepository } from '../src/repositories/pbandai.repository.js';
import { importPbandaiItems, parsePbandaiCsv } from '../src/services/pbandai.service.js';

const HEADER = 'name,tc_name,price,status,url,image';
const ROW_A = 'HG 1/144 Kit A,HG 1/144 甲,HK$450.00,PRE-ORDER,https://p-bandai.com/hk/item/A1,https://p-bandai.com/img/a.jpg';
const ROW_B = 'MG 1/100 Kit B,MG 1/100 乙,HK$1200.00,,https://p-bandai.com/hk/item/B2,https://p-bandai.com/img/b.jpg';

describe('parsePbandaiCsv', () => {
  it('parses rows with a BOM header and keeps the image column', () => {
    const csv = `﻿${HEADER}\n${ROW_A}\n`;

    const { records, skipped } = parsePbandaiCsv(csv);

    expect(skipped).toBe(0);
    expect(records).toHaveLength(1);
    expect(records[0]).toEqual({
      name: 'HG 1/144 Kit A',
      tcName: 'HG 1/144 甲',
      price: 450,
      status: 'PRE-ORDER',
      url: 'https://p-bandai.com/hk/item/A1',
      imageUrl: 'https://p-bandai.com/img/a.jpg',
    });
  });

  it('parses the numeric part of the raw price text and nulls N/A', () => {
    const csv = `${HEADER}\nKit A,,"HK$1,280.50",,https://x/a,\nKit B,,N/A,,https://x/b,\n`;

    const { records } = parsePbandaiCsv(csv);

    expect(records[0]!.price).toBe(1280.5);
    expect(records[1]!.price).toBeNull();
  });

  it('skips rows missing a name or a url', () => {
    const csv = `${HEADER}\n,tc,100,,https://x/a,\nKit B,,100,,,\n`;

    const { records, skipped } = parsePbandaiCsv(csv);

    expect(records).toHaveLength(0);
    expect(skipped).toBe(2);
  });

  it('tolerates a CSV exported before the image column existed', () => {
    const csv = 'name,tc_name,price,status,url\nKit A,甲,HK$100,PRE-ORDER,https://x/a\n';

    const { records, skipped } = parsePbandaiCsv(csv);

    expect(skipped).toBe(0);
    expect(records[0]!.imageUrl).toBeNull();
  });
});

describe('PbandaiRepository', () => {
  it('imports rows and reads them back in insert order', () => {
    const repo = new PbandaiRepository(createInMemoryDatabase());
    const { records } = parsePbandaiCsv(`${HEADER}\n${ROW_A}\n${ROW_B}\n`);

    const result = importPbandaiItems(repo, records);

    expect(result.rowCount).toBe(2);
    const items = repo.findAll();
    expect(items.map((i) => i.name)).toEqual(['HG 1/144 Kit A', 'MG 1/100 Kit B']);
    expect(items[0]!.tcName).toBe('HG 1/144 甲');
    expect(items[0]!.imageUrl).toBe('https://p-bandai.com/img/a.jpg');
    expect(items[0]!.importedAt).not.toBe('');
  });

  it('replaceAll swaps the snapshot so closed pre-orders vanish', () => {
    const repo = new PbandaiRepository(createInMemoryDatabase());
    importPbandaiItems(repo, parsePbandaiCsv(`${HEADER}\n${ROW_A}\n${ROW_B}\n`).records);

    importPbandaiItems(repo, parsePbandaiCsv(`${HEADER}\n${ROW_B}\n`).records);

    const items = repo.findAll();
    expect(items).toHaveLength(1);
    expect(items[0]!.name).toBe('MG 1/100 Kit B');
  });

  it('filters by name or translated name', () => {
    const repo = new PbandaiRepository(createInMemoryDatabase());
    importPbandaiItems(repo, parsePbandaiCsv(`${HEADER}\n${ROW_A}\n${ROW_B}\n`).records);

    expect(repo.findAll('kit a').map((i) => i.name)).toEqual(['HG 1/144 Kit A']);
    expect(repo.findAll('乙').map((i) => i.name)).toEqual(['MG 1/100 Kit B']);
  });
});
