import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ChevronLeft, Loader2, Printer } from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import api from '@/lib/api';
import OverviewAnalytics from '@/components/quiz-analytics/OverviewAnalytics';
import InteractionAnalytics from '@/components/quiz-analytics/InteractionAnalytics';
import SlotAnalytics from '@/components/quiz-analytics/SlotAnalytics';
import InterRaterAgreement from '@/components/quiz-analytics/InterRaterAgreement';
import StudentInstructorComparison from '@/components/quiz-analytics/StudentInstructorComparison';
import ScoreVsRatingAnalysis from '@/components/quiz-analytics/ScoreVsRatingAnalysis';

const AnalyticsTabContent = ({ endpoint, renderContent }) => {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);
    const { quizId } = useParams();

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const res = await api.get(endpoint);
                setData(res.data);
            } catch (err) {
                if (err.response && err.response.data && err.response.data.detail) {
                    setError(err.response.data.detail);
                } else {
                    setError('Failed to load data.');
                }
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
        return (
            <div className="p-4">
                <div className="text-destructive mb-2">{error}</div>
                {error.includes('mapping') && (
                    <Button variant="outline" asChild>
                        <Link to={`/quizzes/${quizId}/edit`}>Go to Rubric Settings</Link>
                    </Button>
                )}
            </div>
        );
    }

    return renderContent(data);
};

const QuizAnalyticsPage = () => {
    const { quizId } = useParams();
    const [searchParams, setSearchParams] = useSearchParams();
    const [loading, setLoading] = useState(true);
    const [quiz, setQuiz] = useState(null);
    const [slots, setSlots] = useState([]);
    const [allQuizzes, setAllQuizzes] = useState([]);
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

    // Determine active tab from URL parameters
    const getActiveTab = () => {
        const tab = searchParams.get('tab');
        const index = searchParams.get('index');

        if (tab === 'interaction') return 'interaction';
        if (tab === 'interaction') return 'interaction';
        if (tab === 'agreement') return 'agreement';
        if (tab === 'comparison') return 'comparison';
        if (tab === 'correlation') return 'correlation';

        if (tab === 'slot' && index !== null && slots.length > 0) {
            // Find slot by index (preserving order)
            // Assuming slots are already ordered by 'order' or as received from API
            // Ideally backend sends them ordered. If not, we might need to sort them first.
            // For now, assuming the array index matches the logical index we want to persist.
            const slotIndex = parseInt(index, 10);
            if (!isNaN(slotIndex) && slotIndex >= 0 && slotIndex < slots.length) {
                return `slot-${slots[slotIndex].id}`;
            }
        }

        // Default to overview or fall back if index invalid
        return 'overview';
    };

    const handleTabChange = (value) => {
        const newParams = new URLSearchParams(searchParams);

        if (value === 'overview') {
            newParams.set('tab', 'overview');
            newParams.delete('index');
        } else if (value === 'interaction') {
            newParams.set('tab', 'interaction');
            newParams.delete('index');
        } else if (value === 'agreement') {
            newParams.set('tab', 'agreement');
            newParams.delete('index');
        } else if (value === 'comparison') {
            newParams.set('tab', 'comparison');
            newParams.delete('index');
        } else if (value === 'correlation') {
            newParams.set('tab', 'correlation');
            newParams.delete('index');
        } else if (value.startsWith('slot-')) {
            const slotId = parseInt(value.replace('slot-', ''), 10);
            const slotIndex = slots.findIndex(s => s.id === slotId);
            if (slotIndex !== -1) {
                newParams.set('tab', 'slot');
                newParams.set('index', slotIndex.toString());
            }
        }

        setSearchParams(newParams);
    };

    const handleQuizSwitch = (newQuizId) => {
        // Construct the new URL preserving the current search params
        navigate({
            pathname: `/quizzes/${newQuizId}/analytics`,
            search: searchParams.toString()
        });
    };

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

    const activeTab = getActiveTab();

    return (
        <AppShell>
            <div className="space-y-8 pb-12">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" to={`/quizzes/${quizId}/edit`} className="print:hidden">
                            <ChevronLeft className="h-5 w-5" />
                        </Button>
                        <div>
                            <h1 className="text-2xl font-bold tracking-tight">Analytics: {quiz.title}</h1>
                            <p className="text-muted-foreground">
                                Detailed insights into student performance and engagement
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2 print:hidden">
                        <Button variant="outline" size="sm" onClick={() => window.print()}>
                            <Printer className="mr-2 h-4 w-4" />
                            Print
                        </Button>
                        <Button variant="outline" to="/analysis/global">
                            Global Analysis
                        </Button>
                        <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Switch Quiz:</span>
                        <select
                            className="h-10 w-[200px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                            value={quizId}
                            onChange={(e) => handleQuizSwitch(e.target.value)}
                        >
                            {allQuizzes.map(q => (
                                <option key={q.id} value={q.id}>
                                    {q.title}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
                    <div className="overflow-x-auto pb-2 print:hidden">
                        <TabsList className="w-full justify-start">
                            <TabsTrigger value="overview">Overview</TabsTrigger>
                            <TabsTrigger value="interaction">Interactions</TabsTrigger>
                            <TabsTrigger value="agreement">Agreement</TabsTrigger>
                            <TabsTrigger value="comparison">S vs I Comparison</TabsTrigger>
                            <TabsTrigger value="correlation">Score vs Rating</TabsTrigger>
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

                        <TabsContent value="agreement">
                            <AnalyticsTabContent
                                endpoint={`/api/quizzes/${quizId}/analytics/agreement/`}
                                renderContent={(data) => <InterRaterAgreement data={data} />}
                            />
                        </TabsContent>

                        <TabsContent value="comparison">
                            <AnalyticsTabContent
                                endpoint={`/api/quizzes/${quizId}/analytics/agreement/`}
                                renderContent={(data) => <StudentInstructorComparison data={data} />}
                            />
                        </TabsContent>

                        <TabsContent value="correlation">
                            <AnalyticsTabContent
                                endpoint={`/api/quizzes/${quizId}/analytics/agreement/`}
                                renderContent={(data) => (
                                    <>
                                        {data.score_correlation && (
                                            <ScoreVsRatingAnalysis data={data} />
                                        )}
                                        {data.time_correlation && data.time_correlation.length > 0 && (
                                            <div className="mt-8">
                                                <ScoreVsRatingAnalysis
                                                    data={{ score_correlation: data.time_correlation }}
                                                    title="Score vs Time Correlation Analysis"
                                                    description="Analysis of how quiz completion time correlates with student graded scores."
                                                    yAxisLabel="Time (minutes)"
                                                />
                                            </div>
                                        )}
                                        {data.word_count_correlation && data.word_count_correlation.length > 0 && (
                                            <div className="mt-8">
                                                <ScoreVsRatingAnalysis
                                                    data={{ score_correlation: data.word_count_correlation }}
                                                    title="Score vs Word Count Correlation Analysis"
                                                    description="Analysis of how total word count of text answers correlates with student graded scores."
                                                    yAxisLabel="Word Count"
                                                />
                                            </div>
                                        )}
                                    </>
                                )}
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
