import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

const CFAAnalysis = ({ results }) => {
    if (!results) return null;

    const { fit_indices, loadings } = results;

    // Helper to determine badge color for fit indices
    const getFitColor = (metric, value) => {
        if (metric === 'rmsea') return value < 0.08 ? 'text-green-600 bg-green-50 animate-pulse' : 'text-red-600 bg-red-50';
        if (metric === 'cfi') return value > 0.90 ? 'text-green-600 bg-green-50' : 'text-red-600 bg-red-50';
        return 'text-gray-900';
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>Halo Effect Analysis (CFA)</CardTitle>
                <CardDescription>
                    Confirmatory Factor Analysis testing a single "General Impression" (Halo) factor.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                    <div className={`p-4 rounded-lg border flex flex-col items-center justify-center ${getFitColor('rmsea', fit_indices.rmsea)}`}>
                        <span className="text-sm font-medium uppercase tracking-wider opacity-70">RMSEA</span>
                        <span className="text-3xl font-bold">{fit_indices.rmsea}</span>
                        <span className="text-xs mt-1 text-center">
                            {fit_indices.rmsea < 0.05 ? "Excellent Fit" : fit_indices.rmsea < 0.08 ? "Good Fit" : "Poor Fit"}
                        </span>
                    </div>
                    <div className={`p-4 rounded-lg border flex flex-col items-center justify-center ${getFitColor('cfi', fit_indices.cfi)}`}>
                        <span className="text-sm font-medium uppercase tracking-wider opacity-70">CFI</span>
                        <span className="text-3xl font-bold">{fit_indices.cfi}</span>
                        <span className="text-xs mt-1 text-center">
                            {fit_indices.cfi > 0.95 ? "Excellent Fit" : fit_indices.cfi > 0.90 ? "Acceptable Fit" : "Poor Fit"}
                        </span>
                    </div>
                    <div className="p-4 rounded-lg border flex flex-col items-center justify-center bg-gray-50">
                        <span className="text-sm font-medium uppercase tracking-wider opacity-70 text-gray-500">Chi-Square</span>
                        <span className="text-3xl font-bold text-gray-700">{fit_indices.chi_square}</span>
                        <span className="text-xs mt-1 text-center text-gray-500">
                            df = {fit_indices.df}
                        </span>
                    </div>
                </div>

                <div className="space-y-4">
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-widest">Factor Loadings (Strength of Halo)</h3>
                    <div className="h-[300px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={loadings} margin={{ top: 20, right: 30, left: 20, bottom: 50 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                <XAxis
                                    dataKey="criterion"
                                    angle={-45}
                                    textAnchor="end"
                                    height={60}
                                    interval={0}
                                    tick={{ fontSize: 12 }}
                                />
                                <YAxis domain={[0, 1]} label={{ value: 'Loading', angle: -90, position: 'insideLeft' }} />
                                <Tooltip
                                    cursor={{ fill: 'transparent' }}
                                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                />
                                <ReferenceLine y={0.4} stroke="red" strokeDasharray="3 3" label={{ position: 'insideTopRight', value: 'Weak Cutoff (0.4)', fill: 'red', fontSize: 10 }} />
                                <ReferenceLine y={0.7} stroke="orange" strokeDasharray="3 3" label={{ position: 'insideTopRight', value: 'Strong Cutoff (0.7)', fill: 'orange', fontSize: 10 }} />
                                <Bar dataKey="loading" fill="#8884d8" radius={[4, 4, 0, 0]} name="Factor Loading" />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                    <p className="text-sm text-gray-500 italic text-center">
                        Higher loadings (&gt;0.7) indicate that the criterion is strongly driven by the general "Halo" factor.
                    </p>
                </div>

                <div className="mt-8 rounded-md border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Criterion</TableHead>
                                <TableHead>Factor Loading (Std.)</TableHead>
                                <TableHead>Strength</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {loadings.map((item, idx) => (
                                <TableRow key={idx}>
                                    <TableCell className="font-medium">{item.criterion}</TableCell>
                                    <TableCell>{item.loading.toFixed(3)}</TableCell>
                                    <TableCell>
                                        <span className={`px-2 py-1 rounded-full text-xs font-semibold ${item.loading > 0.7 ? 'bg-orange-100 text-orange-800' :
                                                item.loading > 0.4 ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
                                            }`}>
                                            {item.loading > 0.7 ? 'Strong' : item.loading > 0.4 ? 'Moderate' : 'Weak'}
                                        </span>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>
        </Card>
    );
};

export default CFAAnalysis;
