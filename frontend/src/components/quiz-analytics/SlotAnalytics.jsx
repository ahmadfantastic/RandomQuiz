import React, { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const WordCountChart = ({ data }) => {
    const { raw_values, min, max } = data;

    const chartData = useMemo(() => {
        if (!raw_values || raw_values.length === 0) return [];

        const binCount = 5;
        const range = max - min;
        const binSize = range > 0 ? range / binCount : 1;

        const bins = Array.from({ length: binCount }, (_, i) => ({
            range: `${Math.round(min + i * binSize)} - ${Math.round(min + (i + 1) * binSize)} words`,
            count: 0,
        }));

        raw_values.forEach(val => {
            const binIndex = Math.min(
                Math.floor((val - min) / binSize),
                binCount - 1
            );
            if (binIndex >= 0) {
                bins[binIndex].count++;
            }
        });

        return bins;
    }, [raw_values, min, max]);

    if (!raw_values || raw_values.length === 0) {
        return <div className="text-center text-muted-foreground py-8">No answers yet</div>;
    }

    return (
        <div className="h-[200px] w-full">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="range" tick={{ fontSize: 10 }} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
};

const SingleCriterionChart = ({ criterion }) => {
    const { distribution, name } = criterion;

    // Sort distribution by value to ensure correct order
    const sortedDistribution = useMemo(() => {
        return [...distribution].sort((a, b) => a.value - b.value);
    }, [distribution]);

    const chartData = useMemo(() => {
        const entry = { name: 'Distribution' };
        sortedDistribution.forEach(d => {
            entry[d.label] = d.percentage;
            entry[`${d.label}_count`] = d.count;
            entry[`${d.label}_value`] = d.value;
        });
        return [entry];
    }, [sortedDistribution]);

    const COLORS = [
        '#ef4444', // Disagree
        '#fca5a5', // Slightly disagree
        '#9ca3af', // Neutral
        '#93c5fd', // Slightly agree
        '#2563eb', // Agree
    ];

    return (
        <div className="mb-6 last:mb-0">
            <h5 className="text-sm font-medium mb-2">{name}</h5>
            <div className="h-[60px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart layout="vertical" data={chartData} barSize={30}>
                        <XAxis type="number" hide />
                        <YAxis type="category" dataKey="name" hide />
                        <Tooltip
                            wrapperStyle={{ zIndex: 1000 }}
                            content={({ active, payload }) => {
                                if (!active || !payload || !payload.length) return null;

                                const data = payload[0].payload;
                                // Create ordered list of items
                                const items = sortedDistribution.map(d => ({
                                    label: d.label,
                                    percentage: data[d.label] || 0,
                                    count: data[`${d.label}_count`] || 0,
                                    color: COLORS[sortedDistribution.indexOf(d) % COLORS.length]
                                }));

                                return (
                                    <div className="bg-background border rounded p-2 shadow-lg text-xs">
                                        {items.map((item, idx) => (
                                            <div key={idx} className="flex items-center gap-2 mb-1 last:mb-0">
                                                <div
                                                    className="w-2 h-2 rounded-sm"
                                                    style={{ backgroundColor: item.color }}
                                                />
                                                <span className="font-medium">{item.label}:</span>
                                                <span>{Math.round(item.percentage)}% ({item.count})</span>
                                            </div>
                                        ))}
                                    </div>
                                );
                            }}
                        />
                        {sortedDistribution.map((d, index) => (
                            <Bar
                                key={d.label}
                                dataKey={d.label}
                                stackId="a"
                                fill={COLORS[index % COLORS.length]}
                            />
                        ))}
                    </BarChart>
                </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap gap-2 mt-1 justify-center">
                {sortedDistribution.map((d, index) => (
                    <div key={d.label} className="flex items-center text-[10px] text-muted-foreground">
                        <div
                            className="w-2 h-2 mr-1 rounded-sm"
                            style={{ backgroundColor: COLORS[index % COLORS.length] }}
                        />
                        {d.label} ({Math.round(d.percentage)}%)
                    </div>
                ))}
            </div>
        </div>
    );
};

const RatingChart = ({ data }) => {
    // New format: data.criteria is a list of criteria distributions
    const criteria = data?.criteria;

    if (!criteria || criteria.length === 0) {
        // Fallback for old format or empty
        if (data?.distribution) {
            return <SingleCriterionChart criterion={{ name: 'Overall', distribution: data.distribution }} />;
        }
        return <div className="text-center text-muted-foreground py-8">No ratings yet</div>;
    }

    return (
        <div className="space-y-2">
            {criteria.map((criterion) => (
                <SingleCriterionChart key={criterion.criterion_id} criterion={criterion} />
            ))}
        </div>
    );
};

const ProblemDistribution = ({ distribution }) => {
    if (!distribution || distribution.length === 0) {
        return null;
    }

    return (
        <div className="mt-4 pt-4 border-t">
            <h4 className="text-sm font-semibold mb-2">Problem Selection</h4>
            <div className="space-y-2">
                {distribution.map((item, index) => (
                    <div key={index} className="flex justify-between items-center text-sm">
                        <span className="truncate flex-1 mr-4" title={item.label}>
                            {item.label}
                        </span>
                        <span className="text-muted-foreground bg-muted px-2 py-0.5 rounded text-xs">
                            {item.count} times
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
};

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

const SlotInteractionTimeline = ({ interactions }) => {
    const [selectedStudent, setSelectedStudent] = React.useState('');

    if (!interactions || interactions.length === 0) {
        return null;
    }

    // Get unique students
    const students = useMemo(() => {
        const uniqueStudents = [...new Set(interactions.map(i => i.student_id))];
        return uniqueStudents.sort();
    }, [interactions]);

    // Set initial student if not set
    React.useEffect(() => {
        if (!selectedStudent && students.length > 0) {
            setSelectedStudent(students[0]);
        }
    }, [students, selectedStudent]);

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
        <div className="mt-4 pt-4 border-t">
            <div className="flex items-center justify-between gap-3 mb-2">
                <div>
                    <p className="text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
                        Student Interactions
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <select
                        value={selectedStudent}
                        onChange={(e) => setSelectedStudent(e.target.value)}
                        className="text-xs border rounded px-2 py-1 bg-background"
                    >
                        {students.map(student => (
                            <option key={student} value={student}>
                                {student}
                            </option>
                        ))}
                    </select>
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

const SlotAnalytics = ({ slots }) => {
    return (
        <div className="space-y-4">
            {slots.map((slot) => (
                <Card key={slot.id}>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base font-medium">{slot.label}</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {slot.response_type === 'open_text' ? (
                            <WordCountChart data={slot.data} />
                        ) : (
                            <RatingChart data={slot.data} />
                        )}
                        <SlotInteractionTimeline interactions={slot.interactions} />
                        <ProblemDistribution distribution={slot.problem_distribution} />
                    </CardContent>
                </Card>
            ))}
        </div>
    );
};
export default SlotAnalytics;
