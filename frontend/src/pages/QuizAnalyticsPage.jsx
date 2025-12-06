import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ChevronLeft, Loader2 } from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import api from '@/lib/api';
import OverviewAnalytics from '@/components/quiz-analytics/OverviewAnalytics';
import InteractionAnalytics from '@/components/quiz-analytics/InteractionAnalytics';
import SlotAnalytics from '@/components/quiz-analytics/SlotAnalytics';

const AnalyticsTabContent = ({ endpoint, renderContent }) => {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const res = await api.get(endpoint);
                setData(res.data);
            } catch (err) {
                setError('Failed to load data.');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [endpoint]);

    if (loading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    if (error) {
        return <div className="text-destructive p-4">{error}</div>;
    }

    return renderContent(data);
};

const QuizAnalyticsPage = () => {
    const { quizId } = useParams();
    const [loading, setLoading] = useState(true);
    const [quiz, setQuiz] = useState(null);
    const [slots, setSlots] = useState([]);
    const [allQuizzes, setAllQuizzes] = useState([]);
    const [activeTab, setActiveTab] = useState('overview');
    const navigate = useNavigate();

    useEffect(() => {
        const fetchQuizInfo = async () => {
            try {
                setLoading(true);
                // Fetch quiz details to get title and slots structure
                const res = await api.get(`/api/quizzes/${quizId}/`);
                setQuiz(res.data);
                // Extract slots from quiz data
                if (res.data.slots) {
                    setSlots(res.data.slots);
                }

                // Fetch all quizzes for switcher
                const allRes = await api.get('/api/quizzes/');
                setAllQuizzes(allRes.data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        if (quizId) {
            fetchQuizInfo();
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

    if (!quiz) {
        return (
            <AppShell>
                <div className="p-8 text-center">
                    <p>Quiz not found.</p>
                    <Button variant="link" className="mt-4" to="/quizzes">
                        Back to Quizzes
                    </Button>
                </div>
            </AppShell>
        );
    }

    return (
        <AppShell>
            <div className="space-y-8 pb-12">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" to={`/quizzes/${quizId}/edit`}>
                            <ChevronLeft className="h-5 w-5" />
                        </Button>
                        <div>
                            <h1 className="text-2xl font-bold tracking-tight">Analytics: {quiz.title}</h1>
                            <p className="text-muted-foreground">
                                Detailed insights into student performance and engagement
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button variant="outline" to="/analysis/global">
                            Global Analysis
                        </Button>
                        <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Switch Quiz:</span>
                        <select
                            className="h-10 w-[200px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                            value={quizId}
                            onChange={(e) => navigate(`/quizzes/${e.target.value}/analytics`)}
                        >
                            {allQuizzes.map(q => (
                                <option key={q.id} value={q.id}>
                                    {q.title}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                    <div className="overflow-x-auto pb-2">
                        <TabsList className="w-full justify-start">
                            <TabsTrigger value="overview">Overview</TabsTrigger>
                            <TabsTrigger value="interaction">Interactions</TabsTrigger>
                            {slots.map(slot => (
                                <TabsTrigger key={slot.id} value={`slot-${slot.id}`}>
                                    {slot.label || `Slot ${slot.order}`}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                    </div>

                    <div className="mt-6">
                        <TabsContent value="overview">
                            <AnalyticsTabContent
                                endpoint={`/api/quizzes/${quizId}/analytics/overview/`}
                                renderContent={(data) => <OverviewAnalytics data={data} />}
                            />
                        </TabsContent>

                        <TabsContent value="interaction">
                            <AnalyticsTabContent
                                endpoint={`/api/quizzes/${quizId}/analytics/interactions/`}
                                renderContent={(data) => <InteractionAnalytics data={data} />}
                            />
                        </TabsContent>

                        {slots.map(slot => (
                            <TabsContent key={slot.id} value={`slot-${slot.id}`}>
                                <AnalyticsTabContent
                                    endpoint={`/api/quizzes/${quizId}/analytics/slots/${slot.id}/`}
                                    renderContent={(data) => <SlotAnalytics slot={data} />}
                                />
                            </TabsContent>
                        ))}
                    </div>
                </Tabs>
            </div>
        </AppShell>
    );
};

export default QuizAnalyticsPage;
