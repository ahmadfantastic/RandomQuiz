import React from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const InstructorsRatingsTab = ({ data, roundToTwo, problem_groups, criteriaList, banks, anova }) => {
    return (
        <div className="space-y-8">
            <Card>
                <CardHeader>
                    <CardTitle>Inter-Rater Reliability Analysis</CardTitle>
                    <CardDescription>Comparison of agreement (weighted kappa) between instructors for each criterion</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="rounded-md border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Criterion</TableHead>
                                    {problem_groups && problem_groups.map(group => (
                                        <TableHead key={group.name}>{group.name}</TableHead>
                                    ))}

                                    {(!problem_groups || problem_groups.length !== 2) && (
                                        <TableHead>Sample Size (N Pairs)</TableHead>
                                    )}
                                    {problem_groups && problem_groups.length === 2 && (
                                        <>
                                            <TableHead>Sig. (2-tailed)</TableHead>
                                            <TableHead>Sig. (1-tailed)</TableHead>
                                            <TableHead>Cohen's d</TableHead>
                                        </>
                                    )}

                                    <TableHead>Average Score</TableHead>

                                    <TableHead>Weighted Kappa</TableHead>
                                </TableRow>

                            </TableHeader>
                            <TableBody>
                                {data.global_criteria_irr && data.global_criteria_irr.length > 0 ? (
                                    data.global_criteria_irr.map((item, idx) => (
                                        <TableRow key={idx}>
                                            <TableCell className="font-medium">{item.criterion}</TableCell>
                                            {/* Group Columns */}
                                            {problem_groups && problem_groups.map(group => (
                                                <TableCell key={group.name}>
                                                    {group.means && group.means[item.criterion] !== undefined
                                                        ? roundToTwo(group.means[item.criterion])
                                                        : '-'}
                                                </TableCell>
                                            ))}

                                            {(!problem_groups || problem_groups.length !== 2) && (
                                                <TableCell>{item.n}</TableCell>
                                            )}

                                            {problem_groups && problem_groups.length === 2 && (
                                                <>
                                                    <TableCell className={item.t_test?.p_2_tailed < 0.05 ? "font-bold text-green-600" : ""}>
                                                        {item.t_test && item.t_test.p_2_tailed != null ? item.t_test.p_2_tailed.toFixed(4) : '-'}
                                                    </TableCell>
                                                    <TableCell className={item.t_test?.p_1_tailed < 0.05 ? "font-bold text-green-600" : ""}>
                                                        {item.t_test && item.t_test.p_1_tailed != null ? item.t_test.p_1_tailed.toFixed(4) : '-'}
                                                    </TableCell>
                                                    <TableCell>
                                                        {item.t_test && item.t_test.cohens_d != null ? item.t_test.cohens_d.toFixed(3) : '-'}
                                                    </TableCell>
                                                </>
                                            )}

                                            <TableCell>
                                                {item.mean !== undefined ? roundToTwo(item.mean) : '-'}
                                            </TableCell>

                                            <TableCell>
                                                {item.kappa != null ? item.kappa.toFixed(3) : '-'}
                                            </TableCell>
                                        </TableRow>

                                    ))
                                ) : (
                                    <TableRow>
                                        <TableCell colSpan={4 + (problem_groups ? problem_groups.length : 0) + (problem_groups && problem_groups.length === 2 ? 3 : 0)} className="text-center text-muted-foreground h-24">
                                            No inter-rater data available.
                                        </TableCell>
                                    </TableRow>
                                )}

                                {data.overall_criteria_stats && (
                                    <TableRow className="border-t-2 border-border font-bold bg-muted/50">
                                        <TableCell>Weighted</TableCell>
                                        {/* Group Columns for Weighted Row */}
                                        {problem_groups && problem_groups.map(group => (
                                            <TableCell key={group.name}>
                                                {data.overall_criteria_stats.group_means && data.overall_criteria_stats.group_means[group.name] !== undefined ? (
                                                    roundToTwo(data.overall_criteria_stats.group_means[group.name])
                                                ) : '-'}
                                            </TableCell>
                                        ))}

                                        {(!problem_groups || problem_groups.length !== 2) && (
                                            <TableCell>{data.overall_criteria_stats.n}</TableCell>
                                        )}
                                        {problem_groups && problem_groups.length === 2 && (
                                            <>
                                                <TableCell className={data.overall_criteria_stats.t_test?.p_2_tailed < 0.05 ? "font-bold text-green-600" : ""}>
                                                    {data.overall_criteria_stats.t_test && data.overall_criteria_stats.t_test.p_2_tailed != null ? data.overall_criteria_stats.t_test.p_2_tailed.toFixed(4) : '-'}
                                                </TableCell>
                                                <TableCell className={data.overall_criteria_stats.t_test?.p_1_tailed < 0.05 ? "font-bold text-green-600" : ""}>
                                                    {data.overall_criteria_stats.t_test && data.overall_criteria_stats.t_test.p_1_tailed != null ? data.overall_criteria_stats.t_test.p_1_tailed.toFixed(4) : '-'}
                                                </TableCell>
                                                <TableCell>
                                                    {data.overall_criteria_stats.t_test && data.overall_criteria_stats.t_test.cohens_d != null ? data.overall_criteria_stats.t_test.cohens_d.toFixed(3) : '-'}
                                                </TableCell>
                                            </>
                                        )}
                                        <TableCell>{roundToTwo(data.overall_criteria_stats.mean)}</TableCell>


                                        <TableCell>

                                        </TableCell>

                                    </TableRow>


                                )}
                            </TableBody>

                        </Table>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Problem Bank Rating Summary</CardTitle>
                    <CardDescription>Average instructor ratings and weighted scores for each problem bank</CardDescription>
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
                                                    ? roundToTwo(bank.means[cid])
                                                    : '-'}
                                            </TableCell>
                                        ))}
                                        <TableCell className="font-bold">
                                            {(() => {
                                                const score = bank.means?.weighted_score;
                                                if (score !== undefined && score !== null) {
                                                    return roundToTwo(score);
                                                }
                                                return '-';
                                            })()}
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
                                {data.overall_bank_stats && (
                                    <TableRow className="border-t-2 border-border font-bold bg-muted/50">
                                        <TableCell>All</TableCell>
                                        {criteriaList.map(cid => (
                                            <TableCell key={cid}>
                                                {data.overall_bank_stats[cid] !== undefined
                                                    ? roundToTwo(data.overall_bank_stats[cid])
                                                    : '-'}
                                            </TableCell>
                                        ))}
                                        <TableCell>
                                            {(() => {
                                                const score = data.overall_bank_stats.weighted_score;
                                                if (score !== undefined && score !== null) {
                                                    return roundToTwo(score);
                                                }
                                                return '-';
                                            })()}
                                        </TableCell>


                                        <TableCell>
                                            {data.overall_bank_stats.inter_rater_reliability !== undefined && data.overall_bank_stats.inter_rater_reliability !== null
                                                ? data.overall_bank_stats.inter_rater_reliability.toFixed(3)
                                                : '-'}
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>

                        </Table>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Bank Variance Analysis (ANOVA)</CardTitle>
                    <CardDescription>One-way ANOVA comparing instructor ratings across problem banks</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="rounded-md border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Criterion</TableHead>
                                    <TableHead>F-statistic</TableHead>
                                    <TableHead>p-value</TableHead>
                                    <TableHead>Post-hoc Analysis (Tukey's HSD)</TableHead>
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
                                                res.tukey_results && res.tukey_results.length > 0 ? (
                                                    <div className="text-xs space-y-1">
                                                        {res.tukey_results.map((tukeyRes, tukeyIdx) => (
                                                            <div key={tukeyIdx}>{tukeyRes}</div>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    <span className="text-muted-foreground italic text-xs">No significant pairwise differences</span>
                                                )
                                            ) : (
                                                '-'
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))}
                                {anova.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={4} className="text-center text-muted-foreground h-24">
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
    );
};

export default InstructorsRatingsTab;
