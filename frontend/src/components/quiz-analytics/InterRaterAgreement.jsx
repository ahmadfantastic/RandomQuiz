
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

const InterRaterAgreement = ({ data }) => {
    if (!data || !data.agreement) {
        return (
            <div className="p-4">
                <p>No agreement data available.</p>
            </div>
        );
    }

    const { agreement } = data;

    if (agreement.length === 0) {
        return (
            <div className="p-4">
                <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>No Data</AlertTitle>
                    <AlertDescription>
                        No common rated problems found between Instructors and Students to calculate agreement.
                    </AlertDescription>
                </Alert>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Inter-rater Agreement</CardTitle>
                    <CardDescription>
                        Agreement between Instructor ratings and Student ratings using Quadratic Weighted Kappa.
                        Scores are aggregated using the mean rounded down to the nearest valid rating.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Criterion</TableHead>
                                <TableHead>Instructor Code</TableHead>
                                <TableHead>Common Problems</TableHead>
                                <TableHead>Agreement (Kappa)</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {agreement.map((item) => (
                                <TableRow key={item.criterion_id} className={item.criterion_id === 'all' ? "bg-muted/50 font-bold" : ""}>
                                    <TableCell className="font-medium">{item.criterion_name}</TableCell>
                                    <TableCell className="font-mono text-xs">{item.instructor_code}</TableCell>
                                    <TableCell>{item.common_problems}</TableCell>
                                    <TableCell>
                                        {item.kappa_score}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            {data.details && data.details.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Detailed Comparison</CardTitle>
                        <CardDescription>
                            Individual problem ratings (Sorted by Problem ID).
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="max-h-[500px] overflow-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Problem</TableHead>
                                        {data.criteria_columns?.map((col) => (
                                            <TableHead key={col.id}>{col.name}</TableHead>
                                        ))}
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.details.map((item, index) => (
                                        <TableRow key={index}>
                                            <TableCell className="font-medium">{item.problem_label}</TableCell>
                                            {data.criteria_columns?.map((col) => {
                                                const rating = item.ratings[col.id];
                                                if (!rating) {
                                                    return <TableCell key={col.id}><span className="text-muted-foreground">-</span></TableCell>;
                                                }
                                                const match = rating.instructor === rating.student;
                                                const mismatchStyle = "bg-yellow-100 text-yellow-800 border-yellow-300 hover:bg-yellow-200";
                                                const matchStyle = "hover:bg-muted";

                                                return (
                                                    <TableCell key={col.id}>
                                                        <div className="flex items-center gap-2">
                                                            <div className="flex flex-col items-center">
                                                                <span className="text-[10px] text-muted-foreground uppercase">Inst</span>
                                                                <Popover>
                                                                    <PopoverTrigger asChild>
                                                                        <Badge variant={!match ? "outline" : "outline"} className={cn("cursor-pointer", !match ? mismatchStyle : matchStyle)}>
                                                                            {rating.instructor}
                                                                        </Badge>
                                                                    </PopoverTrigger>
                                                                    <PopoverContent className="w-64 p-3 text-xs">
                                                                        <h4 className="font-semibold mb-2">Instructor Ratings</h4>
                                                                        <div className="space-y-1">
                                                                            {rating.instructor_details?.map((d, i) => (
                                                                                <div key={i} className="flex justify-between border-b pb-1 last:border-0 last:pb-0">
                                                                                    <span>Value:</span>
                                                                                    <span className="font-mono">{d.value}</span>
                                                                                </div>
                                                                            ))}
                                                                            <div className="mt-2 pt-2 border-t font-semibold flex justify-between">
                                                                                <span>Mean:</span>
                                                                                <span>{rating.instructor_mean?.toFixed(2)}</span>
                                                                            </div>
                                                                            <div className="flex justify-between">
                                                                                <span>Aggregated:</span>
                                                                                <span>{rating.instructor}</span>
                                                                            </div>
                                                                        </div>
                                                                    </PopoverContent>
                                                                </Popover>
                                                            </div>
                                                            <div className="h-4 w-px bg-border mx-1"></div>
                                                            <div className="flex flex-col items-center">
                                                                <span className="text-[10px] text-muted-foreground uppercase">Stu</span>
                                                                <Popover>
                                                                    <PopoverTrigger asChild>
                                                                        <Badge variant={!match ? "outline" : "outline"} className={cn("cursor-pointer", !match ? mismatchStyle : matchStyle)}>
                                                                            {rating.student}
                                                                        </Badge>
                                                                    </PopoverTrigger>
                                                                    <PopoverContent className="w-64 p-3 text-xs bg-white dark:bg-popover">
                                                                        <h4 className="font-semibold mb-2">Student Ratings</h4>
                                                                        <div className="space-y-2">
                                                                            {rating.student_details?.map((d, i) => (
                                                                                <div key={i} className="bg-muted/50 p-2 rounded">
                                                                                    <div className="flex justify-between">
                                                                                        <span className="text-muted-foreground">Original Score:</span>
                                                                                        <span className="font-mono font-medium">{d.raw}</span>
                                                                                    </div>
                                                                                </div>
                                                                            ))}
                                                                            <div className="mt-2 pt-2 border-t font-semibold flex justify-between">
                                                                                <span>Mean (Raw):</span>
                                                                                <span>{rating.student_mean?.toFixed(2)}</span>
                                                                            </div>
                                                                            <div className="flex justify-between">
                                                                                <span>Mapped Score:</span>
                                                                                <span>{rating.student}</span>
                                                                            </div>
                                                                        </div>
                                                                    </PopoverContent>
                                                                </Popover>
                                                            </div>
                                                        </div>
                                                    </TableCell>
                                                );
                                            })}
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

export default InterRaterAgreement;
