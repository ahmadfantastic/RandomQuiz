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

const calculateStats = (distribution) => {
    let totalScore = 0;
    let totalCount = 0;
    let sumSq = 0;

    distribution.forEach(d => {
        const val = d.value;
        const count = d.count;
        totalScore += val * count;
        totalCount += count;
        sumSq += val * val * count;
    });

    if (totalCount === 0) return { mean: 0, variance: 0, n: 0 };

    const mean = totalScore / totalCount;
    // Sample variance
    const variance = totalCount > 1
        ? (sumSq - (totalScore * totalScore) / totalCount) / (totalCount - 1)
        : 0;

    return { mean, variance, n: totalCount };
};

// Welch's t-test
const calculateTTest = (stats1, stats2) => {
    if (stats1.n < 2 || stats2.n < 2) return null;
    if (stats1.variance === 0 && stats2.variance === 0) return null;

    const num = stats1.mean - stats2.mean;
    const denom = Math.sqrt((stats1.variance / stats1.n) + (stats2.variance / stats2.n));

    if (denom === 0) return null;

    const t = num / denom;

    // Degrees of freedom
    const v1 = stats1.variance / stats1.n;
    const v2 = stats2.variance / stats2.n;
    const df = Math.pow(v1 + v2, 2) / ((Math.pow(v1, 2) / (stats1.n - 1)) + (Math.pow(v2, 2) / (stats2.n - 1)));

    return { t, df };
};

function normalCDF(x) {
    var t = 1 / (1 + .2316419 * Math.abs(x));
    var d = .3989423 * Math.exp(-x * x / 2);
    var prob = d * t * (.3193815 + t * (-.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
    if (x > 0) prob = 1 - prob;
    return prob;
}

function getPValue(t, df) {
    // Approximation using Normal distribution
    // Note: This underestimates p-value for small df (increases Type I error risk)
    // but is acceptable for a general overview without heavy libraries.
    // We could use a correction for better accuracy if needed.
    return 2 * (1 - normalCDF(Math.abs(t)));
}

const RatingAnalysis = ({ title, data, groupedData }) => {
    const { headers, rows } = useMemo(() => {
        if (groupedData) {
            // Pivoted table for Group Comparison
            const groups = groupedData.map(g => g.group);
            let headers = ['Criterion', ...groups];
            const isTwoGroups = groups.length === 2;

            if (isTwoGroups) {
                headers.push('Sig. (2-tailed)');
                headers.push('Sig. (1-tailed)');
            }

            const criteriaNames = groupedData[0]?.data?.criteria?.map(c => c.name) || [];

            const rows = criteriaNames.map(cName => {
                const row = { name: cName, values: [] };
                const groupStats = [];

                groups.forEach((gName, idx) => {
                    const gData = groupedData[idx];
                    const criterion = gData.data.criteria.find(c => c.name === cName);
                    if (criterion) {
                        const stats = calculateStats(criterion.distribution);
                        groupStats.push(stats);
                        row.values.push(stats.n > 0 ? stats.mean.toFixed(2) : '—');
                    } else {
                        groupStats.push({ mean: 0, variance: 0, n: 0 });
                        row.values.push('—');
                    }
                });

                if (isTwoGroups) {
                    const tResult = calculateTTest(groupStats[0], groupStats[1]);
                    if (tResult) {
                        const pVal2Tailed = getPValue(tResult.t, tResult.df);
                        const pVal1Tailed = pVal2Tailed / 2;

                        const isSig2 = pVal2Tailed < 0.05;
                        const pDisplay2 = pVal2Tailed < 0.001 ? '< 0.001' : pVal2Tailed.toFixed(3);

                        const isSig1 = pVal1Tailed < 0.05;
                        const pDisplay1 = pVal1Tailed < 0.001 ? '< 0.001' : pVal1Tailed.toFixed(3);

                        row.values.push(
                            <span className={isSig2 ? "font-bold text-primary" : "text-muted-foreground"}>
                                {pDisplay2}
                                {isSig2 && "*"}
                            </span>
                        );
                        row.values.push(
                            <span className={isSig1 ? "font-bold text-primary" : "text-muted-foreground"}>
                                {pDisplay1}
                                {isSig1 && "*"}
                            </span>
                        );
                    } else {
                        row.values.push('—');
                        row.values.push('—');
                    }
                }

                return row;
            });
            return { headers, rows };
        } else {
            // Standard table for Overall
            if (!data?.criteria) return { headers: [], rows: [] };
            const headers = ['Criterion', 'Average'];
            const rows = data.criteria.map(c => {
                const stats = calculateStats(c.distribution);
                return {
                    name: c.name,
                    values: [stats.n > 0 ? stats.mean.toFixed(2) : 'N/A']
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
