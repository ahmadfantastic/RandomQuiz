import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { interpolateLab } from 'd3-interpolate';

const CorrelationMatrix = ({ data }) => {
    if (!data || !data.matrix || !data.criteria) return null;

    const { criteria, matrix } = data;

    // Helper for cell color
    const getCellColor = (r) => {
        if (r === null || r === undefined) return 'bg-muted/10';

        // Halo Effect analysis:
        // r > 0.5 -> Solid Red (Bad)
        // r < 0 -> Green (Good/Divergent)

        if (r > 0.5) {
            return `rgba(239, 68, 68, 0.5)`; // Tailwind red-500, flat opacity
        } else if (r > 0) {
            return 'transparent'; // Or very faint if preferred, but user said "just show one red"
        } else {
            const intensity = Math.max(0.1, Math.abs(r));
            return `rgba(34, 197, 94, ${intensity * 0.3})`; // Tailwind green-500 (Inverse)
        }
    };

    const getTextColor = (r) => {
        if (r === null || r === undefined) return 'text-muted-foreground';
        if (Math.abs(r) > 0.5) return 'font-bold text-foreground';
        return 'text-foreground';
    };

    return (
        <Card className="mt-8">
            <CardHeader>
                <CardTitle>Inter-Criterion Correlation Matrix</CardTitle>
                <CardDescription>
                    Pairwise correlation between criteria ratings. Correlation &gt; 0.5 (Red) suggests potential Halo Effect.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="overflow-x-auto">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-[150px]">Criterion</TableHead>
                                {criteria.map((c, i) => (
                                    <TableHead key={i} className="text-center min-w-[100px]">{c}</TableHead>
                                ))}
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {criteria.map((rowName, i) => (
                                <TableRow key={i}>
                                    <TableCell className="font-medium bg-muted/50">{rowName}</TableCell>
                                    {matrix[i].map((cell, j) => {
                                        const r = cell ? cell.r : null;
                                        const isDiag = i === j;

                                        return (
                                            <TableCell
                                                key={j}
                                                className="text-center border p-2 h-16"
                                                style={{ backgroundColor: isDiag ? 'transparent' : getCellColor(r) }}
                                            >
                                                {cell ? (
                                                    <div className="flex flex-col items-center justify-center text-xs">
                                                        <span className={`text-sm ${getTextColor(r)}`}>
                                                            {r.toFixed(2)}
                                                        </span>
                                                        {!isDiag && cell.n && (
                                                            <span className="text-[9px] text-muted-foreground">
                                                                n={cell.n}
                                                            </span>
                                                        )}
                                                    </div>
                                                ) : (
                                                    <span className="text-muted-foreground">-</span>
                                                )}
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
    );
};

export default CorrelationMatrix;
