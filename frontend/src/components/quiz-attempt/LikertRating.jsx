import React from 'react';
import { cn } from '@/lib/utils';

const LikertRating = ({
  criteria,
  scale,
  selectedRatings,
  onRatingSelect,
  slotId,
}) => {
  return (
    <div className="mt-5">
      {/* Scale Legend at Top - Only on Mobile */}
      <div className="mb-6 flex flex-wrap gap-3 sm:hidden">
        {scale.map((option) => (
          <div key={`legend-${option.value}`} className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-muted-foreground/30 text-xs font-semibold text-muted-foreground">
              {option.value}
            </div>
            <span className="text-xs text-muted-foreground">{option.label}</span>
          </div>
        ))}
      </div>

      {/* Criteria Grid */}
      <div className="space-y-6">
        {criteria.map((criterion) => {
          const currentValue = selectedRatings?.[criterion.id];

          return (
            <div key={criterion.id} className="rounded-2xl border bg-card/70 p-4 shadow-sm">
              {/* Criterion Description */}
              <div className="mb-4">
                <p className="text-sm font-semibold text-foreground">{criterion.name}</p>
                <p className="text-xs text-muted-foreground">{criterion.description}</p>
              </div>

              {/* Rating Options - Vertical Grid */}
              <div className="grid grid-cols-5 gap-2 sm:gap-3">
                {scale.map((option) => {
                  const optionKey = `${option.value}`;
                  const isSelected = `${currentValue}` === optionKey;

                  return (
                    <label
                      key={`${criterion.id}-${optionKey}`}
                      className={cn(
                        'flex flex-col items-center gap-2 cursor-pointer rounded-lg p-2 transition-colors sm:p-3',
                        isSelected ? 'bg-primary/10' : 'hover:bg-muted/50'
                      )}
                    >
                      <input
                        type="radio"
                        name={`${slotId}-${criterion.id}`}
                        value={option.value}
                        className="sr-only"
                        checked={isSelected}
                        onChange={() => onRatingSelect(criterion.id, option.value)}
                      />
                      <div className={cn(
                        'flex h-8 w-8 items-center justify-center rounded-full border-2 text-sm font-semibold transition-colors sm:h-10 sm:w-10 sm:text-base',
                        isSelected
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-muted-foreground/30 text-muted-foreground hover:border-primary/50'
                      )}>
                        {option.value}
                      </div>
                      <span className="hidden text-center text-xs text-muted-foreground sm:block">{option.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Instructions */}
      <p className="mt-4 text-xs text-muted-foreground">
        Select one rating for each criterion. Use the legend above as a reference.
      </p>
    </div>
  );
};

export default LikertRating;
