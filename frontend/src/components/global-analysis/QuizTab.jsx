import React from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const QuizTab = ({ data, roundToTwo }) => {
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
                                        {data.quiz_analysis.all_criteria.map(c => (
                                            <TableHead key={c}>{c}</TableHead>
                                        ))}
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
                                            {data.quiz_analysis.all_criteria.map(c => (
                                                <TableCell key={c}>
                                                    {quiz.means && quiz.means[c] !== undefined
                                                        ? roundToTwo(quiz.means[c])
                                                        : '-'}
                                                </TableCell>
                                            ))}
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
        </div>
    );
};

export default QuizTab;
