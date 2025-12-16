import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Printer } from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import InstructorsRatingsTab from '@/components/global-analysis/InstructorsRatingsTab';
import StudentRatingTab from '@/components/global-analysis/StudentRatingTab';
import InstructorVsStudentKappaTab from '@/components/global-analysis/InstructorVsStudentKappaTab';
import InstructorVsStudentTTestTab from '@/components/global-analysis/InstructorVsStudentTTestTab';
import StudentScoreTab from '@/components/global-analysis/StudentScoreTab';
import TimeCorrelationTab from '@/components/global-analysis/TimeCorrelationTab';
import GlobalInteractionsTab from '@/components/global-analysis/GlobalInteractionsTab';
import api from '@/lib/api';

const GlobalAnalysisPage = () => {
    const [activeTab, setActiveTab] = useState('instructors-ratings');

    // Independent State for each section
    const [quizzes, setQuizzes] = useState([]);

    const [instructorData, setInstructorData] = useState(null);
    const [studentData, setStudentData] = useState(null);
    const [agreementData, setAgreementData] = useState(null);
    const [correlationData, setCorrelationData] = useState(null);

    const [loading, setLoading] = useState({
        quizzes: true,
        instructor: false,
        student: false,
        agreement: false,
        correlation: false
    });

    const [error, setError] = useState(null);
    const navigate = useNavigate();

    // Initial Load: Quizzes only
    useEffect(() => {
        const fetchQuizzes = async () => {
            try {
                const res = await api.get('/api/quizzes/');
                setQuizzes(res.data);
                setLoading(prev => ({ ...prev, quizzes: false }));
            } catch (err) {
                console.error("Failed to load quizzes", err);
                setError("Failed to load quizzes.");
                setLoading(prev => ({ ...prev, quizzes: false }));
            }
        };
        fetchQuizzes();
    }, []);


    // Lazy Load Handlers
    const loadInstructorData = async () => {
        if (instructorData) return;
        setLoading(prev => ({ ...prev, instructor: true }));
        try {
            const res = await api.get('/api/problem-banks/analysis/global/instructor/');
            setInstructorData(res.data);
        } catch (err) {
            console.error(err);
            setError("Failed to load instructor data.");
        } finally {
            setLoading(prev => ({ ...prev, instructor: false }));
        }
    };

    const loadStudentData = async () => {
        if (studentData) return;
        setLoading(prev => ({ ...prev, student: true }));
        try {
            const res = await api.get('/api/problem-banks/analysis/global/student/');
            setStudentData(res.data);
        } catch (err) {
            console.error(err);
            setError("Failed to load student data.");
        } finally {
            setLoading(prev => ({ ...prev, student: false }));
        }
    };

    const loadCorrelationData = async () => {
        if (correlationData) return;
        setLoading(prev => ({ ...prev, correlation: true }));
        try {
            const res = await api.get('/api/problem-banks/analysis/global/correlation/');
            setCorrelationData(res.data);
        } catch (err) {
            console.error(err);
            setError("Failed to load correlation analysis.");
        } finally {
            setLoading(prev => ({ ...prev, correlation: false }));
        }
    };

    const loadAgreementData = async () => {
        if (agreementData) return;
        setLoading(prev => ({ ...prev, agreement: true }));
        try {
            const res = await api.get('/api/problem-banks/analysis/global/agreement/');
            setAgreementData(res.data);
        } catch (err) {
            console.error(err);
            setError("Failed to load agreement data.");
        } finally {
            setLoading(prev => ({ ...prev, agreement: false }));
        }
    };


    // Effect to trigger loads based on active tab
    useEffect(() => {
        if (activeTab === 'instructors-ratings') {
            loadInstructorData();
        } else if (activeTab === 'student-rating') {
            loadStudentData();
            loadCorrelationData(); // Needed for matrix
        } else if (activeTab === 'instructor-vs-student-kappa') {
            loadAgreementData();
        } else if (activeTab === 'instructor-vs-student-t-test') {
            // T-Test tab uses data from Agrement Endpoint (global_comparison)
            loadAgreementData();
        } else if (activeTab === 'student-score') {
            loadStudentData();
            loadCorrelationData();
        } else if (activeTab === 'time-correlation') {
            loadCorrelationData();
        } else if (activeTab === 'global-interactions') {
            // Handled internally by the tab component, but we keep tab state
        }
    }, [activeTab]);


    const handleTabChange = (value) => {
        setActiveTab(value);
    };

    if (loading.quizzes) {
        return (
            <AppShell>
                <div className="flex h-[50vh] items-center justify-center">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
                </div>
            </AppShell>
        );
    }

    // Instructor Data Helpers
    const problem_groups = instructorData?.problem_groups || [];
    const banks = instructorData?.banks || [];
    const anova = instructorData?.anova || [];
    const criteriaList = instructorData?.criteria_order || [];
    // roundToTwo is utility

    const roundToTwo = (num) => {
        if (num === undefined || num === null) return '-';
        return (Math.round((num + Number.EPSILON) * 100) / 100).toFixed(2);
    };

    return (
        <AppShell>
            <div className="space-y-8 pb-12">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight">Global Analysis</h1>
                        <p className="text-muted-foreground mt-2">
                            Comprehensive analysis across all problem banks and quizzes
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

                {error && (
                    <div className="rounded-md bg-destructive/15 p-4 text-destructive">
                        {error}
                    </div>
                )}

                <Tabs value={activeTab} className="w-full" onValueChange={handleTabChange}>
                    <TabsList className="grid w-full grid-cols-7 mb-8 h-auto flex-wrap">
                        <TabsTrigger value="instructors-ratings">Inst. Ratings</TabsTrigger>
                        <TabsTrigger value="student-rating">Stu. Rating</TabsTrigger>
                        <TabsTrigger value="instructor-vs-student-kappa">Inst. vs Stu. (Kappa)</TabsTrigger>
                        <TabsTrigger value="instructor-vs-student-t-test">Inst. vs Stu. (T-Test)</TabsTrigger>
                        <TabsTrigger value="student-score">Stu. Score</TabsTrigger>
                        <TabsTrigger value="time-correlation">Time Correl.</TabsTrigger>
                        <TabsTrigger value="global-interactions">Stu. Interactions</TabsTrigger>
                    </TabsList>

                    <TabsContent value="instructors-ratings" className="space-y-8">
                        {loading.instructor ? (
                            <div className="p-12 text-center text-muted-foreground">Loading instructor analysis...</div>
                        ) : (
                            <InstructorsRatingsTab
                                data={instructorData || {}}
                                roundToTwo={roundToTwo}
                                problem_groups={problem_groups}
                                criteriaList={criteriaList}
                                banks={banks}
                                anova={anova}
                            />
                        )}
                    </TabsContent>

                    <TabsContent value="student-rating" className="space-y-8">
                        {loading.student || loading.correlation ? (
                            <div className="p-12 text-center text-muted-foreground">Loading student analysis...</div>
                        ) : (
                            <StudentRatingTab
                                data={{
                                    ...(studentData || {}),
                                    inter_criterion_correlation: correlationData?.inter_criterion_correlation,
                                    factor_analysis: correlationData?.factor_analysis
                                }}
                                roundToTwo={roundToTwo}
                            />
                        )}
                    </TabsContent>

                    <TabsContent value="instructor-vs-student-kappa" className="space-y-8">
                        {loading.agreement ? (
                            <div className="p-12 text-center text-muted-foreground">Loading agreement analysis...</div>
                        ) : (
                            <InstructorVsStudentKappaTab
                                data={agreementData || {}}
                            />
                        )}
                    </TabsContent>

                    <TabsContent value="instructor-vs-student-t-test" className="space-y-8">
                        {loading.agreement ? (
                            <div className="p-12 text-center text-muted-foreground">Loading comparison analysis...</div>
                        ) : (
                            <InstructorVsStudentTTestTab
                                data={agreementData || {}}
                            />
                        )}
                    </TabsContent>

                    <TabsContent value="student-score" className="space-y-8">
                        {loading.student || loading.correlation ? (
                            <div className="p-12 text-center text-muted-foreground">Loading score analysis...</div>
                        ) : (
                            <StudentScoreTab
                                data={{
                                    ...(studentData || {}),
                                    ...(correlationData || {})
                                }}
                                roundToTwo={roundToTwo}
                            />
                        )}
                    </TabsContent>

                    <TabsContent value="time-correlation">
                        {loading.correlation ? (
                            <div className="p-12 text-center text-muted-foreground">Loading correlation analysis...</div>
                        ) : (
                            <TimeCorrelationTab
                                data={correlationData || {}}
                            />
                        )}
                    </TabsContent>

                    <TabsContent value="global-interactions">
                        <GlobalInteractionsTab />
                    </TabsContent>
                </Tabs>
            </div>
        </AppShell>
    );
};

export default GlobalAnalysisPage;
