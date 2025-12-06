import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, CheckCircle, Clock, AlignLeft, Activity } from 'lucide-react';

const AnalyticsSummary = ({ completionStats, timeStats, word_count_stats, cronbach_alpha }) => {
    const { total_attempts, completed_count, completion_rate } = completionStats;
    const { mean, median, min, max } = timeStats;

    const formatTime = (minutes) => {
        if (!minutes) return 'N/A';
        const mins = Math.floor(minutes);
        const secs = Math.round((minutes - mins) * 60);
        return `${mins}m ${secs}s`;
    };

    return (
        <div className="grid gap-4 md:grid-cols-4">
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Average Score</CardTitle>
                    <CheckCircle className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">{completionStats.avg_score ? completionStats.avg_score.toFixed(1) : '0.0'}</div>
                    <p className="text-xs text-muted-foreground">
                        Range: {completionStats.min_score !== undefined ? completionStats.min_score.toFixed(1) : '0'} - {completionStats.max_score !== undefined ? completionStats.max_score.toFixed(1) : '0'}
                    </p>
                </CardContent>
            </Card>
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Completion Rate</CardTitle>
                    <Users className="h-4 w-4 text-muted-foreground" />
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
                        Median: {formatTime(median)} (Range: {formatTime(min)}-{formatTime(max)})
                    </p>
                </CardContent>
            </Card>
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Average Word Count</CardTitle>
                    <AlignLeft className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">{Math.round(word_count_stats?.mean || 0)}</div>
                    <p className="text-xs text-muted-foreground">
                        Median: {Math.round(word_count_stats?.median || 0)} (Range: {Math.round(word_count_stats?.min || 0)}-{Math.round(word_count_stats?.max || 0)})
                    </p>
                </CardContent>
            </Card>
        </div>
    );
};

export default AnalyticsSummary;
