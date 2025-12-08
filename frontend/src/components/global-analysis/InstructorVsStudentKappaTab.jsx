import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import InterRaterAgreement from '@/components/quiz-analytics/InterRaterAgreement';

const InstructorVsStudentKappaTab = ({ data }) => {
    return (
        <div className="space-y-8">
            <Card>
                <CardHeader>
                    <CardTitle>Instructor vs. Student Agreement (Kappa)</CardTitle>
                    <CardDescription>
                        Analysis of agreement between instructor and student ratings using aggregated weighted kappa
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
