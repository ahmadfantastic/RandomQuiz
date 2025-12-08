import React from 'react';
import StudentInstructorComparison from '@/components/quiz-analytics/StudentInstructorComparison';

const InstructorVsStudentTTestTab = ({ data }) => {
    return (
        <div className="space-y-8">
            {data.global_comparison && (
                <div className="space-y-4">
                    <h2 className="text-xl font-semibold tracking-tight">Global Student vs Instructor Comparison</h2>
                    <StudentInstructorComparison data={data.global_comparison} />
                </div>
            )}
        </div>
    );
};

export default InstructorVsStudentTTestTab;
