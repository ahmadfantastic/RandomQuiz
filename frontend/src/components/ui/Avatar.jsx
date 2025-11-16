import React from 'react';

import { cn } from '@/lib/utils';

const Avatar = ({ src, name, size = 40, className, ...props }) => {
  const initials = (name || '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((segment) => segment[0].toUpperCase())
    .join('');

  if (src) {
    return (
      <img
        src={src}
        alt={name || 'Profile picture'}
        className={cn('rounded-full object-cover', className)}
        style={{ width: size, height: size }}
        {...props}
      />
    );
  }

  return (
    <span
      className={cn(
        'inline-flex items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/70 text-white font-semibold',
        className
      )}
      style={{ width: size, height: size }}
      aria-hidden="true"
      {...props}
    >
      {initials || 'RQ'}
    </span>
  );
};

export default Avatar;
