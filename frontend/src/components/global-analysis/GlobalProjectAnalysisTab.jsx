import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const ProjectAnalysisTab = ({ data, roundToTwo }) => {
    if (!data) return null;

    const { quiz_correlations, aggregated_quadrants } = data;

    // Sort correlations by quiz title
    const sortedCorrelations = [...(quiz_correlations || [])].sort((a, b) => a.quiz_title.localeCompare(b.quiz_title));

    // Total counts can be derived from sums of one valid quad setup, e.g. med_med
    const totalStudents = aggregated_quadrants?.med_med ?
        (aggregated_quadrants.med_med.masters + aggregated_quadrants.med_med.implementers + aggregated_quadrants.med_med.conceptualizers + aggregated_quadrants.med_med.strugglers)
        : 0;

    const renderQuadrantTable = (counts, title, total) => {
        if (!counts) return null;

        const getPct = (val) => total > 0 ? ((val / total) * 100).toFixed(1) + '%' : '0%';

        return (
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">{title}</CardTitle>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="h-8">Learner Profile</TableHead>
                                <TableHead className="h-8 text-right">Count</TableHead>
                                <TableHead className="h-8 text-right">Percentage</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            <TableRow className="h-8">
                                <TableCell className="font-medium text-green-700 py-1">Masters</TableCell>
                                <TableCell className="text-right py-1">{counts.masters}</TableCell>
                                <TableCell className="text-right py-1">{getPct(counts.masters)}</TableCell>
                            </TableRow>
                            <TableRow className="h-8">
                                <TableCell className="font-medium text-blue-700 py-1">Conceptualizers</TableCell>
                                <TableCell className="text-right py-1">{counts.conceptualizers}</TableCell>
                                <TableCell className="text-right py-1">{getPct(counts.conceptualizers)}</TableCell>
                            </TableRow>
                            <TableRow className="h-8">
                                <TableCell className="font-medium text-orange-700 py-1">Implementers</TableCell>
                                <TableCell className="text-right py-1">{counts.implementers}</TableCell>
                                <TableCell className="text-right py-1">{getPct(counts.implementers)}</TableCell>
                            </TableRow>
                            <TableRow className="h-8">
                                <TableCell className="font-medium text-red-700 py-1">Strugglers</TableCell>
                                <TableCell className="text-right py-1">{counts.strugglers}</TableCell>
                                <TableCell className="text-right py-1">{getPct(counts.strugglers)}</TableCell>
                            </TableRow>
                            <TableRow className="h-8 border-t bg-muted/50">
                                <TableCell className="font-bold py-1">Total</TableCell>
                                <TableCell className="text-right font-bold py-1">{total}</TableCell>
                                <TableCell className="text-right font-bold py-1"></TableCell>
                            </TableRow>
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        );
    };

    return (
        <div className="space-y-8">
            {/* Correlation Table */}
            <Card>
                <CardHeader>
                    <CardTitle>Project Score vs Quiz Score Correlations</CardTitle>
                    <CardDescription>
                        Correlation between project scores and quiz scores for each quiz.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Quiz</TableHead>
                                <TableHead className="text-right">Students</TableHead>
                                <TableHead className="text-right">% of Total</TableHead>
                                <TableHead className="text-right">Pearson (r)</TableHead>
                                <TableHead className="text-right">Pearson (p)</TableHead>
                                <TableHead className="text-right">Spearman (ρ)</TableHead>
                                <TableHead className="text-right">Spearman (p)</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {sortedCorrelations.map(c => (
                                <TableRow key={c.quiz_id}>
                                    <TableCell className="font-medium">{c.quiz_title}</TableCell>
                                    <TableCell className="text-right">{c.count}</TableCell>
                                    <TableCell className="text-right text-muted-foreground">{totalStudents > 0 ? ((c.count / totalStudents) * 100).toFixed(1) + '%' : '-'}</TableCell>
                                    <TableCell className="text-right">{c.pearson_r !== null ? c.pearson_r : '-'}</TableCell>
                                    <TableCell className="text-right text-muted-foreground text-xs">{c.pearson_p !== null ? c.pearson_p : '-'}</TableCell>
                                    <TableCell className="text-right">{c.spearman_rho !== null ? c.spearman_rho : '-'}</TableCell>
                                    <TableCell className="text-right text-muted-foreground text-xs">{c.spearman_p !== null ? c.spearman_p : '-'}</TableCell>
                                </TableRow>
                            ))}
                            {sortedCorrelations.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={7} className="text-center text-muted-foreground h-24">
                                        No quiz data available.
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            {/* Aggregated Quadrants */}
            <div>
                <h3 className="text-lg font-semibold mb-4">Learner Profile Analysis (Aggregated)</h3>
                <p className="text-sm text-muted-foreground mb-4">
                    Students classified into profiles based on their performance within their specific quiz.
                    Counts are aggregated across all quizzes.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {renderQuadrantTable(aggregated_quadrants?.med_med, "Median / Median", totalStudents)}

                    {/* Only show half-max cols if we have valid counts */}
                    {aggregated_quadrants?.med_half?.valid_count > 0 &&
                        renderQuadrantTable(aggregated_quadrants.med_half, "Med / 50% Max", aggregated_quadrants.med_half.valid_count)
                    }

                    {renderQuadrantTable(aggregated_quadrants?.max95_med, "95% Max / Median", totalStudents)}

                    {aggregated_quadrants?.max95_half?.valid_count > 0 &&
                        renderQuadrantTable(aggregated_quadrants.max95_half, "95% Max / 50% Max", aggregated_quadrants.max95_half.valid_count)
                    }
                </div>
            </div>
        </div>
    );
};

export default ProjectAnalysisTab;
