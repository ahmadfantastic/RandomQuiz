import React from 'react';
import ScoreVsRatingAnalysis from '@/components/quiz-analytics/ScoreVsRatingAnalysis';

const StudentScoreTab = ({ data }) => {
    return (
        <div className="space-y-8">
            {data.score_correlation && (
                <ScoreVsRatingAnalysis data={data} />
            )}

            {data.time_correlation && (
                <ScoreVsRatingAnalysis
                    data={{ score_correlation: data.time_correlation }}
                    title="Score vs Time Correlation Analysis"
                    description="Analysis of how quiz completion time correlates with student graded scores."
                    yAxisLabel="Time (minutes)"
                />
            )}

            {data.word_count_correlation && (
                <ScoreVsRatingAnalysis
                    data={{ score_correlation: data.word_count_correlation }}
                    title="Score vs Word Count Correlation Analysis"
                    description="Analysis of how total word count of text answers correlates with student graded scores."
                    yAxisLabel="Word Count"
                />
            )}
        </div>
    );
};

export default StudentScoreTab;
