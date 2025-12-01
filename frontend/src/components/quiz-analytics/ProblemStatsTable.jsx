import React from 'react';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronRight } from 'lucide-react';

const ProblemStatsTable = ({ problems, onProblemClick }) => {
    if (!problems || problems.length === 0) {
        return <div className="text-muted-foreground text-sm">No problem data available.</div>;
    }

    return (
        <div className="rounded-md border">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>Problem</TableHead>
                        <TableHead className="text-right">Count</TableHead>
                        <TableHead className="text-right">Avg Score</TableHead>
                        <TableHead className="text-right">Avg Time</TableHead>
                        <TableHead className="text-right">Avg Words</TableHead>
                        <TableHead className="w-[50px]"></TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {problems.map((problem) => (
                        <TableRow
                            key={problem.label}
                            className="cursor-pointer hover:bg-muted/50"
                            onClick={() => onProblemClick(problem)}
                        >
                            <TableCell className="font-medium">
                                {problem.label}
                            </TableCell>
                            <TableCell className="text-right">
                                <Badge variant="secondary">{problem.count}</Badge>
                            </TableCell>
                            <TableCell className="text-right">
                                {problem.avg_score.toFixed(1)}
                            </TableCell>
                            <TableCell className="text-right">
                                {problem.avg_time.toFixed(1)} min
                            </TableCell>
                            <TableCell className="text-right">
                                {Math.round(problem.avg_words)}
                            </TableCell>
                            <TableCell>
                                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </div>
    );
};

export default ProblemStatsTable;
