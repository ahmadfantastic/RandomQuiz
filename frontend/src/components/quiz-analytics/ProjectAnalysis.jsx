import React, { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Upload, FileUp, AlertCircle, CheckCircle2 } from 'lucide-react';
import CorrelationAnalysis from '@/components/quiz-analytics/CorrelationAnalysis';
import TeamVarianceAnalysis from '@/components/quiz-analytics/TeamVarianceAnalysis';
import api from '@/lib/api';

const ProjectAnalysis = ({ quizId, data, onDataUpdate }) => {
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState(null);
    const [successMessage, setSuccessMessage] = useState(null);
    const fileInputRef = useRef(null);

    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        setUploading(true);
        setUploadError(null);
        setSuccessMessage(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            await api.post(`/api/quizzes/${quizId}/project-scores/`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            setSuccessMessage('Scores imported successfully!');
            if (onDataUpdate) {
                onDataUpdate();
            }
            // Clear input
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        } catch (err) {
            console.error(err);
            setUploadError(err.response?.data?.detail || 'Failed to upload CSV.');
        } finally {
            setUploading(false);
        }
    };



    return (
        <div className="space-y-6">
            {data && data.score_correlation && (
                <CorrelationAnalysis
                    data={data}
                    title="Project Score vs Quiz Score"
                    description="Analysis of correlation between project score (independent) and quiz score."
                    xAxisLabel="Quiz Score"
                    yAxisLabel="Project Score"
                />
            )}

            {data && data.team_variance && data.team_variance.length > 0 && (
                <TeamVarianceAnalysis
                    data={data.team_variance}
                />
            )}

            <Card>
                <CardHeader>
                    <CardTitle>Import Project Scores</CardTitle>
                    <CardDescription>
                        Upload a CSV file containing "Project Score" and "Quiz Score" columns to analyze the correlation.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="grid w-full max-w-sm items-center gap-1.5">
                        <Label htmlFor="csv-upload">Project Scores CSV</Label>
                        <div className="flex gap-2">
                            <Input
                                id="csv-upload"
                                type="file"
                                accept=".csv"
                                ref={fileInputRef}
                                onChange={handleFileUpload}
                                disabled={uploading}
                            />
                            {uploading && <Button disabled>Uploading...</Button>}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                            Required headers: <code>Project Score</code>, <code>Quiz Score</code>. Optional: <code>Team</code>, <code>Grade</code>.
                        </p>
                    </div>

                    {uploadError && (
                        <Alert variant="destructive" className="mt-4">
                            <AlertCircle className="h-4 w-4" />
                            <AlertTitle>Error</AlertTitle>
                            <AlertDescription>{uploadError}</AlertDescription>
                        </Alert>
                    )}

                    {successMessage && (
                        <Alert className="mt-4 border-green-500 text-green-700 bg-green-50">
                            <CheckCircle2 className="h-4 w-4 text-green-600" />
                            <AlertTitle>Success</AlertTitle>
                            <AlertDescription>{successMessage}</AlertDescription>
                        </Alert>
                    )}
                </CardContent>
            </Card>
        </div>
    );
};

export default ProjectAnalysis;
