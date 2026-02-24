import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import InterRaterAgreement from '@/components/quiz-analytics/InterRaterAgreement';

const InstructorVsStudentKappaTab = ({ data, instructorAggMethod, studentAggMethod, onAggregationChange }) => {
    return (
        <div className="space-y-8">
            <div className="flex flex-wrap items-center gap-6 rounded-lg border bg-card text-card-foreground shadow-sm p-4">
                <div className="flex items-center gap-3">
                    <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Instructor Aggregation:</span>
                    <select
                        className="h-9 w-[180px] rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                        value={instructorAggMethod || 'average_nearest'}
                        onChange={(e) => onAggregationChange?.('instructor', e.target.value)}
                    >
                        <option value="average_nearest">Average (Nearest)</option>
                        <option value="average_floor">Average (Floor)</option>
                        <option value="average_ceil">Average (Ceil)</option>
                        <option value="popular_vote">Popular Vote</option>
                    </select>
                </div>
                <div className="flex items-center gap-3">
                    <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Student Aggregation:</span>
                    <select
                        className="h-9 w-[180px] rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                        value={studentAggMethod || 'average_nearest'}
                        onChange={(e) => onAggregationChange?.('student', e.target.value)}
                    >
                        <option value="average_nearest">Average (Nearest)</option>
                        <option value="average_floor">Average (Floor)</option>
                        <option value="average_ceil">Average (Ceil)</option>
                        <option value="popular_vote">Popular Vote</option>
                    </select>
                </div>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Instructor vs. Student Agreement (Kappa)</CardTitle>
                    <CardDescription>
                        Analysis of agreement between instructor and student ratings using aggregated weighted kappa
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <InterRaterAgreement data={data?.global_quiz_agreement} />
                </CardContent>
            </Card>
        </div>
    );
};

export default InstructorVsStudentKappaTab;
