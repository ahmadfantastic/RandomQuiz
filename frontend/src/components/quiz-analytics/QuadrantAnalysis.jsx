import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Label } from 'recharts';

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const QuadrantChart = ({ title, data, xThreshold, yThreshold, xDomain, yDomain }) => {
    // Quadrant Labels logic:
    // Top-Right: Masters (High Proj / High Quiz)
    // Bottom-Left: Strugglers (Low Proj / Low Quiz)
    // Top-Left: Conceptualizers (Low Proj / High Quiz)
    // Bottom-Right: Implementers (High Proj / Low Quiz)

    // Calculate Stats
    const total = data.length;
    const stats = { masters: 0, implementers: 0, conceptualizers: 0, strugglers: 0 };

    data.forEach(p => {
        // data.y is Project Score (X-Axis), data.x is Quiz Score (Y-Axis)
        // Check thresholds for High/Low. 
        // Using >= for High.
        const isHighProject = p.y >= xThreshold;
        const isHighQuiz = p.x >= yThreshold;

        if (isHighProject && isHighQuiz) stats.masters++;
        else if (isHighProject && !isHighQuiz) stats.implementers++;
        else if (!isHighProject && isHighQuiz) stats.conceptualizers++;
        else stats.strugglers++;
    });

    const getPct = (count) => total > 0 ? ((count / total) * 100).toFixed(1) + '%' : '0%';

    return (
        <div className="flex flex-col border rounded-md p-2">
            <h4 className="text-sm font-semibold text-center mb-2">{title}</h4>
            <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                            dataKey="y"
                            type="number"
                            name="Project Score"
                            domain={xDomain}
                            label={{ value: 'Project Score', position: 'insideBottom', offset: -10, fontSize: 12 }}
                            tickFormatter={(val) => Number(val).toFixed(1)}
                        />
                        <YAxis
                            dataKey="x"
                            type="number"
                            name="Quiz Score"
                            domain={yDomain}
                            label={{ value: 'Quiz Score', angle: -90, position: 'insideLeft', fontSize: 12 }}
                            tickFormatter={(val) => Number(val).toFixed(0)}
                        />
                        <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(value, name) => [Number(value).toFixed(name === 'Project Score' ? 1 : 0), name]} />

                        {/* Threshold Lines */}
                        <ReferenceLine x={xThreshold} stroke="red" strokeDasharray="3 3">
                            <Label value={`${Number(xThreshold).toFixed(1)}`} position="insideTopRight" fontSize={10} fill="red" />
                        </ReferenceLine>
                        <ReferenceLine y={yThreshold} stroke="red" strokeDasharray="3 3">
                            <Label value={`${Number(yThreshold).toFixed(0)}`} position="insideRight" fontSize={10} fill="red" />
                        </ReferenceLine>

                        {/* Quadrant Labels */}
                        <ReferenceLine x={xDomain[1]} y={yDomain[1]} stroke="none">
                            <Label value="Masters" position="insideTopRight" offset={10} className="fill-green-600 font-bold" />
                        </ReferenceLine>
                        <ReferenceLine x={xDomain[0]} y={yDomain[0]} stroke="none">
                            <Label value="Strugglers" position="insideBottomLeft" offset={10} className="fill-red-600 font-bold" />
                        </ReferenceLine>
                        <ReferenceLine x={xDomain[0]} y={yDomain[1]} stroke="none">
                            <Label value="Conceptualizers" position="insideTopLeft" offset={10} className="fill-blue-600 font-bold" />
                        </ReferenceLine>
                        <ReferenceLine x={xDomain[1]} y={yDomain[0]} stroke="none">
                            <Label value="Implementers" position="insideBottomRight" offset={10} className="fill-orange-600 font-bold" />
                        </ReferenceLine>

                        <Scatter name="Students" data={data} fill="#8884d8" />
                    </ScatterChart>
                </ResponsiveContainer>
            </div>

            <div className="mt-4 px-2">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="h-8">Profile</TableHead>
                            <TableHead className="h-8 text-right">Count</TableHead>
                            <TableHead className="h-8 text-right">%</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        <TableRow className="h-8">
                            <TableCell className="font-medium text-green-700 py-1">Masters</TableCell>
                            <TableCell className="text-right py-1">{stats.masters}</TableCell>
                            <TableCell className="text-right py-1">{getPct(stats.masters)}</TableCell>
                        </TableRow>
                        <TableRow className="h-8">
                            <TableCell className="font-medium text-blue-700 py-1">Conceptualizers</TableCell>
                            <TableCell className="text-right py-1">{stats.conceptualizers}</TableCell>
                            <TableCell className="text-right py-1">{getPct(stats.conceptualizers)}</TableCell>
                        </TableRow>
                        <TableRow className="h-8">
                            <TableCell className="font-medium text-orange-700 py-1">Implementers</TableCell>
                            <TableCell className="text-right py-1">{stats.implementers}</TableCell>
                            <TableCell className="text-right py-1">{getPct(stats.implementers)}</TableCell>
                        </TableRow>
                        <TableRow className="h-8">
                            <TableCell className="font-medium text-red-700 py-1">Strugglers</TableCell>
                            <TableCell className="text-right py-1">{stats.strugglers}</TableCell>
                            <TableCell className="text-right py-1">{getPct(stats.strugglers)}</TableCell>
                        </TableRow>
                    </TableBody>
                </Table>
            </div>
        </div>
    );
};

const QuadrantAnalysis = ({ data, config }) => {
    if (!data || !config) return null;

    // config contains: project_median, project_thresh_val, project_threshold_ratio, quiz_median, quiz_max_50, quiz_max_possible
    const points = data; // Array of {x: quiz, y: project} -> Chart expects X=Project(y), Y=Quiz(x)

    // Extract scores
    const projectScores = points.map(p => p.y);
    const quizScores = points.map(p => p.x);

    const ratioVal = config.project_threshold_ratio || 0.95;
    const ratioPct = (ratioVal * 100).toFixed(0);

    // Helper to calculate symmetric domain centered on threshold
    const getCenteredDomain = (scores, threshold, forceZero = false) => {
        if (threshold === undefined || threshold === null) return ['auto', 'auto'];

        let minScore = Math.min(...scores);
        let maxScore = Math.max(...scores);

        // Let's expand slightly for padding
        // const padding = 5; 
        if (forceZero) {
            minScore = Math.min(minScore, 0);
        }

        const distMin = Math.abs(minScore - threshold);
        const distMax = Math.abs(maxScore - threshold);
        let delta = Math.max(distMin, distMax);

        // Ensure visualization has some breathing room if variance is low
        if (delta < 5) delta = 5;
        delta = delta * 1.1; // Add 10% padding so points aren't on the edge

        // To be safe and show nice numbers, maybe round up?
        // Let's just use exact symmetric range.

        return [threshold - delta, threshold + delta];
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>Learner Profile Analysis (Quadrants)</CardTitle>
                <CardDescription>
                    Categorizing students into profiles based on Project vs Quiz performance.
                    Plots are centered on the respective thresholds.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Plot 1: Med / Med */}
                    <QuadrantChart
                        title="Median Project / Median Quiz"
                        data={points}
                        xThreshold={config.project_median}
                        yThreshold={config.quiz_median}
                        xDomain={getCenteredDomain(projectScores, config.project_median, false)}
                        yDomain={getCenteredDomain(quizScores, config.quiz_median, true)}
                    />

                    {/* Plot 2: Med / 50% Max */}
                    {config.quiz_max_possible > 0 && (
                        <QuadrantChart
                            title="Median Project / 50% Quiz Max"
                            data={points}
                            xThreshold={config.project_median}
                            yThreshold={config.quiz_max_50}
                            xDomain={getCenteredDomain(projectScores, config.project_median, false)}
                            yDomain={getCenteredDomain(quizScores, config.quiz_max_50, true)}
                        />
                    )}

                    {/* Plot 3: Thresh / Med */}
                    <QuadrantChart
                        title={`${ratioPct}% Max Project / Median Quiz`}
                        data={points}
                        xThreshold={config.project_thresh_val}
                        yThreshold={config.quiz_median}
                        xDomain={getCenteredDomain(projectScores, config.project_thresh_val, false)}
                        yDomain={getCenteredDomain(quizScores, config.quiz_median, true)}
                    />

                    {/* Plot 4: Thresh / 50% Max */}
                    {config.quiz_max_possible > 0 && (
                        <QuadrantChart
                            title={`${ratioPct}% Max Project / 50% Quiz Max`}
                            data={points}
                            xThreshold={config.project_thresh_val}
                            yThreshold={config.quiz_max_50}
                            xDomain={getCenteredDomain(projectScores, config.project_thresh_val, false)}
                            yDomain={getCenteredDomain(quizScores, config.quiz_max_50, true)}
                        />
                    )}
                </div>
                {config.quiz_max_possible === 0 && (
                    <p className="text-sm text-muted-foreground mt-4 text-center">
                        * Rubric information not available to calculate "50% of Quiz Max" thresholds.
                    </p>
                )}
            </CardContent>
        </Card>
    );
};

export default QuadrantAnalysis;
