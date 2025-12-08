
import React, { useState } from 'react';
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

    // Group comparison by group field
    const groupedComparison = comparison.reduce((acc, item) => {
        const group = item.group || 'Ungrouped';
        if (!acc[group]) acc[group] = [];
        acc[group].push(item);
        return acc;
    }, {});

    // Extract Overall
    const overallComparison = groupedComparison['Overall'];
    const groups = Object.keys(groupedComparison).filter(g => g !== 'Overall').sort();

    const ComparisonTable = ({ title, items, className }) => (
        <div className={`border rounded-md overflow-hidden ${className}`}>
            <div className="px-4 py-2 bg-muted/40 font-semibold text-sm border-b">
                {title}
            </div>
            <Table>
                <TableHeader className="bg-secondary/50">
                    <TableRow>
                        <TableHead className="w-[150px]">Criterion</TableHead>
                        <TableHead>Common Problems</TableHead>
                        <TableHead>Instructor Mean</TableHead>
                        <TableHead>Student Mean (Mapped)</TableHead>
                        <TableHead>Mean Diff</TableHead>
                        <TableHead>T-Statistic</TableHead>
                        <TableHead>P-Value</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {items.map((item) => (
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
        </div>
    );

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Rating Comparison by Group</CardTitle>
                    <CardDescription>
                        T-test comparison of average ratings between students and instructors, segmented by Problem Group
                    </CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                    <div className="p-4 space-y-8">
                        {overallComparison && (
                            <ComparisonTable
                                title="Overall (All Problems)"
                                items={overallComparison}
                                className="border-primary/20 shadow-sm"
                            />
                        )}

                        {groups.length > 0 && (
                            <div className="space-y-4">
                                <h3 className="font-medium text-lg text-muted-foreground">Breakdown by Group</h3>
                                {groups.map(group => (
                                    <ComparisonTable
                                        key={group}
                                        title={`Group: ${group}`}
                                        items={groupedComparison[group]}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                </CardContent >
            </Card >

            <DetailedComparisonTable details={data.details} criteria={data.criteria_columns} />
        </div >
    );
};

import { Modal } from "@/components/ui/modal";

const DetailedComparisonTable = ({ details, criteria }) => {
    const [selectedData, setSelectedData] = useState(null);

    if (!details || details.length === 0) return null;

    return (
        <>
            <Card>
                <CardHeader>
                    <CardTitle>Problem-Level Rating Comparison</CardTitle>
                    <CardDescription>
                        Detailed breakdown of average ratings and weighted scores per problem. Click on a cell to view individual ratings.
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
                                            {row.problem_label} <br />
                                            {row.problem_group || '-'}
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
                                                <TableCell
                                                    key={col.id}
                                                    className="text-center cursor-pointer hover:bg-muted/50 transition-colors"
                                                    onClick={() => setSelectedData({
                                                        title: `${row.problem_label} - ${col.name} (${col.id})`,
                                                        data: rating
                                                    })}
                                                >
                                                    <div className="flex flex-col items-center gap-1 text-xs">
                                                        <div className="grid grid-cols-2 gap-x-2 gap-y-1 w-full max-w-[120px]">
                                                            <span className="text-right text-muted-foreground">Inst:</span>
                                                            <span className="font-mono">{typeof instMean === 'number' ? instMean.toFixed(2) : instMean}</span>

                                                            <span className="text-right text-muted-foreground">Stud:</span>
                                                            <span className="font-mono">{typeof studMean === 'number' ? studMean.toFixed(2) : studMean}</span>

                                                            <span className="text-right text-muted-foreground">Diff:</span>
                                                            <span className={`font-mono font-medium ${diff > 0 ? "text-green-600" : diff < 0 ? "text-red-600" : ""}`}>
                                                                {diff > 0 ? "+" : ""}{typeof diff === 'number' ? diff.toFixed(2) : diff}
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
                </CardContent >
            </Card >

            <Modal
                open={!!selectedData}
                onOpenChange={(open) => !open && setSelectedData(null)}
                title={selectedData?.title || "Details"}
            >
                {selectedData && (
                    <div className="space-y-4">
                        <div>
                            <h4 className="font-semibold mb-2">Instructor Ratings</h4>
                            {selectedData.data.instructor_details && selectedData.data.instructor_details.length > 0 ? (
                                <div className="flex flex-wrap gap-2">
                                    {selectedData.data.instructor_details.map((d, i) => (
                                        <div key={i} className="px-2 py-1 bg-secondary rounded text-sm border">
                                            {d.value}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-muted-foreground">No details available.</p>
                            )}
                        </div>

                        <div>
                            <h4 className="font-semibold mb-2">Student Ratings</h4>
                            {selectedData.data.student_details && selectedData.data.student_details.length > 0 ? (
                                <div className="flex flex-wrap gap-2">
                                    {selectedData.data.student_details.map((d, i) => (
                                        <div key={i} className="px-2 py-1 bg-secondary rounded text-sm border flex flex-col items-center">
                                            <span><strong>Raw:</strong> {d.raw}</span>
                                            {d.mapped !== undefined && (
                                                <span className="text-xs text-muted-foreground">Mapped: {d.mapped.toFixed(2)}</span>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-muted-foreground">No details available.</p>
                            )}
                        </div>
                    </div>
                )}
            </Modal>
        </>
    );
};

export default StudentInstructorComparison;
