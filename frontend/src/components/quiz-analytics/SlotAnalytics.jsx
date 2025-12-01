import React, { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import ProblemStatsTable from './ProblemStatsTable';
import StudentProblemDetailsModal from './StudentProblemDetailsModal';

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







const SlotAnalytics = ({ slots }) => {
    const [selectedProblem, setSelectedProblem] = React.useState(null);
    const [selectedSlotId, setSelectedSlotId] = React.useState(null);
    const [isModalOpen, setIsModalOpen] = React.useState(false);

    const handleProblemClick = (slotId, problem) => {
        setSelectedSlotId(slotId);
        setSelectedProblem(problem);
        setIsModalOpen(true);
    };

    return (
        <div className="space-y-4">
            {slots.map((slot) => (
                <Card key={slot.id}>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base font-medium">{slot.label}</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex flex-col gap-6">
                            <div className="w-full">
                                {slot.response_type === 'open_text' ? (
                                    <WordCountChart data={slot.data} />
                                ) : (
                                    <RatingChart data={slot.data} />
                                )}
                            </div>
                            {slot.response_type === 'open_text' && slot.problem_distribution && slot.problem_distribution.length > 0 && (
                                <div className="w-full border-t pt-4">
                                    <h4 className="text-sm font-semibold mb-4">Problem Breakdown</h4>
                                    <ProblemStatsTable
                                        problems={slot.problem_distribution}
                                        onProblemClick={(problem) => handleProblemClick(slot.id, problem)}
                                    />
                                </div>
                            )}
                        </div>

                    </CardContent>
                </Card>
            ))}

            <StudentProblemDetailsModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                slotId={selectedSlotId}
                problem={selectedProblem}
            />
        </div>
    );
};
export default SlotAnalytics;
