import React, { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import RatingChart from './RatingChart';
import ProblemStatsTable from './ProblemStatsTable';
import StudentProblemDetailsModal from './StudentProblemDetailsModal';

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
    return 2 * (1 - normalCDF(Math.abs(t)));
}

// Consistent rounding helper
const roundToTwo = (num) => {
    if (num === undefined || num === null) return '-';
    return (Math.round((num + Number.EPSILON) * 100) / 100).toFixed(2);
};

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
                        row.values.push(stats.n > 0 ? roundToTwo(stats.mean) : '—');
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
                    values: [stats.n > 0 ? roundToTwo(stats.mean) : 'N/A']
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

const RatingSlotAnalytics = ({ slot }) => {
    const [selectedProblem, setSelectedProblem] = useState(null);
    const [isModalOpen, setIsModalOpen] = useState(false);

    const handleProblemClick = (problem) => {
        setSelectedProblem(problem);
        setIsModalOpen(true);
    };

    if (!slot) return null;

    return (
        <div className="space-y-4">
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-base font-medium">{slot.label}</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-col gap-6">
                        <div className="w-full">
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
                        </div>
                        {slot.problem_distribution && slot.problem_distribution.length > 0 && (
                            <div className="w-full border-t pt-4">
                                <h4 className="text-sm font-semibold mb-4">Problem Breakdown</h4>
                                <ProblemStatsTable
                                    problems={slot.problem_distribution}
                                    responseType={slot.response_type}
                                    onProblemClick={handleProblemClick}
                                />
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            <StudentProblemDetailsModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                slotId={slot.id}
                problem={selectedProblem}
            />
        </div>
    );
};

export default RatingSlotAnalytics;
