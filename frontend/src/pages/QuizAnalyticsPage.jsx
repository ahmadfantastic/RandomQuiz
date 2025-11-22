import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ChevronLeft, Loader2 } from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import api from '@/lib/api';
import AnalyticsSummary from '@/components/quiz-analytics/AnalyticsSummary';
import TimeDistributionChart from '@/components/quiz-analytics/TimeDistributionChart';
import SlotAnalytics from '@/components/quiz-analytics/SlotAnalytics';


const QuizAnalyticsPage = () => {
    const { quizId } = useParams();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);
    const [quizTitle, setQuizTitle] = useState('');

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const [analyticsRes, quizRes] = await Promise.all([
                    api.get(`/api/quizzes/${quizId}/analytics/`),
                    api.get(`/api/quizzes/${quizId}/`)
                ]);
                setData(analyticsRes.data);
                setQuizTitle(quizRes.data.title);
            } catch (err) {
                setError('Failed to load analytics data.');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        if (quizId) {
            fetchData();
        }
    }, [quizId]);

    if (loading) {
        return (
            <AppShell>
                <div className="flex h-[50vh] items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
            </AppShell>
        );
    }

    if (error) {
        return (
            <AppShell>
                <div className="p-8 text-center text-destructive">
                    <p>{error}</p>
                    <Button variant="link" className="mt-4" to={`/quizzes/${quizId}/edit`}>
                        Back to Quiz
                    </Button>
                </div>
            </AppShell>
        );
    }

    return (
        <AppShell>
            <div className="space-y-8 pb-12">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" to={`/quizzes/${quizId}/edit`}>
                        <ChevronLeft className="h-5 w-5" />
                    </Button>
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Analytics: {quizTitle}</h1>
                        <p className="text-muted-foreground">
                            Detailed insights into student performance and engagement
                        </p>
                    </div>
                </div>

                <AnalyticsSummary
                    completionStats={{
                        total_attempts: data.total_attempts,
                        completed_count: data.total_attempts, // All attempts in our query are completed
                        completion_rate: data.completion_rate
                    }}
                    timeStats={data.time_distribution}
                    word_count_stats={data.word_count_stats}
                />

                <div className="grid gap-8">
                    <TimeDistributionChart timeStats={data.time_distribution} />
                </div>

                <div>
                    <h2 className="text-xl font-semibold mb-4">Slot Analysis</h2>
                    <SlotAnalytics slots={data.slots} />
                </div>
            </div>
        </AppShell>
    );
};

export default QuizAnalyticsPage;
