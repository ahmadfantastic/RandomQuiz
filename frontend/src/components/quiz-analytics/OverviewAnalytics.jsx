import React from 'react';
import AnalyticsSummary from './AnalyticsSummary';
import TimeDistributionChart from './TimeDistributionChart';

const OverviewAnalytics = ({ data }) => {
    if (!data) return null;

    return (
        <div className="space-y-8">
            <AnalyticsSummary
                completionStats={{
                    total_attempts: data.total_attempts,
                    completed_count: data.total_attempts,
                    completion_rate: data.completion_rate,
                    avg_score: data.avg_score,
                    min_score: data.min_score,
                    max_score: data.max_score
                }}
                timeStats={data.time_distribution}
                word_count_stats={data.word_count_stats}
            />
            <TimeDistributionChart timeStats={data.time_distribution} />
        </div>
    );
};

export default OverviewAnalytics;
