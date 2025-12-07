
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertCircle } from 'lucide-react';

const StudentInstructorComparison = ({ data }) => {
    if (!data || !data.comparison) {
        return (
            <div className="p-4">
                <p>No comparison data available.</p>
            </div>
        );
    }

    const { comparison } = data;

    if (comparison.length === 0) {
        return (
            <div className="p-4">
                <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>No Data</AlertTitle>
                    <AlertDescription>
                        No common rated problems found to perform comparison.
                    </AlertDescription>
                </Alert>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Student vs Instructor Comparison</CardTitle>
                    <CardDescription>
                        Comparison of average ratings using Paired T-Test. Student ratings are normalized to [0, 1].
                    </CardDescription>
                </CardHeader>
                <CardContent className="max-h-50 overflow-y-auto">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Criterion</TableHead>
                                <TableHead>Common Problems</TableHead>
                                <TableHead>Instructor Mean (0-1)</TableHead>
                                <TableHead>Student Mean (Norm)</TableHead>
                                <TableHead>Mean Diff</TableHead>
                                <TableHead>T-Statistic</TableHead>
                                <TableHead>P-Value</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {comparison.map((item) => (
                                <TableRow key={item.criterion_id}>
                                    <TableCell className="font-medium">{item.criterion_name}</TableCell>
                                    <TableCell>{item.common_problems}</TableCell>
                                    <TableCell>{item.instructor_mean}</TableCell>
                                    <TableCell>{item.student_mean_norm}</TableCell>
                                    <TableCell className={item.mean_difference > 0 ? "text-green-600" : "text-red-600"}>
                                        {item.mean_difference > 0 ? "+" : ""}{item.mean_difference}
                                    </TableCell>
                                    <TableCell>{item.t_statistic !== null ? item.t_statistic : '-'}</TableCell>
                                    <TableCell>
                                        {item.p_value !== null ? (
                                            <span className={item.p_value < 0.05 ? "font-bold text-primary" : ""}>
                                                {item.p_value}
                                                {item.p_value < 0.05 && "*"}
                                            </span>
                                        ) : '-'}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            <DetailedComparisonTable details={data.details} criteria={data.criteria_columns} />
        </div>
    );
};

const DetailedComparisonTable = ({ details, criteria }) => {
    if (!details || details.length === 0) return null;

    return (
        <Card>
            <CardHeader>
                <CardTitle>Detailed Comparison By Problem</CardTitle>
                <CardDescription>
                    Breakdown of average scores per problem.
                </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
                <div className="max-h-[500px] overflow-y-auto">
                    <Table>
                        <TableHeader className="sticky top-0 bg-secondary z-10 shadow-sm">
                            <TableRow>
                                <TableHead className="w-[100px]">Problem</TableHead>
                                {criteria.map(col => (
                                    <TableHead key={col.id} className="text-center min-w-[150px]">
                                        {col.id}
                                    </TableHead>
                                ))}
                                <TableHead className="text-center min-w-[150px] font-bold border-l bg-muted/50">
                                    Weighted
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {details.map((row) => (
                                <TableRow key={row.problem_id}>
                                    <TableCell className="font-medium whitespace-nowrap">
                                        {row.problem_label}
                                    </TableCell>
                                    {criteria.map((col) => {
                                        const rating = row.ratings[col.id];
                                        if (!rating) {
                                            return <TableCell key={col.id} className="text-center text-muted-foreground">-</TableCell>;
                                        }

                                        const instMean = rating.instructor_mean !== undefined ? rating.instructor_mean : rating.instructor;
                                        const studMean = rating.student_mean_norm !== undefined ? rating.student_mean_norm : 0;
                                        const diff = studMean - instMean;

                                        if (instMean === undefined && studMean === undefined) {
                                            return <TableCell key={col.id} className="text-center text-muted-foreground">-</TableCell>;
                                        }

                                        return (
                                            <TableCell key={col.id} className="text-center">
                                                <div className="flex flex-col items-center gap-1 text-xs">
                                                    <div className="grid grid-cols-2 gap-x-2 gap-y-1 w-full max-w-[120px]">
                                                        <span className="text-right text-muted-foreground">Inst:</span>
                                                        <span className="font-mono">{instMean.toFixed(2)}</span>

                                                        <span className="text-right text-muted-foreground">Stud:</span>
                                                        <span className="font-mono">{studMean.toFixed(2)}</span>

                                                        <span className="text-right text-muted-foreground">Diff:</span>
                                                        <span className={`font-mono font-medium ${diff > 0 ? "text-green-600" : diff < 0 ? "text-red-600" : ""}`}>
                                                            {diff > 0 ? "+" : ""}{diff.toFixed(2)}
                                                        </span>
                                                    </div>
                                                </div>
                                            </TableCell>
                                        );
                                    })}

                                    {/* Weighted Column */}
                                    <TableCell className="text-center border-l bg-muted/50">
                                        {(row.weighted_instructor !== undefined && row.weighted_student !== undefined) ? (
                                            <div className="flex flex-col items-center gap-1 text-xs font-semibold">
                                                <div className="grid grid-cols-2 gap-x-2 gap-y-1 w-full max-w-[120px]">
                                                    <span className="text-right text-muted-foreground">Inst:</span>
                                                    <span className="font-mono">{row.weighted_instructor.toFixed(2)}</span>

                                                    <span className="text-right text-muted-foreground">Stud:</span>
                                                    <span className="font-mono">{row.weighted_student.toFixed(2)}</span>

                                                    <span className="text-right text-muted-foreground">Diff:</span>
                                                    <span className={`font-mono font-medium ${row.weighted_diff > 0 ? "text-green-600" : row.weighted_diff < 0 ? "text-red-600" : ""}`}>
                                                        {row.weighted_diff > 0 ? "+" : ""}{row.weighted_diff.toFixed(2)}
                                                    </span>
                                                </div>
                                            </div>
                                        ) : (
                                            <span className="text-muted-foreground">-</span>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>
        </Card>
    );
};

export default StudentInstructorComparison;
