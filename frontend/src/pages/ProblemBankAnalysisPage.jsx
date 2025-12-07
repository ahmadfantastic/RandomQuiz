import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ChevronLeft, Loader2, Printer } from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import api from '@/lib/api';

const ProblemBankAnalysisPage = () => {
    const { bankId } = useParams();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);
    const [bank, setBank] = useState(null);
    const [allBanks, setAllBanks] = useState([]);
    const navigate = useNavigate();

    // Consistent rounding helper
    const roundToTwo = (num) => {
        if (num === undefined || num === null) return '-';
        return (Math.round((num + Number.EPSILON) * 100) / 100).toFixed(2);
    };


    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const [analysisRes, bankRes, allBanksRes] = await Promise.all([
                    api.get(`/api/problem-banks/${bankId}/analysis/`),
                    api.get(`/api/problem-banks/${bankId}/`),
                    api.get('/api/problem-banks/')
                ]);
                setData(analysisRes.data);
                setBank(bankRes.data);
                setAllBanks(allBanksRes.data);
            } catch (err) {
                setError('Failed to load analysis data.');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        if (bankId) {
            fetchData();
        }
    }, [bankId]);

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

    const { instructors, inter_rater } = data;

    return (
        <AppShell>
            <div className="space-y-8 pb-12">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" to={`/problem-banks`} className="print:hidden">
                            <ChevronLeft className="h-5 w-5" />
                        </Button>
                        <div>
                            <h1 className="text-2xl font-bold tracking-tight">Analysis: {bank.name}</h1>
                            <p className="text-muted-foreground">
                                Detailed rating analysis and inter-rater reliability
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
                        <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Switch Bank:</span>
                        <select
                            className="h-10 w-[200px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                            value={bankId}
                            onChange={(e) => navigate(`/problem-banks/${e.target.value}/analysis`)}
                        >
                            {allBanks.map(b => (
                                <option key={b.id} value={b.id}>
                                    {b.name}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                <Tabs defaultValue={instructors[0]?.id?.toString()} className="space-y-4">
                    <TabsList>
                        {instructors.map(inst => (
                            <TabsTrigger key={inst.id} value={inst.id.toString()}>
                                {inst.name}
                            </TabsTrigger>
                        ))}
                        {inter_rater?.pairwise?.length > 0 && (
                            <TabsTrigger value="inter_rater">Inter-Rater Reliability</TabsTrigger>
                        )}
                    </TabsList>

                    {instructors.map(inst => (
                        <TabsContent key={inst.id} value={inst.id.toString()} className="space-y-6">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Problem Ratings</CardTitle>
                                    <CardDescription>Average ratings per problem for {inst.name}</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="rounded-md border">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Order</TableHead>
                                                    <TableHead>Problem</TableHead>
                                                    <TableHead>Group</TableHead>
                                                    {/* Dynamically add criteria headers based on first rating or rubric? 
                                                        We don't have rubric here easily, but we can infer from values keys 
                                                        or pass rubric in API response. For now, let's use keys from first rating.
                                                    */}
                                                    {/* Use rubric criteria for headers if available, otherwise fallback */
                                                        (data.rubric?.criteria || (inst.ratings.length > 0 ? Object.keys(inst.ratings[0].values).map(cid => ({ id: cid })) : [])).map(c => (
                                                            <TableHead key={c.id}>{c.id}</TableHead>
                                                        ))}
                                                    <TableHead className="font-bold">Weighted Score</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {inst.ratings.map((rating) => (
                                                    <TableRow key={rating.problem_id}>
                                                        <TableCell>{rating.order}</TableCell>
                                                        <TableCell className="font-medium">{rating.label}</TableCell>
                                                        <TableCell>{rating.group || '-'}</TableCell>
                                                        {/* Use rubric criteria for cell order */
                                                            (data.rubric?.criteria || Object.keys(rating.values).map(cid => ({ id: cid }))).map(c => (
                                                                <TableCell key={c.id}>{rating.values[c.id] !== undefined ? rating.values[c.id] : '-'}</TableCell>
                                                            ))}
                                                        <TableCell className="font-bold">
                                                            {rating.weighted_score !== undefined && rating.weighted_score !== null
                                                                ? roundToTwo(rating.weighted_score)
                                                                : '-'}
                                                        </TableCell>


                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </div>
                                </CardContent>
                            </Card>

                            {inst.group_comparisons.length > 0 && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Group Comparisons (t-test)</CardTitle>
                                        <CardDescription>Statistical comparison of ratings between problem groups</CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="rounded-md border">
                                            <Table>
                                                <TableHeader>
                                                    <TableRow>
                                                        <TableHead>Criteria</TableHead>
                                                        <TableHead>Group 1</TableHead>
                                                        <TableHead>Group 2</TableHead>
                                                        <TableHead>Mean 1</TableHead>
                                                        <TableHead>Mean 2</TableHead>
                                                        <TableHead>t-statistic</TableHead>
                                                        <TableHead>p-value</TableHead>
                                                    </TableRow>
                                                </TableHeader>
                                                <TableBody>
                                                    {inst.group_comparisons.map((comp, idx) => (
                                                        <TableRow key={idx}>
                                                            <TableCell>{comp.criteria_id}</TableCell>
                                                            <TableCell>{comp.group1}</TableCell>
                                                            <TableCell>{comp.group2}</TableCell>
                                                            <TableCell>{roundToTwo(comp.mean1)}</TableCell>
                                                            <TableCell>{roundToTwo(comp.mean2)}</TableCell>
                                                            <TableCell>{comp.t_stat?.toFixed(3) || '-'}</TableCell>

                                                            <TableCell className={comp.p_value < 0.05 ? "font-bold text-green-600" : ""}>
                                                                {comp.p_value?.toFixed(4) || '-'}
                                                            </TableCell>
                                                        </TableRow>
                                                    ))}
                                                </TableBody>
                                            </Table>
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </TabsContent>
                    ))}

                    <TabsContent value="inter_rater" className="space-y-6">
                        <Card>
                            <CardHeader>
                                <CardTitle>Inter-Rater Reliability (Cohen's Kappa)</CardTitle>
                                <CardDescription>Pairwise agreement between instructors</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="rounded-md border">
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Instructor 1</TableHead>
                                                <TableHead>Instructor 2</TableHead>
                                                <TableHead>Criteria</TableHead>
                                                <TableHead>N (Common Problems)</TableHead>
                                                <TableHead>Kappa</TableHead>
                                                <TableHead>Interpretation</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {inter_rater?.pairwise?.map((k, idx) => {
                                                let interpretation = 'Poor';
                                                if (k.kappa > 0.8) interpretation = 'Almost Perfect';
                                                else if (k.kappa > 0.6) interpretation = 'Substantial';
                                                else if (k.kappa > 0.4) interpretation = 'Moderate';
                                                else if (k.kappa > 0.2) interpretation = 'Fair';
                                                else if (k.kappa > 0) interpretation = 'Slight';

                                                const isOverall = k.criteria_id === 'Overall';
                                                return (
                                                    <TableRow key={idx} className={isOverall ? "bg-muted/50 font-bold" : ""}>
                                                        <TableCell>{k.instructor1}</TableCell>
                                                        <TableCell>{k.instructor2}</TableCell>
                                                        <TableCell>{k.criteria_id}</TableCell>
                                                        <TableCell>{k.n}</TableCell>
                                                        <TableCell>{k.kappa.toFixed(3)}</TableCell>
                                                        <TableCell>{interpretation}</TableCell>
                                                    </TableRow>
                                                );
                                            })}
                                        </TableBody>
                                    </Table>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            </div>
        </AppShell >
    );
};

export default ProblemBankAnalysisPage;
