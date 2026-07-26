export const MIN_VERIFIED_COMMENTS = 30;
export const MIN_CONTRIBUTING_THREADS = 3;

type ProductEvidence = {
  mentions?: number | null;
  contributingThreads?: number | null;
};

export function hasPublishableEvidence(product: ProductEvidence): boolean {
  return (
    Number(product.mentions ?? 0) >= MIN_VERIFIED_COMMENTS &&
    Number(product.contributingThreads ?? 0) >= MIN_CONTRIBUTING_THREADS
  );
}

export function hasLimitedEvidence(product: ProductEvidence): boolean {
  return !hasPublishableEvidence(product);
}
