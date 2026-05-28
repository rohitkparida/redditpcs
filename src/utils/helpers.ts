// Shared utility functions for RedditPCs

/**
 * Generates a URL-friendly slug from a string (e.g., product or category name)
 */
export const slugify = (name: string): string => {
  if (!name) return '';
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
};

/**
 * Returns the appropriate Tailwind/CSS color class based on the recommendation rate
 */
export const getSentimentColor = (score: number): string => {
  if (score >= 0.9) return 'text-emerald-600 dark:text-emerald-450';
  if (score >= 0.8) return 'text-emerald-500 dark:text-emerald-500';
  if (score >= 0.7) return 'text-yellow-500 dark:text-yellow-450';
  return 'text-orange-500 dark:text-orange-450';
};

/**
 * Formats an ISO date string into a clean, human-readable date
 */
export const formatDate = (iso: string): string => {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
};
