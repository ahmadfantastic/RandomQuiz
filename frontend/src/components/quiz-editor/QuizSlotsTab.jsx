import React from 'react';
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
}) => (
  <div className="space-y-6">
    <div className="flex items-center justify-between">
      <div>
        <h3 className="text-lg font-semibold">Problem Slots</h3>
        <p className="text-sm text-muted-foreground">
          Each slot draws random problems from a bank
        </p>
      </div>
      <div className="flex gap-2">
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
            <svg className="h-8 w-8 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
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
          const problemCount = slot.slot_problems?.length ?? 0;
          const isReady = problemCount > 0;
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
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Bank:</span>
                    <span className="font-medium">{slot.problem_bank_name || 'None'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Response:</span>
                    <span className="font-medium">{getResponseTypeLabel(slot.response_type)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Problems:</span>
                    <span className="font-medium">{problemCount}</span>
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
              </CardContent>
            </Card>
          );
        })}
      </div>
    )}
  </div>
);

export default QuizSlotsTab;
