import React, { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts';

const RatingChart = ({ data }) => {
    const criteria = data?.criteria;

    // Fallback for empty data
    if (!criteria || criteria.length === 0) {
        if (data?.distribution) {
            return <RatingChart data={{ criteria: [{ name: 'Overall', distribution: data.distribution }] }} />;
        }
        return <div className="text-center text-muted-foreground py-8">No ratings yet</div>;
    }

    // Process data for Diverging Stacked Bar Chart
    const { processedData, bars, height, domain, levels, levelColorMap } = useMemo(() => {
        if (!criteria.length) return { processedData: [], bars: [], height: 0, domain: [-100, 100], levels: [], levelColorMap: {} };

        // 1. Determine the scale structure
        const sampleDist = [...criteria[0].distribution].sort((a, b) => a.value - b.value);
        const levels = sampleDist.map(d => d.label);
        const count = levels.length;
        const midPoint = Math.floor(count / 2);
        const hasNeutral = count % 2 !== 0;

        const BASE_COLORS = [
            '#ef4444', // Disagree (Most negative)
            '#fca5a5', // Slightly disagree
            '#9ca3af', // Neutral
            '#93c5fd', // Slightly agree
            '#2563eb', // Agree (Most positive)
        ];

        const levelColorMap = {};
        levels.forEach((label, idx) => {
            levelColorMap[label] = BASE_COLORS[idx % BASE_COLORS.length];
        });

        let minVal = 0;
        let maxVal = 0;

        // 2. Transform data
        const chartData = criteria.map(criterion => {
            const row = { name: criterion.name };
            const distMap = {};
            criterion.distribution.forEach(d => {
                distMap[d.label] = d;
            });

            const sortedDist = levels.map(label => distMap[label] || { label, percentage: 0, count: 0, value: 0 });

            let currentNeg = 0;
            let currentPos = 0;

            // Left side (Negative)
            for (let i = midPoint - 1; i >= 0; i--) {
                const item = sortedDist[i];
                const key = `left_${item.label}`;
                row[key] = -item.percentage;
                row[`orig_${item.label}`] = item;
                currentNeg += item.percentage;
            }

            // Neutral processing
            if (hasNeutral) {
                const neutralItem = sortedDist[midPoint];
                const halfVal = neutralItem.percentage / 2;

                row[`left_neutral_${neutralItem.label}`] = -halfVal;
                row[`orig_neutral_${neutralItem.label}`] = neutralItem;
                currentNeg += halfVal;

                row[`right_neutral_${neutralItem.label}`] = halfVal;
                currentPos += halfVal;
            }

            // Right side (Positive)
            const startRight = hasNeutral ? midPoint + 1 : midPoint;
            for (let i = startRight; i < count; i++) {
                const item = sortedDist[i];
                const key = `right_${item.label}`;
                row[key] = item.percentage;
                row[`orig_${item.label}`] = item;
                currentPos += item.percentage;
            }

            minVal = Math.max(minVal, currentNeg);
            maxVal = Math.max(maxVal, currentPos);

            return row;
        });

        // Add padding to domain
        const domainMax = Math.ceil(maxVal / 10) * 10;
        const domainMin = -Math.ceil(minVal / 10) * 10;
        // Ensure at least some width if everything is 0
        const finalDomain = [domainMin === 0 ? -10 : domainMin, domainMax === 0 ? 10 : domainMax];

        // 3. Generate Bar components configuration
        const barConfigs = [];

        // Left Bars (Negative) - Render order: Closest to 0 -> Furthest
        if (hasNeutral) {
            const label = levels[midPoint];
            barConfigs.push({
                dataKey: `left_neutral_${label}`,
                color: levelColorMap[label],
                stackId: 'stack',
                label: label,
                name: label,
                isNeutral: true
            });
        }
        for (let i = midPoint - 1; i >= 0; i--) {
            const label = levels[i];
            barConfigs.push({
                dataKey: `left_${label}`,
                color: levelColorMap[label],
                stackId: 'stack',
                label: label,
                name: label
            });
        }

        // Right Bars (Positive) - Render order: Closest to 0 -> Furthest
        if (hasNeutral) {
            const label = levels[midPoint];
            barConfigs.push({
                dataKey: `right_neutral_${label}`,
                color: levelColorMap[label],
                stackId: 'stack',
                label: label,
                name: label,
                isNeutral: true,
                hideLegend: true
            });
        }
        const startRight = hasNeutral ? midPoint + 1 : midPoint;
        for (let i = startRight; i < count; i++) {
            const label = levels[i];
            barConfigs.push({
                dataKey: `right_${label}`,
                color: levelColorMap[label],
                stackId: 'stack',
                label: label,
                name: label
            });
        }

        const calcHeight = Math.max(150, criteria.length * 60 + 60);

        return { processedData: chartData, bars: barConfigs, height: calcHeight, domain: finalDomain, levels, levelColorMap };
    }, [criteria]);

    const CustomTooltip = ({ active, payload, label }) => {
        if (!active || !payload || !payload.length) return null;

        const rowData = payload[0].payload;
        const items = [];
        // Reconstruct items from rowData
        // We can iterate levels to ensure correct order
        levels.forEach(lvl => {
            // Check for normal or neutral keys
            // Normal left: left_Label
            // Normal right: right_Label
            // Neutral: left_neutral_Label or right_neutral_Label
            // We stored orig_Label or orig_neutral_Label

            // Simpler: just check for orig_Label or orig_neutral_Label
            let item = rowData[`orig_${lvl}`];
            if (!item) item = rowData[`orig_neutral_${lvl}`];

            if (item) {
                items.push({
                    ...item,
                    color: levelColorMap[lvl]
                });
            }
        });

        return (
            <div className="bg-background border rounded p-2 shadow-lg text-xs">
                <p className="font-semibold mb-2">{label}</p>
                {items.map((item, idx) => (
                    <div key={idx} className="flex items-center gap-2 mb-1 last:mb-0">
                        <div
                            className="w-2 h-2 rounded-sm"
                            style={{ backgroundColor: item.color }}
                        />
                        <span className="font-medium">{item.label}:</span>
                        <span>{Math.round(item.percentage)}% ({item.count})</span>
                    </div>
                ))}
            </div>
        );
    };

    const renderLegend = (props) => {
        return (
            <div className="flex flex-wrap justify-center gap-4 mt-2">
                {levels.map((level) => (
                    <div key={level} className="flex items-center gap-1.5">
                        <div
                            className="w-3 h-3 rounded-sm"
                            style={{ backgroundColor: levelColorMap[level] }}
                        />
                        <span className="text-xs text-muted-foreground font-medium">
                            {level}
                        </span>
                    </div>
                ))}
            </div>
        );
    };

    return (
        <div style={{ height: height, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
                <BarChart
                    layout="vertical"
                    data={processedData}
                    margin={{ top: 20, right: 30, left: 40, bottom: 5 }}
                    stackOffset="sign"
                >
                    <XAxis
                        type="number"
                        tickFormatter={(val) => Math.abs(val) + '%'}
                        domain={domain}
                        hide={false}
                        tick={{ fontSize: 10 }}
                    />
                    <YAxis
                        type="category"
                        dataKey="name"
                        width={100}
                        tick={{ fontSize: 11, width: 90 }}
                        interval={0}
                    />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: 'transparent' }} />
                    <Legend content={renderLegend} />
                    <ReferenceLine x={0} stroke="#666" />

                    {bars.map(bar => (
                        <Bar
                            key={bar.dataKey}
                            dataKey={bar.dataKey}
                            stackId="stack"
                            fill={bar.color}
                            name={bar.name}
                            legendType={bar.hideLegend ? 'none' : undefined}
                        />
                    ))}
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
};

export default RatingChart;
