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

import RatingChart from './RatingChart';







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
                            {slot.problem_distribution && slot.problem_distribution.length > 0 && (
                                <div className="w-full border-t pt-4">
                                    <h4 className="text-sm font-semibold mb-4">Problem Breakdown</h4>
                                    <ProblemStatsTable
                                        problems={slot.problem_distribution}
                                        responseType={slot.response_type}
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
