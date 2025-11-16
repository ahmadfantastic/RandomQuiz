import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs) {
  // This is the crucial change: twMerge intelligently resolves conflicts
  return twMerge(clsx(inputs));
}