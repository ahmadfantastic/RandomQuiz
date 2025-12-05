import React from 'react';
import { cn } from '@/lib/utils';

const Checkbox = React.forwardRef(({ className, checked, onCheckedChange, ...props }, ref) => {
    return (
        <input
            type="checkbox"
            className={cn(
                "h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary accent-primary cursor-pointer",
                className
            )}
            checked={checked}
            onChange={(e) => onCheckedChange?.(e.target.checked)}
            ref={ref}
            {...props}
        />
    );
});

Checkbox.displayName = 'Checkbox';

export { Checkbox };
