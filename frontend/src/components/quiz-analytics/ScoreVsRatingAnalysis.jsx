import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Label } from 'recharts';

const ScoreVsRatingAnalysis = ({ data, title, description, yAxisLabel = "Rating", xAxisLabel = "Grade Score" }) => {
    if (!data || !data.score_correlation) {
        return (
            <div className="p-4">
                <p>No score correlation data available.</p>
            </div>
        );
    }

    const { score_correlation } = data;

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>{title || "Score vs Rating Correlation Analysis"}</CardTitle>
                    <CardDescription>
                        {description || "Analysis of how student ratings correlate with graded scores."}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="space-y-12">
                        {score_correlation.map((item, index) => (
                            <div key={index} className="flex flex-col lg:flex-row gap-6 items-start border-b pb-12 last:border-0 last:pb-0">
                                {/* Left Column: Transposed Stats Table */}
                                <div className="w-full lg:w-1/3 shrink-0">
                                    <h3 className="text-lg font-semibold mb-4">{item.name}</h3>
                                    <div className="rounded-md border">
                                        <Table>
                                            <TableBody>
                                                <TableRow>
                                                    <TableCell className="font-medium bg-muted/50 w-1/2">Sample Size</TableCell>
                                                    <TableCell>{item.count}</TableCell>
                                                </TableRow>
                                                <TableRow>
                                                    <TableCell className="font-medium bg-muted/50">Pearson r</TableCell>
                                                    <TableCell className={Math.abs(item.pearson_r) > 0.5 ? "font-bold text-primary" : ""}>
                                                        {item.pearson_r !== null ? item.pearson_r : '-'}
                                                    </TableCell>
                                                </TableRow>
                                                <TableRow>
                                                    <TableCell className="font-medium bg-muted/50">P-Value (Pearson)</TableCell>
                                                    <TableCell>
                                                        {item.pearson_p !== null ? (
                                                            <span className={item.pearson_p < 0.05 ? "text-green-600 font-bold" : ""}>
                                                                {item.pearson_p}{item.pearson_p < 0.05 && "*"}
                                                            </span>
                                                        ) : '-'}
                                                    </TableCell>
                                                </TableRow>
                                                <TableRow>
                                                    <TableCell className="font-medium bg-muted/50">Spearman rho</TableCell>
                                                    <TableCell className={Math.abs(item.spearman_rho) > 0.5 ? "font-bold text-primary" : ""}>
                                                        {item.spearman_rho !== null ? item.spearman_rho : '-'}
                                                    </TableCell>
                                                </TableRow>
                                                <TableRow>
                                                    <TableCell className="font-medium bg-muted/50">P-Value (Spearman)</TableCell>
                                                    <TableCell>
                                                        {item.spearman_p !== null ? (
                                                            <span className={item.spearman_p < 0.05 ? "text-green-600 font-bold" : ""}>
                                                                {item.spearman_p}{item.spearman_p < 0.05 && "*"}
                                                            </span>
                                                        ) : '-'}
                                                    </TableCell>
                                                </TableRow>
                                            </TableBody>
                                        </Table>
                                    </div>
                                </div>

                                {/* Right Column: Scatter Plot */}
                                <div className="w-full lg:w-2/3 h-[350px]">
                                    {item.points && item.points.length > 0 ? (
                                        <ResponsiveContainer width="100%" height="100%">
                                            <ScatterChart
                                                margin={{
                                                    top: 20,
                                                    right: 20,
                                                    bottom: 20,
                                                    left: 20,
                                                }}
                                            >
                                                <CartesianGrid />
                                                <XAxis type="number" dataKey="x" name="Score">
                                                    <Label value={xAxisLabel} offset={-10} position="insideBottom" />
                                                </XAxis>
                                                <YAxis type="number" dataKey="y" name={yAxisLabel}>
                                                    <Label value={yAxisLabel} angle={-90} position="insideLeft" />
                                                </YAxis>
                                                <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                                                <Scatter name="Students" data={item.points} fill="hsl(var(--primary))" />
                                            </ScatterChart>
                                        </ResponsiveContainer>
                                    ) : (
                                        <div className="flex h-full items-center justify-center text-muted-foreground border rounded-md bg-muted/10">
                                            No data points available for plot
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

export default ScoreVsRatingAnalysis;
