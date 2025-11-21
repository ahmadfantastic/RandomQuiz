import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, CheckCircle, Clock } from 'lucide-react';

const AnalyticsSummary = ({ completionStats, timeStats }) => {
    const { total_attempts, completed_count, completion_rate } = completionStats;
    const { mean, median } = timeStats;

    const formatTime = (minutes) => {
        if (!minutes) return 'N/A';
        const mins = Math.floor(minutes);
        const secs = Math.round((minutes - mins) * 60);
        return `${mins}m ${secs}s`;
    };

    return (
        <div className="grid gap-4 md:grid-cols-3">
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Completion Rate</CardTitle>
                    <CheckCircle className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">{Math.round(completion_rate)}%</div>
                    <p className="text-xs text-muted-foreground">
                        {completed_count} of {total_attempts} students completed
                    </p>
                </CardContent>
            </Card>
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Average Time</CardTitle>
                    <Clock className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">{formatTime(mean)}</div>
                    <p className="text-xs text-muted-foreground">
                        Median: {formatTime(median)}
                    </p>
                </CardContent>
            </Card>
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Total Attempts</CardTitle>
                    <Users className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">{total_attempts}</div>
                    <p className="text-xs text-muted-foreground">
                        Students who started the quiz
                    </p>
                </CardContent>
            </Card>
        </div>
    );
};

export default AnalyticsSummary;
