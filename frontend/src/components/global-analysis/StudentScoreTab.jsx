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
                        <CardTitle>Quiz Analysis</CardTitle>
                        <CardDescription>Performance usage statistics and ratings for your quizzes</CardDescription>
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
