import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronLeft, Loader2, Printer } from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import InstructorsRatingsTab from '@/components/global-analysis/InstructorsRatingsTab';
import StudentRatingTab from '@/components/global-analysis/StudentRatingTab';
import InstructorVsStudentKappaTab from '@/components/global-analysis/InstructorVsStudentKappaTab';
import InstructorVsStudentTTestTab from '@/components/global-analysis/InstructorVsStudentTTestTab';
import StudentScoreTab from '@/components/global-analysis/StudentScoreTab';
import api from '@/lib/api';

const GlobalAnalysisPage = () => {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);
    const [quizzes, setQuizzes] = useState([]);
    const navigate = useNavigate();

    // Consistent rounding helper: 0.935 -> 0.94
    const roundToTwo = (num) => {
        if (num === undefined || num === null) return '-';
        return (Math.round((num + Number.EPSILON) * 100) / 100).toFixed(2);
    };


    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const [globalRes, quizzesRes] = await Promise.all([
                    api.get('/api/problem-banks/analysis/global/'),
                    api.get('/api/quizzes/')
                ]);
                setData(globalRes.data);
                setQuizzes(quizzesRes.data);
            } catch (err) {
                setError('Failed to load global analysis data.');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

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
                    <Button variant="link" className="mt-4" to={`/problem-banks`}>
                        Back to Problem Banks
                    </Button>
                </div>
            </AppShell>
        );
    }

    const { banks, anova, problem_groups } = data;


    // Collect all unique criteria IDs from banks to build table headers
    const allCriteria = new Set();
    banks.forEach(bank => {
        if (bank.means) {
            Object.keys(bank.means).forEach(cid => {
                if (cid !== 'weighted_score') {
                    allCriteria.add(cid);
                }
            });
        }
    });
    const criteriaList = data.criteria_order || Array.from(allCriteria).sort();

    return (
        <AppShell>
            <div className="space-y-8 pb-12">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Global Analysis</h1>
                        <p className="text-muted-foreground">
                            Comparison of ratings across all problem banks
                        </p>
                    </div>
                    <div className="flex items-center gap-4">
                        <Button variant="outline" size="sm" onClick={() => window.print()} className="print:hidden">
                            <Printer className="mr-2 h-4 w-4" />
                            Print
                        </Button>
                        <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Bank:</span>
                            <select
                                className="h-9 w-[180px] rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                onChange={(e) => {
                                    if (e.target.value) {
                                        navigate(`/problem-banks/${e.target.value}/analysis`);
                                    }
                                }}
                                defaultValue=""
                            >
                                <option value="" disabled>Analyze Bank...</option>
                                {banks.map(b => (
                                    <option key={b.id} value={b.id}>{b.name}</option>
                                ))}
                            </select>
                        </div>

                        <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Quiz:</span>
                            <select
                                className="h-9 w-[180px] rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                onChange={(e) => {
                                    if (e.target.value) {
                                        navigate(`/quizzes/${e.target.value}/analytics`);
                                    }
                                }}
                                defaultValue=""
                            >
                                <option value="" disabled>Analyze Quiz...</option>
                                {quizzes.map(q => (
                                    <option key={q.id} value={q.id}>{q.title}</option>
                                ))}
                            </select>
                        </div>
                    </div>
                </div>

                <Tabs defaultValue="instructors-ratings" className="w-full">
                    <TabsList className="grid w-full grid-cols-6 mb-8 h-auto flex-wrap">
                        <TabsTrigger value="instructors-ratings">Instructors Ratings</TabsTrigger>
                        <TabsTrigger value="student-rating">Student Rating</TabsTrigger>
                        <TabsTrigger value="instructor-vs-student-kappa">Instructor vs Student Kappa</TabsTrigger>
                        <TabsTrigger value="instructor-vs-student-t-test">Instructor vs Student T-Test</TabsTrigger>
                        <TabsTrigger value="student-score">Student Score</TabsTrigger>
                    </TabsList>

                    <TabsContent value="instructors-ratings" className="space-y-8">
                        <InstructorsRatingsTab
                            data={data}
                            roundToTwo={roundToTwo}
                            problem_groups={problem_groups}
                            criteriaList={criteriaList}
                            banks={banks}
                            anova={anova}
                        />
                    </TabsContent>

                    <TabsContent value="student-rating" className="space-y-8">
                        <StudentRatingTab data={data} roundToTwo={roundToTwo} />
                    </TabsContent>

                    <TabsContent value="instructor-vs-student-kappa" className="space-y-8">
                        <InstructorVsStudentKappaTab data={data} />
                    </TabsContent>

                    <TabsContent value="instructor-vs-student-t-test" className="space-y-8">
                        <InstructorVsStudentTTestTab data={data} />
                    </TabsContent>

                    <TabsContent value="student-score" className="space-y-8">
                        <StudentScoreTab data={data} roundToTwo={roundToTwo} />
                    </TabsContent>
                </Tabs>
            </div>
        </AppShell >
    );
};

export default GlobalAnalysisPage;
