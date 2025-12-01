import React, { useState, useEffect, useCallback } from 'react';
import { Check, Edit, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';

import RubricEditorModal from './RubricEditorModal';
import api from '@/lib/api';
import { cn } from '@/lib/utils';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

marked.setOptions({ mangle: false });

const getLevelColor = (points, maxPoints) => {
    // Calculate intensity based on points relative to maxPoints
    // If maxPoints is 0, default to neutral/green
    const ratio = maxPoints > 0 ? points / maxPoints : 1;

    if (ratio < 0.33) return "bg-red-50 border-red-200 hover:border-red-300 text-red-900";
    if (ratio < 0.66) return "bg-yellow-50 border-yellow-200 hover:border-yellow-300 text-yellow-900";
    return "bg-green-50 border-green-200 hover:border-green-300 text-green-900";
};

const getLevelBadgeColor = (index, total) => {
    const intensity = total > 1 ? index / (total - 1) : 1;
    if (intensity < 0.33) return "bg-red-100 text-red-700";
    if (intensity < 0.66) return "bg-yellow-100 text-yellow-700";
    return "bg-green-100 text-green-700";
};

const renderProblemMarkupHtml = (statement) => {
    if (!statement) return '';
    return DOMPurify.sanitize(marked.parse(statement));
};

const FeedbackEditor = ({ initialValue, onSave }) => {
    const [value, setValue] = useState(initialValue || '');

    useEffect(() => {
        setValue(initialValue || '');
    }, [initialValue]);

    return (
        <Textarea
            placeholder="Enter feedback for the student..."
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onBlur={() => onSave(value)}
            className="mt-2"
        />
    );
};

const GradingInterface = ({ quizId }) => {
    const [attempts, setAttempts] = useState([]);
    const [selectedAttemptId, setSelectedAttemptId] = useState(null);
    const [rubric, setRubric] = useState(null);
    const [isRubricModalOpen, setIsRubricModalOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [grades, setGrades] = useState({}); // Map of attemptId -> slotId -> grade
    const [isSaving, setIsSaving] = useState(false);

    const loadData = useCallback(async () => {
        setIsLoading(true);
        try {
            const [attemptsRes, rubricRes] = await Promise.all([
                api.get(`/api/quizzes/${quizId}/attempts/`),
                api.get(`/api/quizzes/${quizId}/grading-rubric/`)
            ]);
            setAttempts(attemptsRes.data);
            setRubric(rubricRes.data);
        } catch (err) {
            console.error('Failed to load grading data', err);
        } finally {
            setIsLoading(false);
        }
    }, [quizId]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const selectedAttempt = attempts.find(a => a.id === selectedAttemptId);

    const handleGradeSave = async (slotId, gradeData) => {
        if (!selectedAttemptId) return;
        setIsSaving(true);
        try {
            await api.put(
                `/api/quizzes/${quizId}/attempts/${selectedAttemptId}/slots/${slotId}/grade/`,
                gradeData
            );

            setAttempts(prevAttempts => prevAttempts.map(attempt => {
                if (attempt.id !== selectedAttemptId) return attempt;

                return {
                    ...attempt,
                    attempt_slots: attempt.attempt_slots.map(slot => {
                        if (slot.slot === slotId) {
                            return {
                                ...slot,
                                grade: {
                                    ...slot.grade,
                                    ...gradeData
                                }
                            };
                        }
                        return slot;
                    })
                };
            }));
        } catch (err) {
            console.error('Failed to save grade', err);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="flex flex-col md:flex-row h-[calc(100vh-200px)] gap-4">
            {/* Sidebar - Student List */}
            <div className="w-full md:w-64 flex-shrink-0 border-b md:border-b-0 md:border-l md:pl-4 overflow-y-auto max-h-[200px] md:max-h-full order-1 md:order-2">
                <div className="mb-4 flex justify-between items-center">
                    <h3 className="font-semibold">Students</h3>
                    <Button variant="outline" size="sm" onClick={() => setIsRubricModalOpen(true)}>
                        <Edit className="h-3 w-3 mr-1" /> Rubric
                    </Button>
                </div>
                <div className="space-y-2">
                    {isLoading ? (
                        <div className="space-y-2">
                            {[1, 2, 3].map((i) => (
                                <div key={i} className="h-12 bg-muted/50 rounded-md animate-pulse" />
                            ))}
                        </div>
                    ) : attempts.map(attempt => {
                        const gradableSlots = attempt.attempt_slots?.filter(s => s.response_type !== 'rating') || [];
                        const isFullyGraded = gradableSlots.length > 0 && gradableSlots.every(s => s.grade?.items?.length > 0);

                        // Calculate score
                        let currentScore = 0;
                        let maxScore = 0;

                        if (rubric?.items) {
                            // Calculate max score per slot (sum of max points of all criteria)
                            const maxScorePerSlot = rubric.items.reduce((sum, item) => {
                                const maxPoints = Math.max(...item.levels.map(l => l.points || 0));
                                return sum + maxPoints;
                            }, 0);

                            maxScore = maxScorePerSlot * gradableSlots.length;

                            // Calculate current score
                            gradableSlots.forEach(slot => {
                                slot.grade?.items?.forEach(gradeItem => {
                                    const rubricItem = rubric.items.find(ri => ri.id === gradeItem.rubric_item);
                                    const level = rubricItem?.levels.find(l => l.id === gradeItem.selected_level);
                                    if (level) {
                                        currentScore += (level.points || 0);
                                    }
                                });
                            });
                        }

                        return (
                            <button
                                key={attempt.id}
                                onClick={() => setSelectedAttemptId(attempt.id)}
                                className={cn(
                                    "w-full text-left p-3 rounded-md flex items-center gap-3 transition-colors",
                                    selectedAttemptId === attempt.id
                                        ? "bg-primary text-primary-foreground"
                                        : "hover:bg-muted"
                                )}
                            >
                                <div className={cn(
                                    "h-8 w-8 rounded-full flex items-center justify-center",
                                    isFullyGraded
                                        ? "bg-green-100 text-green-600"
                                        : "bg-muted-foreground/20"
                                )}>
                                    {isFullyGraded ? <Check className="h-4 w-4" /> : <User className="h-4 w-4" />}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="font-medium truncate">{attempt.student_identifier}</p>
                                    <div className="flex justify-between items-center mt-0.5">
                                        <p className="text-xs opacity-80">
                                            {new Date(attempt.started_at).toLocaleDateString()}
                                        </p>
                                        {isFullyGraded && (
                                            <span className={cn(
                                                "text-xs font-bold px-1.5 py-0.5 rounded",
                                                selectedAttemptId === attempt.id
                                                    ? "bg-primary-foreground/20 text-primary-foreground"
                                                    : "bg-primary/10 text-primary"
                                            )}>
                                                {currentScore}/{maxScore}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Main Content - Grading Interface */}
            <div className="flex-1 overflow-y-auto pr-2 order-2 md:order-1">
                {selectedAttempt ? (
                    <div className="space-y-8">
                        <div className="flex justify-between items-start">
                            <div>
                                <h2 className="text-2xl font-bold">{selectedAttempt.student_identifier}</h2>
                                <p className="text-muted-foreground">
                                    Started: {new Date(selectedAttempt.started_at).toLocaleString()}
                                </p>
                            </div>
                        </div>

                        {selectedAttempt.attempt_slots?.filter(s => s.response_type !== 'rating').map((slot, index) => (
                            <Card key={slot.id} className="border-muted">
                                <CardHeader className="bg-muted/30 pb-3">
                                    <CardTitle className="text-base font-medium">
                                        {slot.slot_label}
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="pt-4 space-y-6">
                                    {/* Problem & Answer */}
                                    <div className="grid gap-6 md:grid-cols-2">
                                        <div className="space-y-2">
                                            <Label className="text-muted-foreground uppercase text-xs font-bold">Problem {slot.problem_display_label}</Label>
                                            <div className="p-3 bg-muted/20 rounded-md text-sm prose max-w-none">
                                                <div dangerouslySetInnerHTML={{ __html: renderProblemMarkupHtml(slot.problem_statement) }} />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <Label className="text-muted-foreground uppercase text-xs font-bold">Student Answer</Label>
                                            <div className="p-3 bg-muted/20 rounded-md text-sm min-h-[100px]">
                                                {slot.answer_data?.text || <span className="text-muted-foreground italic">No answer provided</span>}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Grading Interface */}
                                    {slot.response_type !== 'rating' && (
                                        <div className="border-t pt-4">
                                            <h4 className="font-medium mb-4 flex items-center gap-2">
                                                <Check className="h-4 w-4 text-primary" /> Grading
                                            </h4>

                                            {rubric?.items?.length > 0 ? (
                                                <div className="border rounded-md overflow-hidden">
                                                    <table className="w-full text-sm text-left">
                                                        <thead className="bg-muted/50 text-muted-foreground font-medium border-b">
                                                            <tr>
                                                                <th className="px-4 py-3 w-1/4">Criteria</th>
                                                                <th className="px-4 py-3">Levels</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody className="divide-y">
                                                            {rubric.items.map(item => (
                                                                <tr key={item.id} className="bg-card">
                                                                    <td className="px-4 py-4 align-top">
                                                                        <p className="font-medium">{item.label}</p>
                                                                        <p className="text-xs text-muted-foreground mt-1">{item.description}</p>
                                                                    </td>
                                                                    <td className="px-4 py-4">
                                                                        <div className="flex flex-wrap gap-2">
                                                                            {item.levels.map((level, index) => {
                                                                                const isSelected = slot.grade?.items?.some(
                                                                                    i => i.rubric_item === item.id && i.selected_level === level.id
                                                                                );

                                                                                // Find max points for this item to calculate color intensity
                                                                                const maxPoints = Math.max(...item.levels.map(l => l.points || 0));

                                                                                return (
                                                                                    <button
                                                                                        key={level.id}
                                                                                        onClick={() => {
                                                                                            const currentItems = slot.grade?.items || [];
                                                                                            const otherItems = currentItems.filter(i => i.rubric_item !== item.id);
                                                                                            const newItems = [...otherItems, { rubric_item: item.id, selected_level: level.id }];

                                                                                            handleGradeSave(slot.slot, {
                                                                                                feedback: slot.grade?.feedback || '',
                                                                                                items: newItems
                                                                                            });
                                                                                        }}
                                                                                        className={cn(
                                                                                            "flex-1 min-w-[120px] p-3 rounded-md border text-left transition-all relative",
                                                                                            isSelected
                                                                                                ? "ring-2 ring-primary border-primary"
                                                                                                : "hover:bg-muted/50",
                                                                                            getLevelColor(level.points || 0, maxPoints)
                                                                                        )}
                                                                                    >
                                                                                        <div className="flex justify-between items-start gap-2 mb-1">
                                                                                            <div className="flex items-center gap-2">
                                                                                                <span className="font-semibold">{level.points} pts</span>
                                                                                                <span className="font-medium text-xs text-muted-foreground">- {level.label}</span>
                                                                                            </div>
                                                                                            {isSelected && <Check className="h-4 w-4 text-primary absolute top-2 right-2" />}
                                                                                        </div>
                                                                                        <p className="text-xs text-muted-foreground leading-tight mt-1">{level.description}</p>
                                                                                    </button>
                                                                                );
                                                                            })}
                                                                        </div>
                                                                    </td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            ) : (
                                                <div className="text-center py-8 text-muted-foreground bg-muted/20 rounded-md">
                                                    No rubric defined. Click "Rubric" in the sidebar to create one.
                                                </div>
                                            )}

                                            <div className="mt-6">
                                                <Label>Feedback</Label>
                                                <FeedbackEditor
                                                    initialValue={slot.grade?.feedback}
                                                    onSave={(newValue) => {
                                                        handleGradeSave(slot.slot, {
                                                            feedback: newValue,
                                                            items: slot.grade?.items || []
                                                        });
                                                    }}
                                                />
                                            </div>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                ) : (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                        <User className="h-12 w-12 mb-4 opacity-20" />
                        <p>Select a student from the sidebar to start grading</p>
                    </div>
                )}
            </div>

            <RubricEditorModal
                open={isRubricModalOpen}
                onOpenChange={setIsRubricModalOpen}
                quizId={quizId}
                onSaveSuccess={loadData}
            />
        </div >
    );
};

export default GradingInterface;
