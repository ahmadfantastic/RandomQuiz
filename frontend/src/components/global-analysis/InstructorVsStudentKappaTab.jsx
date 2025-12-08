import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import InterRaterAgreement from '@/components/quiz-analytics/InterRaterAgreement';

const InstructorVsStudentKappaTab = ({ data }) => {
    return (
        <div className="space-y-8">
            <Card>
                <CardHeader>
                    <CardTitle>Instructors vs Students Agreement (All Quizzes)</CardTitle>
                    <CardDescription>
                        Pooled agreement analysis between Student and Instructor ratings across all quizzes.
                        Aggregated using weighted kappa per criterion.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <InterRaterAgreement data={data.global_quiz_agreement} />
                </CardContent>
            </Card>
        </div>
    );
};

export default InstructorVsStudentKappaTab;
