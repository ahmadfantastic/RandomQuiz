import React from 'react';
import CorrelationAnalysis from '@/components/quiz-analytics/CorrelationAnalysis';

const TimeCorrelationTab = ({ data }) => {
    return (
        <div>
            <div className="mb-6">
                <h3 className="text-lg font-medium">Time Correlation Analysis</h3>
                <p className="text-muted-foreground">
                    Analysis of how time taken correlates with ratings and word counts globally.
                </p>
            </div>

            <CorrelationAnalysis
                data={{ score_correlation: data.time_vs_rating_correlation }}
                title="Global Time vs Rating Correlation Analysis"
                description="Global analysis of how quiz completion time correlates with ratings (per criterion and weighted)."
                xAxisLabel="Time (minutes)"
                yAxisLabel="Rating"
            />

            {data.word_count_vs_time_correlation && data.word_count_vs_time_correlation.length > 0 && (
                <div className="mt-12">
                    <CorrelationAnalysis
                        data={{ score_correlation: data.word_count_vs_time_correlation }}
                        title="Global Time vs Word Count Correlation Analysis"
                        description="Global analysis of how time taken correlates with total word count across all quizzes."
                        xAxisLabel="Time (minutes)"
                        yAxisLabel="Word Count"
                    />
                </div>
            )}
        </div>
    );
};

export default TimeCorrelationTab;
