import React, { useState, useEffect } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Modal } from '@/components/ui/modal';
import api from '@/lib/api';

const ProblemBankRubricEditor = ({ open, onOpenChange, bankId, onSaveSuccess }) => {
    const [rubric, setRubric] = useState({ scale: [], criteria: [], rubric_id: null });
    const [availableRubrics, setAvailableRubrics] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (open && bankId) {
            loadData();
        }
    }, [open, bankId]);

    const loadData = async () => {
        setIsLoading(true);
        try {
            const [rubricRes, availableRes] = await Promise.all([
                api.get(`/api/problem-banks/${bankId}/rubric/`),
                api.get(`/api/rubrics/`)
            ]);

            const data = rubricRes.data || {};
            setRubric({
                scale: data.scale || [],
                criteria: data.criteria || [],
                rubric_id: data.rubric_id || null
            });
            setAvailableRubrics(availableRes.data || []);
            setError('');
        } catch (err) {
            setError('Unable to load data.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleRubricSelect = (rubricId) => {
        if (!rubricId) {
            setRubric(prev => ({ ...prev, rubric_id: '' }));
            return;
        }

        const selected = availableRubrics.find(r => r.id.toString() === rubricId.toString());
        if (selected) {
            setRubric({
                scale: selected.scale_options.map(o => ({ value: o.value, label: o.label })),
                criteria: selected.criteria.map(c => ({
                    id: c.id,
                    name: c.name,
                    description: c.description
                })),
                rubric_id: selected.id
            });
        }
    };

    const handleSave = async () => {
        if (!rubric.rubric_id) {
            setError('Please select a rubric template.');
            return;
        }

        setIsSaving(true);
        setError('');
        try {
            await api.put(`/api/problem-banks/${bankId}/rubric/`, { rubric_id: rubric.rubric_id });
            if (onSaveSuccess) onSaveSuccess();
            onOpenChange(false);
        } catch (err) {
            setError('Failed to save rubric.');
        } finally {
            setIsSaving(false);
        }
    };

    // Scale Management - REMOVED
    // Criteria Management - REMOVED

    return (
        <Modal
            open={open}
            onOpenChange={onOpenChange}
            title="Edit Problem Bank Rubric"
            description="Select a rubric template for instructor ratings."
            className="max-w-4xl"
        >
            <div className="space-y-6 max-h-[70vh] overflow-y-auto pr-2">
                {isLoading ? (
                    <div>Loading...</div>
                ) : (
                    <>
                        {error && <div className="text-red-500 text-sm">{error}</div>}

                        {/* Global Rubric Selection */}
                        <div className="space-y-2">
                            <Label>Rubric Template</Label>
                            <select
                                className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                value={rubric.rubric_id || ''}
                                onChange={(e) => handleRubricSelect(e.target.value)}
                            >
                                <option value="">Select a Rubric...</option>
                                {availableRubrics.map(r => (
                                    <option key={r.id} value={r.id}>{r.name} {r.is_global ? '(Global)' : ''}</option>
                                ))}
                            </select>
                            <p className="text-xs text-muted-foreground">
                                Select a pre-defined rubric for this bank.
                            </p>
                        </div>

                        {rubric.rubric_id && (
                            <>
                                <div className="border-t my-4" />

                                {/* Scale Section (Read-only) */}
                                <div className="space-y-4">
                                    <h3 className="text-lg font-medium">Rating Scale</h3>
                                    <div className="grid gap-4">
                                        {rubric.scale.map((option, index) => (
                                            <div key={index} className="flex gap-4 items-center bg-muted/30 p-3 rounded-md">
                                                <div className="w-24">
                                                    <Label className="text-xs">Value</Label>
                                                    <div className="text-sm font-medium">{option.value}</div>
                                                </div>
                                                <div className="flex-1">
                                                    <Label className="text-xs">Label</Label>
                                                    <div className="text-sm">{option.label}</div>
                                                </div>
                                            </div>
                                        ))}
                                        {rubric.scale.length === 0 && (
                                            <div className="text-sm text-muted-foreground italic">No scale options defined.</div>
                                        )}
                                    </div>
                                </div>

                                <div className="border-t my-4" />

                                {/* Criteria Section (Read-only) */}
                                <div className="space-y-4">
                                    <h3 className="text-lg font-medium">Rating Criteria</h3>
                                    <div className="space-y-4">
                                        {rubric.criteria.map((criterion, index) => (
                                            <Card key={index} className="relative border-muted">
                                                <CardHeader className="pb-2 pt-4 px-4">
                                                    <div className="flex items-start gap-4">
                                                        <div className="flex-1 space-y-2">
                                                            <div className="flex gap-2">
                                                                <div className="w-1/3">
                                                                    <Label>ID</Label>
                                                                    <div className="text-sm font-mono">{criterion.id}</div>
                                                                </div>
                                                                <div className="flex-1">
                                                                    <Label>Name</Label>
                                                                    <div className="text-sm font-medium">{criterion.name}</div>
                                                                </div>

                                                            </div>
                                                            <div>
                                                                <Label>Description</Label>
                                                                <div className="text-sm text-muted-foreground">{criterion.description}</div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </CardHeader>
                                            </Card>
                                        ))}
                                        {rubric.criteria.length === 0 && (
                                            <div className="text-sm text-muted-foreground italic">No criteria defined.</div>
                                        )}
                                    </div>
                                </div>
                            </>
                        )}
                    </>
                )}
            </div>
            <div className="pt-4 flex justify-end gap-2 border-t mt-4">
                <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                <Button onClick={handleSave} disabled={isSaving || !rubric.rubric_id}>
                    {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
            </div>
        </Modal>
    );
};

export default ProblemBankRubricEditor;
