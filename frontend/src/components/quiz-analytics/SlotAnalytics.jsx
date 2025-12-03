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

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const RatingAnalysis = ({ title, data, groupedData }) => {
    const { headers, rows } = useMemo(() => {
        if (groupedData) {
            // Pivoted table for Group Comparison
            // Headers: Criterion | Group A | Group B ...
            const groups = groupedData.map(g => g.group);
            const headers = ['Criterion', ...groups];

            // Rows: Criterion Name | Avg A | Avg B ...
            // Assume all groups have same criteria (or handle missing)
            const criteriaNames = groupedData[0]?.data?.criteria?.map(c => c.name) || [];

            const rows = criteriaNames.map(cName => {
                const row = { name: cName, values: [] };
                groups.forEach((gName, idx) => {
                    const gData = groupedData[idx];
                    const criterion = gData.data.criteria.find(c => c.name === cName);
                    if (criterion) {
                        let totalScore = 0;
                        let totalCount = 0;
                        criterion.distribution.forEach(d => {
                            totalScore += d.value * d.count;
                            totalCount += d.count;
                        });
                        row.values.push(totalCount > 0 ? (totalScore / totalCount).toFixed(2) : '—');
                    } else {
                        row.values.push('—');
                    }
                });
                return row;
            });
            return { headers, rows };
        } else {
            // Standard table for Overall
            if (!data?.criteria) return { headers: [], rows: [] };
            const headers = ['Criterion', 'Average'];
            const rows = data.criteria.map(c => {
                let totalScore = 0;
                let totalCount = 0;
                c.distribution.forEach(d => {
                    totalScore += d.value * d.count;
                    totalCount += d.count;
                });
                return {
                    name: c.name,
                    values: [totalCount > 0 ? (totalScore / totalCount).toFixed(2) : 'N/A']
                };
            });
            return { headers, rows };
        }
    }, [data, groupedData]);

    return (
        <div className="space-y-4">
            <h4 className="text-sm font-semibold">{title}</h4>
            <div className="flex flex-col lg:flex-row gap-6">
                <div className="w-full lg:w-1/3 shrink-0">
                    <div className="rounded-md border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    {headers.map((h, i) => (
                                        <TableHead key={i} className={i > 0 ? "text-right" : ""}>{h}</TableHead>
                                    ))}
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {rows.map((row, idx) => (
                                    <TableRow key={idx}>
                                        <TableCell className="font-medium">{row.name}</TableCell>
                                        {row.values.map((v, i) => (
                                            <TableCell key={i} className="text-right">{v}</TableCell>
                                        ))}
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                </div>
                <div className="w-full lg:w-2/3 min-h-[300px]">
                    <RatingChart data={data} dense={!!groupedData} />
                </div>
            </div>
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
                                    <div className="space-y-12">
                                        <RatingAnalysis title="Overall" data={slot.data} />

                                        {slot.data.grouped_data && slot.data.grouped_data.length > 0 && (
                                            <RatingAnalysis
                                                title="Group Comparison"
                                                groupedData={slot.data.grouped_data}
                                                data={(() => {
                                                    const combined = [];
                                                    const criteria = slot.data.criteria || [];

                                                    criteria.forEach((c, idx) => {
                                                        if (idx > 0) {
                                                            // Add separator
                                                            combined.push({
                                                                name: `__sep__${idx}`,
                                                                distribution: []
                                                            });
                                                        }
                                                        // Add Groups
                                                        slot.data.grouped_data.forEach(g => {
                                                            const gc = g.data.criteria.find(item => item.name === c.name);
                                                            if (gc) {
                                                                combined.push({
                                                                    ...gc,
                                                                    name: `${c.name} (${g.group})`
                                                                });
                                                            }
                                                        });
                                                    });

                                                    return { criteria: combined };
                                                })()}
                                            />
                                        )}
                                    </div>
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
