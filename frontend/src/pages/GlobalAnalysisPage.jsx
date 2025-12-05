import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, Loader2 } from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import api from '@/lib/api';

const GlobalAnalysisPage = () => {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const response = await api.get('/api/problem-banks/analysis/global/');
                setData(response.data);
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

    const { banks, anova } = data;

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
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" to={`/problem-banks`}>
                        <ChevronLeft className="h-5 w-5" />
                    </Button>
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Global Analysis</h1>
                        <p className="text-muted-foreground">
                            Comparison of ratings across all problem banks
                        </p>
                    </div>
                </div>

                <Card>
                    <CardHeader>
                        <CardTitle>Average Ratings by Bank</CardTitle>
                        <CardDescription>Mean ratings for each criterion per bank</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="rounded-md border">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Bank</TableHead>
                                        {criteriaList.map(cid => (
                                            <TableHead key={cid}>{cid}</TableHead>
                                        ))}
                                        <TableHead className="font-bold">Weighted Score</TableHead>
                                        <TableHead>Inter-Rater Reliability</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {banks.map(bank => (
                                        <TableRow key={bank.id}>
                                            <TableCell className="font-medium">
                                                <Link to={`/problem-banks/${bank.id}/analysis`} className="hover:underline text-primary">
                                                    {bank.name}
                                                </Link>
                                            </TableCell>
                                            {criteriaList.map(cid => (
                                                <TableCell key={cid}>
                                                    {bank.means && bank.means[cid] !== undefined && bank.means[cid] !== null
                                                        ? bank.means[cid].toFixed(2)
                                                        : '-'}
                                                </TableCell>
                                            ))}
                                            <TableCell className="font-bold">
                                                {bank.means && bank.means.weighted_score !== undefined && bank.means.weighted_score !== null
                                                    ? bank.means.weighted_score.toFixed(2)
                                                    : '-'}
                                            </TableCell>
                                            <TableCell>
                                                {(() => {
                                                    const irr = bank.inter_rater_reliability;
                                                    if (irr === undefined || irr === null) return '-';
                                                    if (typeof irr === 'number') return irr.toFixed(3);
                                                    if (typeof irr === 'object') {
                                                        const values = Object.values(irr);
                                                        if (values.length === 0) return '-';
                                                        const mean = values.reduce((a, b) => a + b, 0) / values.length;
                                                        return mean.toFixed(3);
                                                    }
                                                    return '-';
                                                })()}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>ANOVA Results</CardTitle>
                        <CardDescription>Statistical comparison of ratings across banks (One-way ANOVA)</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="rounded-md border">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Criterion</TableHead>
                                        <TableHead>F-statistic</TableHead>
                                        <TableHead>p-value</TableHead>
                                        <TableHead>Significant?</TableHead>
                                        <TableHead>Banks Included</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {anova.map((res, idx) => (
                                        <TableRow key={idx}>
                                            <TableCell className="font-medium">{res.criterion_id}</TableCell>
                                            <TableCell>{res.f_stat?.toFixed(3) || '-'}</TableCell>
                                            <TableCell className={res.significant ? "font-bold text-green-600" : ""}>
                                                {res.p_value?.toFixed(4) || '-'}
                                            </TableCell>
                                            <TableCell>
                                                {res.significant ? (
                                                    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-green-100 text-green-800">
                                                        Yes
                                                    </span>
                                                ) : (
                                                    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-secondary text-secondary-foreground">
                                                        No
                                                    </span>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-muted-foreground text-sm">
                                                {res.banks_included.join(', ')}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                    {anova.length === 0 && (
                                        <TableRow>
                                            <TableCell colSpan={5} className="text-center text-muted-foreground h-24">
                                                No common criteria found for comparison or insufficient data.
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </AppShell>
    );
};

export default GlobalAnalysisPage;
