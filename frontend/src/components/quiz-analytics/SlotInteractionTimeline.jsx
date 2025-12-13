import React, { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';

const clamp = (value, min, max) => {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return min;
    }
    return Math.min(Math.max(value, min), max);
};

const formatTime = (isoString) => {
    if (!isoString) return '';
    return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};

const computeTypingDelta = (metadata) => {
    const diff = metadata?.diff;
    if (!diff) return 0;
    const added = typeof diff.added === 'string' ? diff.added.length : 0;
    const removed = typeof diff.removed === 'string' ? diff.removed.length : 0;
    return added - removed;
};

const createTypingTitle = (metadata, createdAt) => {
    const timeStr = formatTime(createdAt);
    const timePrefix = timeStr ? `${timeStr} — ` : '';

    const diff = metadata?.diff;
    if (!diff) {
        return `${timePrefix}Typing interaction`;
    }
    const added = typeof diff.added === 'string' ? diff.added.length : 0;
    const removed = typeof diff.removed === 'string' ? diff.removed.length : 0;
    const parts = [];
    if (added) parts.push(`${added} char${added === 1 ? '' : 's'} added`);
    if (removed) parts.push(`${removed} char${removed === 1 ? '' : 's'} removed`);
    if (!parts.length) {
        return `${timePrefix}Typing interaction`;
    }
    return `${timePrefix}Typing — ${parts.join(', ')}`;
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

    const [tooltip, setTooltip] = useState(null);

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
        <div className="relative">
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
            <div
                className="relative h-28 rounded-xl border border-border/70 bg-muted/80"
                onMouseLeave={() => setTooltip(null)}
            >
                {/* Background lines and labels */}
                <div className="absolute left-0 right-0 top-1/2 h-[1px] bg-border" />
                <div className="pointer-events-none absolute inset-x-4 bottom-0 flex justify-between text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
                    <span>{timeLabels.start}</span>
                    <span>{timeLabels.end}</span>
                </div>

                {/* Interactions Container - overflow visible for tooltip but items are contained */}
                <div className="absolute inset-0 overflow-hidden rounded-xl">
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
                                const title = createTypingTitle(event.metadata, event.created_at);
                                return (
                                    <div
                                        key={`${event.created_at}-${index}`}
                                        className="absolute w-4 -ml-2 flex justify-center cursor-pointer group z-10 hover:z-20"
                                        style={{
                                            left: `${event.position}%`,
                                            top,
                                            height: `${height}px`,
                                        }}
                                        onMouseEnter={(e) => {
                                            const rect = e.currentTarget.getBoundingClientRect();
                                            setTooltip({
                                                rect,
                                                content: title,
                                                align: isPositive ? 'bottom' : 'top'
                                            });
                                        }}
                                    >
                                        <div className={`w-0.5 h-full ${barColor}`} />
                                    </div>
                                );
                            }
                            if (event.event_type === 'rating' || event.event_type === 'rating_selection') {
                                const value = event.metadata?.option_value;
                                const criterionId = event.metadata?.criterion_id;
                                const criterionLabel = criterionId ?? 'Criterion';
                                const label = typeof value === 'number' ? value : value ?? 'rating';
                                const title = `Rating ${label} — ${criterionLabel} (${formatTime(event.created_at)})`;

                                return (
                                    <div key={`${event.created_at}-${index}`}>
                                        <div
                                            className="absolute flex h-3 w-3 -ml-1.5 items-center justify-center rounded-full border border-white bg-blue-500 cursor-pointer z-10 hover:z-20"
                                            style={{
                                                left: `${event.position}%`,
                                                top: 'calc(50% - 6px)',
                                            }}
                                            onMouseEnter={(e) => {
                                                const rect = e.currentTarget.getBoundingClientRect();
                                                setTooltip({
                                                    rect,
                                                    content: title,
                                                    align: 'bottom'
                                                });
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

            {/* Custom Tooltip using Portal */}
            {tooltip && createPortal(
                <div
                    className="fixed z-[9999] px-2 py-1 text-xs font-medium text-white bg-slate-900 rounded shadow-lg pointer-events-none whitespace-nowrap"
                    style={{
                        left: tooltip.rect.left + tooltip.rect.width / 2,
                        top: tooltip.align === 'top'
                            ? tooltip.rect.top - 8
                            : tooltip.rect.bottom + 8,
                        transform: `translate(-50%, ${tooltip.align === 'top' ? '-100%' : '0'})`,
                    }}
                >
                    {tooltip.content}
                    {/* Arrow */}
                    <div
                        className={`absolute left-1/2 -ml-1 border-4 border-transparent ${tooltip.align === 'top'
                            ? 'bottom-[-7px] border-t-slate-900'
                            : 'top-[-7px] border-b-slate-900'
                            }`}
                    />
                </div>,
                document.body
            )}
        </div>
    );
};

export default SlotInteractionTimeline;
