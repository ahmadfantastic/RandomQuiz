import React, { useState } from 'react';
import { Modal } from '@/components/ui/modal';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const TeamVarianceAnalysis = ({ data }) => {
    const [selectedTeam, setSelectedTeam] = useState(null);

    // data is array of { team, project_score, quiz_scores: [], members: [] }
    // Transform for ScatterChart
    const points = [];
    data.forEach(teamData => {
        teamData.quiz_scores.forEach(score => {
            points.push({
                team: teamData.team,
                quiz_score: score,
                project_score: teamData.project_score
            });
        });
    });

    if (points.length === 0) {
        return null;
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>Freeloader Detection (Intra-Group Variance)</CardTitle>
                <CardDescription>
                    Analysis of individual Quiz Scores within Project Teams. Teams are sorted by Project Score.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="flex flex-col lg:flex-row gap-6 items-start">
                    {/* Left Column: Stats Table */}
                    <div className="w-full lg:w-1/3 shrink-0">
                        <h3 className="text-lg font-semibold mb-4">Team Statistics</h3>
                        <div className="rounded-md border max-h-[400px] overflow-y-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Team</TableHead>
                                        <TableHead>Proj Mean</TableHead>
                                        <TableHead>Quiz Mean</TableHead>
                                        <TableHead>Quiz Var</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.map((team, idx) => (
                                        <TableRow
                                            key={idx}
                                            className="cursor-pointer hover:bg-muted/50"
                                            onClick={() => setSelectedTeam(team)}
                                        >
                                            <TableCell className="font-medium">{team.team}</TableCell>
                                            <TableCell>{team.project_mean}</TableCell>
                                            <TableCell>{team.quiz_mean}</TableCell>
                                            <TableCell>{team.quiz_variance}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </div>

                    {/* Right Column: Scatter Plot */}
                    <div className="w-full lg:w-2/3 h-[400px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <ScatterChart
                                margin={{
                                    top: 20,
                                    right: 20,
                                    bottom: 20,
                                    left: 20,
                                }}
                            >
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis
                                    dataKey="team"
                                    type="category"
                                    allowDuplicatedCategory={false}
                                    name="Team"
                                    label={{ value: 'Teams (Sorted by Project Score)', position: 'insideBottom', offset: -10 }}
                                />
                                <YAxis
                                    type="number"
                                    dataKey="quiz_score"
                                    name="Quiz Score"
                                    label={{ value: 'Individual Quiz Score', angle: -90, position: 'insideLeft' }}
                                />
                                <Tooltip
                                    cursor={{ strokeDasharray: '3 3' }}
                                    content={({ active, payload }) => {
                                        if (active && payload && payload.length) {
                                            const p = payload[0].payload;
                                            return (
                                                <div className="bg-background border rounded p-2 shadow-md text-sm">
                                                    <div className="font-semibold">{p.team}</div>
                                                    <div>Project Score: {p.project_score}</div>
                                                    <div>Quiz Score: {p.quiz_score}</div>
                                                </div>
                                            );
                                        }
                                        return null;
                                    }}
                                />
                                <Scatter name="Students" data={points} fill="#8884d8" />
                            </ScatterChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <Modal
                    open={!!selectedTeam}
                    onOpenChange={(open) => !open && setSelectedTeam(null)}
                    title={`Details for ${selectedTeam?.team}`}
                    description="Raw scores for members of this team."
                    className="max-w-2xl"
                >
                    {selectedTeam && (
                        <div className="rounded-md border">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Member</TableHead>
                                        <TableHead>Project Score</TableHead>
                                        <TableHead>Quiz Score</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {selectedTeam.quiz_scores.map((score, i) => (
                                        <TableRow key={i}>
                                            <TableCell className="font-medium">
                                                {selectedTeam.members && selectedTeam.members[i] ? selectedTeam.members[i] : `Student ${i + 1}`}
                                            </TableCell>
                                            <TableCell>
                                                {selectedTeam.project_scores_list && selectedTeam.project_scores_list[i]
                                                    ? selectedTeam.project_scores_list[i]
                                                    : selectedTeam.project_mean}
                                            </TableCell>
                                            <TableCell>{score}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </Modal>
            </CardContent>
        </Card>
    );
};

export default TeamVarianceAnalysis;
