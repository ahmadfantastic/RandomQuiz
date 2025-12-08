import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { RatingAnalysis } from '@/components/quiz-analytics/RatingSlotAnalytics';

const StudentRatingTab = ({ data }) => {
    return (
        <div className="space-y-8">
            {data.global_rating_distribution && data.global_rating_distribution.criteria.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Global Rating Analysis</CardTitle>
                        <CardDescription>
                            Aggregated rating distribution for all rating criteria across all quizzes.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-12">
                            <RatingAnalysis title="Overall Distribution" data={data.global_rating_distribution} />

                            {data.grouped_rating_distribution && data.grouped_rating_distribution.length > 0 && (
                                <div className="pt-8 border-t">
                                    <RatingAnalysis
                                        title="Group Comparison"
                                        groupedData={data.grouped_rating_distribution}
                                        data={(() => {
                                            // Create a combined data object for the chart to render all series
                                            // We follow the pattern in RatingSlotAnalytics.jsx
                                            const combined = [];
                                            const criteriaMap = new Map();

                                            // Get all criteria names from the first group (assuming consistency or union)
                                            // Or better, derive from global distribution keys
                                            data.global_rating_distribution.criteria.forEach(c => {
                                                criteriaMap.set(c.name, c);
                                            });

                                            // Iterate collected criteria to maintain order
                                            Array.from(criteriaMap.values()).forEach((c, idx) => {
                                                if (idx > 0) {
                                                    // Separator
                                                    combined.push({
                                                        name: `__sep__${idx}`,
                                                        distribution: []
                                                    });
                                                }

                                                // Add this criterion for EACH Group
                                                data.grouped_rating_distribution.forEach(g => {
                                                    const gc = g.data.criteria.find(item => item.name === c.name);

                                                    // If gc doesn't exist (group missing this criterion), we can still push a placeholder
                                                    // But RatingChart needs 'distribution' to be present.

                                                    if (gc) {
                                                        const label = `${c.id || c.name} (${g.group})`;
                                                        combined.push({
                                                            ...gc,
                                                            id: label,
                                                            name: label
                                                        });
                                                    }
                                                });
                                            });

                                            return { criteria: combined };
                                        })()}
                                    />
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}

            {data.quiz_anova && data.quiz_anova.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>ANOVA Results for Quizzes</CardTitle>
                        <CardDescription>Statistical comparison of student ratings across quizzes (One-way ANOVA)</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="rounded-md border">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Criterion</TableHead>
                                        <TableHead>F-statistic</TableHead>
                                        <TableHead>p-value</TableHead>
                                        <TableHead>Post-hoc Analysis (Tukey's HSD)</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.quiz_anova.map((res, idx) => (
                                        <TableRow key={idx}>
                                            <TableCell className="font-medium">{res.criterion_id}</TableCell>
                                            <TableCell>{res.f_stat?.toFixed(3) || '-'}</TableCell>
                                            <TableCell className={res.significant ? "font-bold text-green-600" : ""}>
                                                {res.p_value?.toFixed(4) || '-'}
                                            </TableCell>
                                            <TableCell>
                                                {res.significant ? (
                                                    res.tukey_results && res.tukey_results.length > 0 ? (
                                                        <div className="text-xs space-y-1">
                                                            {res.tukey_results.map((tukeyRes, tukeyIdx) => (
                                                                <div key={tukeyIdx}>{tukeyRes}</div>
                                                            ))}
                                                        </div>
                                                    ) : (
                                                        <span className="text-muted-foreground italic text-xs">No significant pairwise differences</span>
                                                    )
                                                ) : (
                                                    '-'
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
};

export default StudentRatingTab;
