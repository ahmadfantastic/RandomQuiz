import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { RatingAnalysis } from '@/components/quiz-analytics/RatingSlotAnalytics';
import { Link } from 'react-router-dom';
import CorrelationMatrix from '../quiz-analytics/CorrelationMatrix';
import CFAAnalysis from './CFAAnalysis';

const StudentRatingTab = ({ data, roundToTwo }) => {
    return (
        <div className="space-y-8">
            {data.quiz_analysis && data.quiz_analysis.quizzes.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Quiz Rating Overview</CardTitle>
                        <CardDescription>Average ratings per criterion for each quiz</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="rounded-md border">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Quiz Title</TableHead>
                                        <TableHead>Responses</TableHead>
                                        {data.quiz_analysis.all_criteria.map(c => (
                                            <TableHead key={c}>{c}</TableHead>
                                        ))}
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.quiz_analysis.quizzes.map(quiz => (
                                        <TableRow key={quiz.id}>
                                            <TableCell className="font-medium">
                                                <Link to={`/quizzes/${quiz.id}/analytics`} className="hover:underline text-primary">
                                                    {quiz.title}
                                                </Link>
                                            </TableCell>
                                            <TableCell>{quiz.response_count}</TableCell>
                                            {data.quiz_analysis.all_criteria.map(c => (
                                                <TableCell key={c}>
                                                    {quiz.means && quiz.means[c] !== undefined
                                                        ? roundToTwo(quiz.means[c])
                                                        : '-'}
                                                </TableCell>
                                            ))}
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </CardContent>
                </Card>
            )}

            {data.global_rating_distribution && data.global_rating_distribution.criteria.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Aggregate Rating Distribution</CardTitle>
                        <CardDescription>
                            Distribution of ratings across all quizzes, aggregated by criterion
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
                        <CardTitle>Rating Variance Analysis (ANOVA)</CardTitle>
                        <CardDescription>One-way ANOVA comparing student ratings across quizzes for each criterion</CardDescription>
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
            {data.inter_criterion_correlation && (
                <CorrelationMatrix data={data.inter_criterion_correlation} />
            )}

            {data.factor_analysis && (
                <CFAAnalysis results={data.factor_analysis} />
            )}
        </div>
    );
};

export default StudentRatingTab;
