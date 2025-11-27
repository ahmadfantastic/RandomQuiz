import React from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { getResponseTypeLabel } from '@/lib/responseTypes';

const QuizSlotsTab = ({
  slots,
  banks,
  isLoadingBanks,
  slotError,
  openSlotModal,
  openSlotDetailModal,
  loadSlots,
  slotProblemOptions = {},
  openRubricCriteria,
  openRubricScale,
}) => (
  <div className="space-y-6">
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h3 className="text-lg font-semibold">Problem Slots</h3>
        <p className="text-sm text-muted-foreground">
          Each slot draws random problems from a bank
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={loadSlots}>Refresh</Button>
        <Button variant="outline" to="/problem-banks">Manage Banks</Button>
        <Button onClick={openSlotModal} disabled={isLoadingBanks || !banks.length}>
          Add Slot
        </Button>
      </div>
    </div>

    {slotError && (
      <Card className="border-destructive/30 bg-destructive/5">
        <CardContent className="py-3 text-sm text-destructive">{slotError}</CardContent>
      </Card>
    )}

    {!slots.length ? (
      <Card>
        <CardContent className="py-12 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <Plus className="h-8 w-8 text-muted-foreground" />
          </div>
          <p className="text-lg font-semibold">No slots yet</p>
          <p className="text-sm text-muted-foreground">Create your first slot to start building the quiz</p>
          <Button onClick={openSlotModal} className="mt-4" disabled={isLoadingBanks || !banks.length}>
            Add Your First Slot
          </Button>
        </CardContent>
      </Card>
    ) : (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {slots.map((slot) => {
          const selectedProblemCount = slot.slot_problems?.length ?? 0;
          const responseBadgeClass = {
            open_text: 'bg-blue-100 text-blue-800',
            rating: 'bg-purple-100 text-purple-800',
          }[slot.response_type] ?? 'bg-blue-100 text-blue-800';
          const hasBank = Boolean(slot.problem_bank);
          const availableProblems = hasBank ? slotProblemOptions[slot.problem_bank]?.length : undefined;
          const bankProblemTotal = hasBank ? availableProblems ?? '—' : '—';
          const isReady = selectedProblemCount > 0;
          return (
            <Card key={slot.id} className={cn(
              'transition-all hover:shadow-md',
              isReady ? 'border-emerald-500/20' : 'border-amber-500/20'
            )}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <CardTitle className="text-base">{slot.label || 'Untitled'}</CardTitle>
                    <p className="text-xs text-muted-foreground">Order {slot.order || '—'}</p>
                  </div>
                  <span
                    className={cn(
                      'rounded-full px-2 py-1 text-xs font-semibold',
                      isReady ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                    )}
                  >
                    {isReady ? 'Ready' : 'Setup'}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Bank:</span>
                    <span className="font-medium">{slot.problem_bank_name || 'None'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Response:</span>
                    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold', responseBadgeClass)}>
                      {getResponseTypeLabel(slot.response_type)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Problems:</span>
                    <span className="font-semibold">
                      {selectedProblemCount}/{bankProblemTotal}
                    </span>
                  </div>
                </div>
                <Button
                  onClick={() => openSlotDetailModal(slot.id)}
                  size="sm"
                  className="w-full"
                  variant={isReady ? 'outline' : 'default'}
                >
                  {isReady ? 'Edit Slot' : 'Configure Slot'}
                </Button>
                {slot.response_type === 'rating' && (
                  <div className="grid grid-cols-2 gap-2">
                    <Button variant="outline" size="sm" onClick={openRubricCriteria}>
                      Edit Criteria
                    </Button>
                    <Button variant="outline" size="sm" onClick={openRubricScale}>
                      Edit Scale
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    )}
  </div>
);

export default QuizSlotsTab;
