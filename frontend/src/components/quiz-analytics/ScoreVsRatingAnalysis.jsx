import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Label } from 'recharts';

const ScoreVsRatingAnalysis = ({ data, title, description, yAxisLabel = "Rating" }) => {
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
                        {description || "Analysis of how student ratings correlate with their graded scores per criterion."}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Criterion</TableHead>
                                <TableHead>Sample Size</TableHead>
                                <TableHead>Pearson r</TableHead>
                                <TableHead>P-Value (Pearson)</TableHead>
                                <TableHead>Spearman rho</TableHead>
                                <TableHead>P-Value (Spearman)</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {score_correlation.map((item, index) => (
                                <TableRow key={index}>
                                    <TableCell className="font-medium">{item.name}</TableCell>
                                    <TableCell>{item.count}</TableCell>
                                    <TableCell className={Math.abs(item.pearson_r) > 0.5 ? "font-bold text-primary" : ""}>
                                        {item.pearson_r !== null ? item.pearson_r : '-'}
                                    </TableCell>
                                    <TableCell>
                                        {item.pearson_p !== null ? (
                                            <span className={item.pearson_p < 0.05 ? "text-green-600 font-bold" : ""}>
                                                {item.pearson_p}{item.pearson_p < 0.05 && "*"}
                                            </span>
                                        ) : '-'}
                                    </TableCell>
                                    <TableCell className={Math.abs(item.spearman_rho) > 0.5 ? "font-bold text-primary" : ""}>
                                        {item.spearman_rho !== null ? item.spearman_rho : '-'}
                                    </TableCell>
                                    <TableCell>
                                        {item.spearman_p !== null ? (
                                            <span className={item.spearman_p < 0.05 ? "text-green-600 font-bold" : ""}>
                                                {item.spearman_p}{item.spearman_p < 0.05 && "*"}
                                            </span>
                                        ) : '-'}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {score_correlation.map((item, index) => (
                    <Card key={index} className="h-[400px] flex flex-col">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">{item.name}</CardTitle>
                        </CardHeader>
                        <CardContent className="flex-1 min-h-0">
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
                                            <Label value="Grade Score" offset={-10} position="insideBottom" />
                                        </XAxis>
                                        <YAxis type="number" dataKey="y" name={yAxisLabel}>
                                            <Label value={yAxisLabel} angle={-90} position="insideLeft" />
                                        </YAxis>
                                        <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                                        <Scatter name="Students" data={item.points} fill="hsl(var(--primary))" />
                                    </ScatterChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="flex h-full items-center justify-center text-muted-foreground">
                                    No data points
                                </div>
                            )}
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
};

export default ScoreVsRatingAnalysis;
