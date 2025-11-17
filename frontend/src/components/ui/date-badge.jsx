import React from 'react';
import { cn } from '@/lib/utils';
import { formatDateTime } from '@/lib/formatDateTime';

const DateBadge = ({ value, fallback = 'Not available', className, ...props }) => {
  const formatted = formatDateTime(value);
  const displayText = formatted ?? fallback;
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border border-border/80 bg-muted/70 px-2 py-0.5 text-[11px] font-semibold tracking-tight text-muted-foreground',
        className
      )}
      title={displayText}
      {...props}
    >
      {displayText}
    </span>
  );
};

export default DateBadge;
