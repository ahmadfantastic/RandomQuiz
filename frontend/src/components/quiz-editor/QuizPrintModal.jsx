import React, { useCallback, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Modal } from '@/components/ui/modal';
import { previewQuizPdf } from '@/lib/printQuizPdf';

const DEFAULT_IDENTITY_INSTRUCTION = 'Required so your instructor can match your submission.';

const slugify = (value = '') => {
    const text = String(value || '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
    return text || 'quiz-print';
};

const COPIES_INPUT_ID = 'quiz-print-copies';

const QuizPrintModal = ({
    open,
    onOpenChange,
    quiz,
    details = {},
    slots = [],
    rubric = { scale: [], criteria: [] }
}) => {
    const [isDownloading, setIsDownloading] = useState(false);
    const [downloadError, setDownloadError] = useState('');
    const [copiesInput, setCopiesInput] = useState('1');

    const printableFilename = useMemo(() => `${slugify(quiz?.title)}-printable.pdf`, [quiz?.title]);

    const copies = useMemo(() => Math.max(1, Number(copiesInput) || 1), [copiesInput]);

    const selectRandomSlots = useCallback(() => {
        return (slots || []).map((slot, index) => {
            const problems = Array.isArray(slot.slot_problems) ? slot.slot_problems : [];
            if (!problems.length) {
                return { slot, problem: null, index };
            }
            const randomIndex = Math.floor(Math.random() * problems.length) % problems.length;
            return { slot, problem: problems[randomIndex], index };
        });
    }, [slots]);

    const printableSlots = useMemo(() => selectRandomSlots(), [selectRandomSlots]);

    const printableCopies = useMemo(() => {
        const copiesCount = Math.max(1, copies);
        if (copiesCount <= 1) {
            return [printableSlots];
        }
        const versions = [printableSlots];
        for (let index = 1; index < copiesCount; index += 1) {
            versions.push(selectRandomSlots());
        }
        return versions;
    }, [copies, printableSlots, selectRandomSlots]);

    const ratingCriteria = useMemo(() => {
        return Array.isArray(rubric?.criteria) ? rubric.criteria : [];
    }, [rubric?.criteria]);

    const ratingScaleOptions = useMemo(() => {
        return Array.isArray(rubric?.scale) ? rubric.scale : [];
    }, [rubric?.scale]);

    const hasProblemContent = printableSlots.some((entry) => Boolean(entry.problem));
    const canShuffle = (slots || []).length > 0;


    const handleCopiesChange = useCallback((event) => {
        const sanitized = event.target.value.replace(/[^0-9]/g, '');
        setCopiesInput(sanitized);
    }, []);
    const handleCopiesBlur = useCallback(() => {
        if (!copiesInput) {
            setCopiesInput('1');
        }
    }, [copiesInput]);

    const getMissingFields = useCallback(() => {
        const missing = [];
        if (!details?.description?.trim()) {
            missing.push('quiz description');
        }
        if (!details?.identity_instruction?.trim()) {
            missing.push('identity instruction');
        }
        printableSlots.forEach(({ slot }) => {
            if (!slot?.instruction?.trim()) {
                missing.push(slot?.label ? `"${slot.label}" instruction` : 'a slot instruction');
            }
        });
        return missing;
    }, [details, printableSlots]);

    const handleDownloadPdf = useCallback(() => {
        if (!canShuffle) {
            return;
        }
        setDownloadError('');
        setIsDownloading(true);
        const missingFields = getMissingFields();
        if (missingFields.length) {
            setDownloadError(`Fill the ${missingFields.join(', ')} before printing.`);
            setIsDownloading(false);
            return;
        }
        previewQuizPdf({
            printableFilename,
            quiz,
            details,
            printableCopies,
            ratingCriteria,
            ratingScaleOptions,
        })
            .then(() => setIsDownloading(false))
            .catch((error) => {
                console.error('PDF generation failed', error);
                setDownloadError('Unable to generate the printable PDF right now.');
                setIsDownloading(false);
            });
    }, [
        printableFilename,
        canShuffle,
        copies,
        details,
        printableCopies,
        getMissingFields,
        quiz,
        ratingCriteria,
        ratingScaleOptions,
    ]);

    return (
        <Modal
            open={open}
            onOpenChange={onOpenChange}
            title="Printable quiz"
            description="Generate a randomized version of the quiz that students can write on."
            className="max-w-xl"
        >
            <div className="space-y-6">
                <div className="flex flex-col gap-4 rounded-lg border p-4">
                    <div className="flex flex-col gap-2">
                        <Label htmlFor={COPIES_INPUT_ID} className="text-sm font-medium">
                            Number of Copies
                        </Label>
                        <div className="flex items-center gap-3">
                            <Input
                                type="number"
                                min={1}
                                value={copiesInput}
                                onChange={handleCopiesChange}
                                onBlur={handleCopiesBlur}
                                className="max-w-[100px]"
                                inputMode="numeric"
                                id={COPIES_INPUT_ID}
                            />
                            <p className="text-xs text-muted-foreground">
                                Each copy will contain unique randomized problems and start on a new page.
                            </p>
                        </div>
                    </div>

                    <div className="flex justify-start pt-2">
                        <Button
                            onClick={handleDownloadPdf}
                            disabled={!hasProblemContent || isDownloading}
                            className="w-full sm:w-auto"
                        >
                            {isDownloading ? 'Generating PDF…' : 'Download PDF'}
                        </Button>
                    </div>
                </div>

                {(!hasProblemContent || !canShuffle) && (
                    <Card className="border border-muted/40 bg-muted/10">
                        <CardHeader>
                            <CardTitle className="text-sm">Slots need problems</CardTitle>
                        </CardHeader>
                        <CardContent className="text-sm text-muted-foreground">
                            Add at least one problem to a slot before downloading the printable quiz.
                        </CardContent>
                    </Card>
                )}

                {downloadError && <p className="text-sm text-destructive">{downloadError}</p>}

                <div className="flex justify-end">
                    <Button variant="ghost" onClick={() => onOpenChange(false)}>
                        Close
                    </Button>
                </div>
            </div>
        </Modal>
    );
};

export default QuizPrintModal;
