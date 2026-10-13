// frontend/src/utils/skuLabel.ts
const PROVISIONAL_SKU_PREFIX = 'HD:';

export function skuLabel(sku: string): string {
  return sku.startsWith(PROVISIONAL_SKU_PREFIX) ? '無 JAN' : sku;
}
