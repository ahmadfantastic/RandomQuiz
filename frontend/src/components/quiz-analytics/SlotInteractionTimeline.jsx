import React, { useMemo } from 'react';

const clamp = (value, min, max) => {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return min;
    }
    return Math.min(Math.max(value, min), max);
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

const SlotInteractionTimeline = ({ interactions, selectedStudent }) => {
    if (!interactions || interactions.length === 0) {
        return null;
    }

    // Filter interactions for selected student
    const studentInteractions = useMemo(() => {
        if (!selectedStudent) return [];
        return interactions.filter(i => i.student_id === selectedStudent);
    }, [interactions, selectedStudent]);

    const hasInteractions = studentInteractions.length > 0;

    // Get start and end times from the selected student's interactions
    const timeLabels = useMemo(() => {
        if (!hasInteractions || studentInteractions.length === 0) {
            return { start: 'Start', end: 'Submit' };
        }

        const firstInteraction = studentInteractions[0];
        const startTime = firstInteraction.attempt_started_at
            ? new Date(firstInteraction.attempt_started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : 'Start';
        const endTime = firstInteraction.attempt_completed_at
            ? new Date(firstInteraction.attempt_completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : 'Submit';

        return { start: startTime, end: endTime };
    }, [hasInteractions, studentInteractions]);

    return (
        <div className="">
            <div className="flex items-center justify-between gap-3 mb-2">
                <div>
                    <p className="text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
                        Student Interactions
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                        {studentInteractions.length} interaction{studentInteractions.length === 1 ? '' : 's'}
                    </span>
                </div>
            </div>
            <div className="relative h-28 overflow-hidden rounded-xl border border-border/70 bg-muted/80">
                <div className="absolute left-0 right-0 top-1/2 h-[1px] bg-border" />
                <div className="pointer-events-none absolute inset-x-4 bottom-0 flex justify-between text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
                    <span>{timeLabels.start}</span>
                    <span>{timeLabels.end}</span>
                </div>
                {!hasInteractions && (
                    <p className="absolute inset-0 m-auto w-full text-center text-xs text-muted-foreground">
                        No interactions recorded
                    </p>
                )}
                {hasInteractions &&
                    studentInteractions.map((event, index) => {
                        const left = `calc(${event.position}% - 1px)`;
                        if (event.event_type === 'typing') {
                            const delta = computeTypingDelta(event.metadata);
                            const height = clamp(Math.abs(delta) * 3 + 10, 6, 60);
                            const isPositive = delta >= 0;
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
                            const label = typeof value === 'number' ? value : value ?? 'rating';
                            return (
                                <div key={`${event.created_at}-${index}`}>
                                    <div
                                        title={`Rating ${label} — ${criterionLabel}`}
                                        className="absolute flex h-3 w-3 items-center justify-center rounded-full border border-white bg-blue-500"
                                        style={{
                                            left,
                                            top: 'calc(50% - 6px)',
                                        }}
                                    >
                                        <span className="sr-only">Rating event</span>
                                    </div>
                                    <span
                                        className="pointer-events-none absolute w-max text-[9px] font-semibold uppercase tracking-[0.2em] text-muted-foreground"
                                        style={{
                                            left: `${event.position}%`,
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

export default SlotInteractionTimeline;
