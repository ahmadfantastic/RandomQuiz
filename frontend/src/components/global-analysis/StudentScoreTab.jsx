import React from 'react';
import ScoreVsRatingAnalysis from '@/components/quiz-analytics/ScoreVsRatingAnalysis';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Link } from 'react-router-dom';

const StudentScoreTab = ({ data, roundToTwo }) => {
    return (
        <div className="space-y-8">

            {data.quiz_analysis && data.quiz_analysis.quizzes.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Answer Performance Analysis</CardTitle>
                        <CardDescription>Aggregated performance statistics (score, time, word count) for all quizzes</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="rounded-md border">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Quiz Title</TableHead>
                                        <TableHead>Responses</TableHead>
                                        <TableHead>Avg Time (min)</TableHead>
                                        <TableHead>Avg Words</TableHead>
                                        <TableHead>Avg Score</TableHead>
                                        <TableHead>Std Dev</TableHead>
                                        <TableHead>Cronbach Alpha</TableHead>
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
                                            <TableCell>{roundToTwo(quiz.avg_time_minutes)}</TableCell>
                                            <TableCell>{quiz.avg_word_count !== undefined ? roundToTwo(quiz.avg_word_count) : '-'}</TableCell>
                                            <TableCell>{quiz.avg_score !== undefined ? roundToTwo(quiz.avg_score) : '-'}</TableCell>
                                            <TableCell>{quiz.score_std_dev !== undefined && quiz.score_std_dev !== null ? roundToTwo(quiz.score_std_dev) : '-'}</TableCell>
                                            <TableCell>
                                                {roundToTwo(quiz.cronbach_alpha)}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </CardContent>
                </Card>
            )}

            {data.quiz_score_anova && (
                <Card>
                    <CardHeader>
                        <CardTitle>Score Variance Analysis (ANOVA)</CardTitle>
                        <CardDescription>One-way ANOVA comparing student scores across quizzes to identify significant performance differences</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="rounded-md border">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Comparison</TableHead>
                                        <TableHead>F-statistic</TableHead>
                                        <TableHead>p-value</TableHead>
                                        <TableHead>Post-hoc Analysis (Tukey's HSD)</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    <TableRow>
                                        <TableCell className="font-medium">All Quizzes</TableCell>
                                        <TableCell>{data.quiz_score_anova.f_stat !== null ? data.quiz_score_anova.f_stat.toFixed(3) : '-'}</TableCell>
                                        <TableCell className={data.quiz_score_anova.significant ? "font-bold text-green-600" : ""}>
                                            {data.quiz_score_anova.p_value !== null ? data.quiz_score_anova.p_value.toFixed(4) : '-'}
                                        </TableCell>
                                        <TableCell>
                                            {data.quiz_score_anova.significant ? (
                                                data.quiz_score_anova.tukey_results && data.quiz_score_anova.tukey_results.length > 0 ? (
                                                    <div className="text-xs space-y-1">
                                                        {data.quiz_score_anova.tukey_results.map((tukeyRes, tukeyIdx) => (
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
                                </TableBody>
                            </Table>
                        </div>
                    </CardContent>
                </Card>
            )}

            {data.score_correlation && (
                <ScoreVsRatingAnalysis data={data} />
            )}

            {data.time_correlation && (
                <ScoreVsRatingAnalysis
                    data={{ score_correlation: data.time_correlation }}
                    title="Score vs Time Correlation Analysis"
                    description="Analysis of how quiz completion time correlates with student graded scores."
                    yAxisLabel="Time (minutes)"
                />
            )}

            {data.word_count_correlation && (
                <ScoreVsRatingAnalysis
                    data={{ score_correlation: data.word_count_correlation }}
                    title="Score vs Word Count Correlation Analysis"
                    description="Analysis of how total word count of text answers correlates with student graded scores."
                    yAxisLabel="Word Count"
                />
            )}
        </div>
    );
};

export default StudentScoreTab;
