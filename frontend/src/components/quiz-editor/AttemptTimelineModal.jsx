import React, { useEffect, useMemo, useState } from 'react';
import { Modal } from '@/components/ui/modal';
import DateBadge from '@/components/ui/date-badge';
import api from '@/lib/api';

const clamp = (value, min, max) => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return min;
  }
  return Math.min(Math.max(value, min), max);
};

const mixChannel = (start, end, ratio) => Math.round(start + (end - start) * ratio);

const toHexChannel = (value) => value.toString(16).padStart(2, '0');

const ratingColorStops = {
  low: [239, 68, 68],
  mid: [249, 115, 22],
  high: [34, 197, 94],
};

const getRatingColor = (value, range) => {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return '#b5c0c4';
  }
  const min = range?.min;
  const max = range?.max;
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return '#38bdf8';
  }
  const normalized = max === min ? 0.5 : clamp((numericValue - min) / (max - min), 0, 1);
  const isLow = normalized <= 0.5;
  const startColor = isLow ? ratingColorStops.low : ratingColorStops.mid;
  const endColor = isLow ? ratingColorStops.mid : ratingColorStops.high;
  const ratio = isLow ? normalized / 0.5 : (normalized - 0.5) / 0.5;
  const [r, g, b] = startColor.map((channel, index) =>
    mixChannel(channel, endColor[index], ratio)
  );
  return `#${toHexChannel(r)}${toHexChannel(g)}${toHexChannel(b)}`;
};

const parseTimestamp = (value, fallback) => {
  const parsed = value ? new Date(value).getTime() : NaN;
  return Number.isFinite(parsed) ? parsed : fallback;
};

const computeTypingDelta = (metadata) => {
  const diff = metadata?.diff;
  if (!diff) return 0;
  const added = typeof diff.added === 'string' ? diff.added.length : 0;
  const removed = typeof diff.removed === 'string' ? diff.removed.length : 0;
  return added - removed;
};

const createTypingTitle = (metadata) => {
  const diff = metadata?.diff;
  if (!diff) {
    return 'Typing interaction';
  }
  const added = typeof diff.added === 'string' ? diff.added.length : 0;
  const removed = typeof diff.removed === 'string' ? diff.removed.length : 0;
  const parts = [];
  if (added) parts.push(`${added} char${added === 1 ? '' : 's'} added`);
  if (removed) parts.push(`${removed} char${removed === 1 ? '' : 's'} removed`);
  if (!parts.length) {
    return 'Typing interaction';
  }
  return `Typing — ${parts.join(', ')}`;
};

const AttemptTimelineModal = ({ open, attempt, quizId, onOpenChange, ratingRange }) => {
  const [timeline, setTimeline] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !attempt) {
      setTimeline(null);
      setError('');
      setLoading(false);
      return undefined;
    }

    let isCancelled = false;
    setLoading(true);
    setError('');
    setTimeline(null);

    api
      .get(`/api/quizzes/${quizId}/attempts/${attempt.id}/interactions/`)
      .then((res) => {
        if (!isCancelled) {
          setTimeline(res.data);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setError(err.response?.data?.detail || 'Unable to load the interaction timeline.');
        }
      })
      .finally(() => {
        if (!isCancelled) {
          setLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [attempt?.id, open, quizId]);

  const startTime = timeline?.started_at || attempt?.started_at;
  const endTime =
    timeline?.completed_at || attempt?.completed_at || startTime || new Date().toISOString();
  const safeStartMs = parseTimestamp(startTime, Date.now());
  const safeEndMs = parseTimestamp(endTime, safeStartMs + 1);
  const durationMs = Math.max(1, safeEndMs - safeStartMs);

  const timelineSlots = useMemo(() => {
    if (!timeline?.slots?.length) {
      return [];
    }
      return timeline.slots.map((slot) => {
        const interactions = (slot.interactions || []).map((event) => {
          const eventTime = event.created_at ? new Date(event.created_at).getTime() : safeStartMs;
          const normalized = clamp(((eventTime - safeStartMs) / durationMs) * 100, 0, 100);
          return {
            ...event,
            position: Number.isNaN(normalized) ? 0 : normalized,
            leftPercent: `${Number.isFinite(normalized) ? normalized : 0}%`,
            delta: event.event_type === 'typing' ? computeTypingDelta(event.metadata) : 0,
          };
        });
      return {
        ...slot,
        interactions,
      };
    });
  }, [durationMs, safeStartMs, timeline]);

  const renderSlotTimeline = (slot) => {
    const hasInteractions = Array.isArray(slot.interactions) && slot.interactions.length > 0;
    return (
      <div key={slot.id} className="space-y-2 rounded-2xl border bg-white/50 p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
              {slot.response_type === 'rating' ? 'Rating slot' : 'Text slot'}
            </p>
            <p className="text-sm font-semibold">{slot.slot_label || 'Slot'}</p>
          </div>
          <span className="text-xs text-muted-foreground">
            {slot.interactions.length} interaction{slot.interactions.length === 1 ? '' : 's'}
          </span>
        </div>
        <div className="relative h-28 overflow-hidden rounded-xl border border-border/70 bg-muted/80">
          <div className="absolute left-0 right-0 top-1/2 h-[1px] bg-border" />
          <div className="pointer-events-none absolute inset-x-4 bottom-0 flex justify-between text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
            <span>Start</span>
            <span>Submit</span>
          </div>
          {!hasInteractions && (
            <p className="absolute inset-0 m-auto w-full text-center text-xs text-muted-foreground">
              No interactions recorded
            </p>
          )}
          {hasInteractions &&
            slot.interactions.map((event, index) => {
              const left = `calc(${event.position}% - 1px)`;
              if (event.event_type === 'typing') {
                const height = clamp(Math.abs(event.delta) * 3 + 10, 6, 60);
                const isPositive = event.delta >= 0;
                const top = isPositive ? `calc(50% - ${height}px)` : '50%';
                const barColor = isPositive ? 'bg-emerald-500' : 'bg-rose-500';
                return (
                  <div
                    key={`${event.created_at}-${index}`}
                    title={createTypingTitle(event.metadata)}
                    className={`absolute w-0.5 ${barColor}`}
                    style={{
                      left,
                      top,
                      height: `${height}px`,
                    }}
                  />
                );
              }
              if (event.event_type === 'rating' || event.event_type === 'rating_selection') {
                const value = event.metadata?.option_value;
                const criterionId = event.metadata?.criterion_id;
                const criterionLabel = criterionId ?? 'Criterion';
                const color = getRatingColor(value, ratingRange);
                const label = typeof value === 'number' ? value : value ?? 'rating';
                const dotLeft = event.leftPercent ? `calc(${event.leftPercent} - 1px)` : left;
                return (
                  <div key={`${event.created_at}-${index}`}>
                    <div
                      title={`Rating ${label} — ${criterionLabel}`}
                      className="absolute flex h-3 w-3 items-center justify-center rounded-full border border-white"
                      style={{
                        left: dotLeft,
                        top: 'calc(50% - 6px)',
                        backgroundColor: color,
                      }}
                    >
                      <span className="sr-only">Rating event</span>
                    </div>
                    <span
                      className="pointer-events-none absolute w-max text-[9px] font-semibold uppercase tracking-[0.2em] text-muted-foreground"
                      style={{
                        left: event.leftPercent || '0%',
                        top: 'calc(50% + 10px)',
                        transform: 'translate(-50%, 0)',
                        maxWidth: '160px',
                        textAlign: 'center',
                      }}
                    >
                      {criterionLabel}
                    </span>
                  </div>
                );
              }
              return null;
            })}
        </div>
      </div>
    );
  };

  return (
    <Modal
      open={open && Boolean(attempt)}
      onOpenChange={onOpenChange}
      title="Attempt timeline"
      description="Inspect how the student interacted with every slot."
      className="max-w-4xl"
    >
      <div className="space-y-4">
        <div className="rounded-xl border border-border/70 bg-muted/50 p-4 text-sm">
          <p className="font-semibold">{attempt?.student_identifier || 'Unknown student'}</p>
          <p className="text-xs text-muted-foreground flex items-center gap-2">
            <span>Started</span>
            <DateBadge value={startTime} fallback="Not available" />
            <span className="text-muted-foreground">·</span>
            <span>Submitted</span>
            <DateBadge value={endTime} fallback="Not available" />
          </p>
        </div>
        {loading && <p className="text-sm text-muted-foreground">Loading timeline…</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && timelineSlots.length > 0 && (
          <div className="space-y-4">
            {timelineSlots.map((slot) => renderSlotTimeline(slot))}
          </div>
        )}
        {!loading && !error && timelineSlots.length === 0 && (
          <p className="text-sm text-muted-foreground">No slot interactions have been recorded yet.</p>
        )}
      </div>
    </Modal>
  );
};

export default AttemptTimelineModal;
