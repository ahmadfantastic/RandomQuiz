import React, { useState, useEffect } from 'react';
import { Star } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import api from '@/lib/api';

const InstructorRatingInterface = ({ problemId, bankId }) => {
    const [rubric, setRubric] = useState(null);
    const [rating, setRating] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (problemId && bankId) {
            loadData();
        }
    }, [problemId, bankId]);

    const loadData = async () => {
        setIsLoading(true);
        try {
            const [rubricRes, ratingRes] = await Promise.all([
                api.get(`/api/problem-banks/${bankId}/rubric/`),
                api.get(`/api/problems/${problemId}/rate/`)
            ]);
            setRubric(rubricRes.data);
            setRating(ratingRes.data);
        } catch (err) {
            console.error('Failed to load rating data', err);
            setError('Unable to load rating data.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleRate = async (criterionId, value) => {
        if (!rating) return;

        const currentEntries = rating.entries || [];
        const existingEntryIndex = currentEntries.findIndex(e => e.criterion_id === criterionId);

        let newEntries;
        if (existingEntryIndex >= 0) {
            newEntries = [...currentEntries];
            newEntries[existingEntryIndex] = { criterion_id: criterionId, value };
        } else {
            newEntries = [...currentEntries, { criterion_id: criterionId, value }];
        }

        const newRating = { ...rating, entries: newEntries };
        setRating(newRating); // Optimistic update

        setIsSaving(true);
        try {
            const res = await api.put(`/api/problems/${problemId}/rate/`, newRating);
            setRating(res.data);
        } catch (err) {
            console.error('Failed to save rating', err);
            setError('Failed to save rating.');
            // Revert optimistic update? For now just show error.
        } finally {
            setIsSaving(false);
        }
    };

    if (isLoading) return <div className="text-sm text-muted-foreground">Loading ratings...</div>;
    if (!rubric || !rubric.criteria || rubric.criteria.length === 0) return null;

    // Transform rating entries into a map for easier lookup
    const ratingsMap = rating?.entries?.reduce((acc, entry) => {
        acc[entry.criterion_id] = entry;
        return acc;
    }, {}) || {};

    return (
        <div className="mt-4 border-t pt-4">
            <h4 className="text-sm font-medium mb-3">Instructor Rating</h4>
            {error && <div className="text-xs text-red-500 mb-2">{error}</div>}
            <div className="space-y-6">
                {rubric.criteria.map((criterion) => {
                    const currentRatingEntry = ratingsMap[criterion.id];
                    const currentValue = currentRatingEntry ? currentRatingEntry.value : null;

                    return (
                        <div key={criterion.id} className="rounded-2xl border bg-card/70 p-4 shadow-sm">
                            <div className="mb-4">
                                <h4 className="font-medium text-foreground">{criterion.name}</h4>
                                <p className="text-sm text-muted-foreground">{criterion.description}</p>
                            </div>

                            <div className="grid grid-cols-5 gap-2 sm:gap-3">
                                {rubric.scale.map((option) => {
                                    const isSelected = currentValue === option.value;
                                    return (
                                        <button
                                            key={`${criterion.id}-${option.value}`}
                                            type="button"
                                            onClick={() => handleRate(criterion.id, option.value)}
                                            disabled={isSaving}
                                            className={cn(
                                                'flex flex-col items-center gap-2 rounded-lg p-2 transition-colors sm:p-3',
                                                isSelected ? 'bg-primary/10' : 'hover:bg-muted/50',
                                                isSaving ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'
                                            )}
                                        >
                                            <div
                                                className={cn(
                                                    'flex h-8 w-8 items-center justify-center rounded-full border-2 text-sm font-semibold transition-colors sm:h-10 sm:w-10 sm:text-base',
                                                    isSelected
                                                        ? 'border-primary bg-primary text-primary-foreground'
                                                        : 'border-muted-foreground/30 text-muted-foreground hover:border-primary/50'
                                                )}
                                            >
                                                {option.value}
                                            </div>
                                            <span className="hidden text-center text-xs text-muted-foreground sm:block">
                                                {option.label}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    );
                })}
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
                {isSaving ? 'Saving...' : 'Ratings are saved automatically.'}
            </div>
        </div>
    );
};

export default InstructorRatingInterface;
