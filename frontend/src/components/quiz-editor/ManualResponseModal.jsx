import React, { useState, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Modal } from '@/components/ui/modal';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import LikertRating from '@/components/quiz-attempt/LikertRating';
import { Loader2 } from 'lucide-react';

const ManualResponseModal = ({
    isOpen,
    onClose,
    slots,
    slotProblemOptions,
    rubric,
    onSave,
    isSaving,
}) => {
    const [studentIdentifier, setStudentIdentifier] = useState('');
    const [responses, setResponses] = useState({}); // slotId -> { problemId, answerData }

    const handleProblemChange = (slotId, problemId) => {
        setResponses((prev) => ({
            ...prev,
            [slotId]: {
                ...prev[slotId],
                problemId: problemId,
            },
        }));
    };

    const handleTextChange = (slotId, text) => {
        setResponses((prev) => ({
            ...prev,
            [slotId]: {
                ...prev[slotId],
                answerData: { text },
            },
        }));
    };

    const handleRatingChange = (slotId, criterionId, value) => {
        setResponses((prev) => {
            const currentAnswerData = prev[slotId]?.answerData || { ratings: {} };
            const currentRatings = currentAnswerData.ratings || {};

            return {
                ...prev,
                [slotId]: {
                    ...prev[slotId],
                    answerData: {
                        ...currentAnswerData,
                        ratings: {
                            ...currentRatings,
                            [criterionId]: value,
                        },
                    },
                },
            };
        });
    };

    const handleSubmit = (e) => {
        e.preventDefault();

        if (!studentIdentifier.trim()) {
            return;
        }

        const formattedAnswers = {};
        slots.forEach(slot => {
            const resp = responses[slot.id];
            if (resp) {
                formattedAnswers[slot.id] = {
                    problem_id: resp.problemId,
                    answer_data: resp.answerData
                };
            }
        });

        onSave({
            student_identifier: studentIdentifier,
            answers: formattedAnswers
        });
    };

    const ratingCriteria = useMemo(() => {
        return Array.isArray(rubric?.criteria) ? rubric.criteria : [];
    }, [rubric]);

    const ratingScale = useMemo(() => {
        return Array.isArray(rubric?.scale) ? rubric.scale : [];
    }, [rubric]);

    return (
        <Modal
            open={isOpen}
            onOpenChange={onClose}
            title="Add Manual Response"
            className="max-w-3xl"
        >
            <div className="flex flex-col gap-6 max-h-[70vh] overflow-hidden">
                <div className="space-y-2">
                    <Label htmlFor="student-id">Student Identifier</Label>
                    <Input
                        id="student-id"
                        value={studentIdentifier}
                        onChange={(e) => setStudentIdentifier(e.target.value)}
                        placeholder="e.g. John Doe or ID123"
                    />
                </div>

                <div className="flex-1 overflow-y-auto pr-2 space-y-8">
                    {slots.map((slot) => {
                        const slotProblems = slot.slot_problems || [];
                        const currentResponse = responses[slot.id] || {};
                        const selectedProblemId = currentResponse.problemId;

                        return (
                            <div key={slot.id} className="border rounded-lg p-4 space-y-4">
                                <div className="flex items-center justify-between">
                                    <h4 className="font-medium">{slot.label}</h4>
                                    <span className="text-xs text-muted-foreground uppercase">{slot.response_type === 'rating' ? 'Rating' : 'Text'}</span>
                                </div>

                                <div className="space-y-2">
                                    <Label>Select Problem</Label>
                                    <select
                                        className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                        value={selectedProblemId ? String(selectedProblemId) : ''}
                                        onChange={(e) => handleProblemChange(slot.id, Number(e.target.value))}
                                    >
                                        <option value="" disabled>Select the problem presented</option>
                                        {slotProblems.map((sp) => (
                                            <option key={sp.problem} value={String(sp.problem)}>
                                                {sp.display_label || `Problem ${sp.problem}`}
                                            </option>
                                        ))}
                                    </select>
                                </div>

                                <div className="space-y-2">
                                    <Label>Student Answer</Label>
                                    {slot.response_type === 'rating' ? (
                                        <LikertRating
                                            criteria={ratingCriteria}
                                            scale={ratingScale}
                                            selectedRatings={currentResponse.answerData?.ratings || {}}
                                            onRatingSelect={(criterionId, value) => handleRatingChange(slot.id, criterionId, value)}
                                            slotId={slot.id}
                                        />
                                    ) : (
                                        <Textarea
                                            placeholder="Enter student's answer..."
                                            value={currentResponse.answerData?.text || ''}
                                            onChange={(e) => handleTextChange(slot.id, e.target.value)}
                                            className="min-h-[100px]"
                                        />
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>

                <div className="flex justify-end gap-2 pt-4 border-t">
                    <Button variant="outline" onClick={onClose} disabled={isSaving}>
                        Cancel
                    </Button>
                    <Button onClick={handleSubmit} disabled={isSaving || !studentIdentifier.trim()}>
                        {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Save Response
                    </Button>
                </div>
            </div>
        </Modal>
    );
};

export default ManualResponseModal;
