import React, { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const TimeDistributionChart = ({ timeStats }) => {
    const { raw_values, min, max } = timeStats;

    const data = useMemo(() => {
        if (!raw_values || raw_values.length === 0) return [];

        // Create bins
        const binCount = 10;
        const range = max - min;
        const binSize = range > 0 ? range / binCount : 1;

        const bins = Array.from({ length: binCount }, (_, i) => ({
            range: `${Math.round(min + i * binSize)}m - ${Math.round(min + (i + 1) * binSize)}m`,
            count: 0,
            minVal: min + i * binSize,
            maxVal: min + (i + 1) * binSize
        }));

        raw_values.forEach(val => {
            const binIndex = Math.min(
                Math.floor((val - min) / binSize),
                binCount - 1
            );
            if (binIndex >= 0) {
                bins[binIndex].count++;
            }
        });

        return bins;
    }, [raw_values, min, max]);

    if (!raw_values || raw_values.length === 0) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>Time Distribution</CardTitle>
                </CardHeader>
                <CardContent className="h-[300px] flex items-center justify-center text-muted-foreground">
                    No data available
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>Time Distribution</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="h-[300px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={data}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} />
                            <XAxis
                                dataKey="range"
                                tick={{ fontSize: 12 }}
                                interval={0}
                                angle={-45}
                                textAnchor="end"
                                height={60}
                            />
                            <YAxis allowDecimals={false} />
                            <Tooltip
                                cursor={{ fill: 'transparent' }}
                                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                            />
                            <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
    );
};

export default TimeDistributionChart;
