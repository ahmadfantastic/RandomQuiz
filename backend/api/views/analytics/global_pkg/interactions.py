import numpy as np
import math
from collections import defaultdict
from scipy import stats as sp_stats, stats
from django.db.models import Sum
from django.db.models.functions import Coalesce

from rest_framework.views import APIView
from rest_framework.response import Response

from accounts.models import ensure_instructor
from accounts.permissions import IsInstructor
from quizzes.models import (
    Quiz, QuizAttempt, QuizSlot, QuizAttemptInteraction, QuizSlotGrade
)
from ..utils import calculate_typing_metrics

class GlobalInteractionAnalyticsView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request):
        instructor = ensure_instructor(request.user)
        
        # Get all quizzes for this instructor
        quizzes = Quiz.objects.filter(owner=instructor)
        
        # Get all attempts
        attempts = QuizAttempt.objects.filter(quiz__in=quizzes, completed_at__isnull=False)
        
        # Interactions
        # Group by slot
        interactions_by_slot = {}
        
        # We need to label slots with Quiz Title + Slot Label
        all_slots = QuizSlot.objects.filter(quiz__in=quizzes)
        slot_map = {s.id: f"{s.quiz.title} - {s.label or s.order}" for s in all_slots}
        
        all_interactions = QuizAttemptInteraction.objects.filter(
            attempt_slot__attempt__in=attempts
        ).values(
            'attempt_slot__slot_id',
            'event_type',
            'created_at',
            'metadata',
            'attempt_slot__attempt__student_identifier',
            'attempt_slot__attempt__started_at',
            'attempt_slot__attempt__completed_at'
        )
        
        for interaction in all_interactions:
            slot_id = interaction['attempt_slot__slot_id']
            if slot_id not in interactions_by_slot:
                interactions_by_slot[slot_id] = []
            
            start = interaction['attempt_slot__attempt__started_at']
            end = interaction['attempt_slot__attempt__completed_at']
            created_at = interaction['created_at']
            position = 0
            if start and end and created_at:
                total_duration = (end - start).total_seconds()
                if total_duration > 0:
                    event_time = (created_at - start).total_seconds()
                    position = min(max(event_time / total_duration, 0), 1) * 100

            interactions_by_slot[slot_id].append({
                'event_type': interaction['event_type'],
                'created_at': created_at,
                'metadata': interaction['metadata'],
                'position': position,
                'student_id': interaction['attempt_slot__attempt__student_identifier'],
                'attempt_started_at': start,
                'attempt_completed_at': end
            })

        # Calculate metrics for JSON response
        metrics_by_slot = {} # slot_id -> { student_id -> metrics_dict }
        correlations_by_slot = {} # slot_id -> { metric_name: {r, p, n} }

        # Pre-fetch slot grades for all attempts
        slot_grades = QuizSlotGrade.objects.filter(
            attempt_slot__attempt__in=attempts
        ).values(
            'attempt_slot__slot_id',
            'attempt_slot__attempt__student_identifier',
        ).annotate(
            score=Coalesce(Sum('items__selected_level__points'), 0.0)
        )
        
        grades_map = defaultdict(dict) # slot_id -> { student_id -> score }
        for g in slot_grades:
            grades_map[g['attempt_slot__slot_id']][g['attempt_slot__attempt__student_identifier']] = g['score']

        
        # Aggregate ALL interactions into one "Global" slot
        global_interactions = []
        global_metrics_by_student = defaultdict(list) # student_id -> list of metrics
        global_correlation_points = defaultdict(list) # metric_name -> list of {x, y, student_id}
        
        # We need to map attempt -> score (aggregated score for that attempt's slot?)
        # Actually correlation is usually: Metric vs Slot Score.
        # If we pool, we take (Metric for Attempt A, Score for Attempt A).
        
        # 1. Collect all interactions flat
        for slot_id, interactions in interactions_by_slot.items():
            for i in interactions:
                # Add slot label to metadata for reference if needed
                i['metadata']['original_slot'] = slot_map.get(slot_id, 'Unknown')
                i['metadata']['original_slot_id'] = slot_id
                global_interactions.append(i)

            # 2. Calculate metrics per slot/student and collect for aggregation
            by_student = defaultdict(list)
            for i in interactions:
                by_student[i['student_id']].append(i)
            
            for student_id, student_interactions in by_student.items():
                typing_events = [i for i in student_interactions if i['event_type'] == 'typing']
                if not typing_events: continue
                
                typing_events.sort(key=lambda x: x['created_at'])
                attempt_start = student_interactions[0]['attempt_started_at']
                
                metrics = calculate_typing_metrics(typing_events, attempt_start)
                # metrics tuple: (ipl, rr, burst, wpm, active_time, fwc)
                
                # Store for student average
                global_metrics_by_student[student_id].append(metrics)
                
                # Store for correlation (if score exists)
                if student_id in grades_map[slot_id]:
                    score = grades_map[slot_id][student_id]
                    # Append point (val, score, student_id)
                    global_correlation_points['ipl'].append((metrics[0], score, student_id))
                    global_correlation_points['revision_ratio'].append((metrics[1], score, student_id))
                    global_correlation_points['burstiness'].append((metrics[2], score, student_id))
                    global_correlation_points['wpm'].append((metrics[3], score, student_id))

        # 3. Calculate Average Metrics per Student (for "Student Metrics" display)
        final_metrics = {}
        for student_id, m_list in global_metrics_by_student.items():
            count = len(m_list)
            if count > 0:
                # Average indices 0 to 5
                avg_m = [sum(x)/count for x in zip(*m_list)]
                final_metrics[student_id] = {
                    'ipl': avg_m[0],
                    'revision_ratio': avg_m[1],
                    'burstiness': avg_m[2],
                    'wpm': avg_m[3],
                    'active_time': avg_m[4],
                    'word_count': avg_m[5]
                }

        # 4. Compute Correlations (Pooled)
        final_correlations = {}
        
        def compute_stats(name, data_points):
            # data_points: list of (metric_val, score, sid)
            if len(data_points) < 2: return None
            x = [p[0] for p in data_points]
            y = [p[1] for p in data_points]
            ids = [p[2] for p in data_points]
            
            if len(set(x)) <= 1 or len(set(y)) <= 1: return None
            
            try:
                p_r = sp_stats.pearsonr(x, y).statistic
                p_p = sp_stats.pearsonr(x, y).pvalue
                s_stat = sp_stats.spearmanr(x, y)
                s_rho = s_stat.correlation
                s_p = s_stat.pvalue
                
                if math.isnan(p_r) or math.isnan(p_p): return None
                
                points = [{'x': round(xv, 4), 'y': round(yv, 2), 'student_id': sid} for xv, yv, sid in zip(x, y, ids)]
                
                return {
                    'name': name,
                    'count': len(x),
                    'pearson_r': round(p_r, 4),
                    'pearson_p': round(p_p, 5),
                    'spearman_rho': round(s_rho, 4) if not math.isnan(s_rho) else None,
                    'spearman_p': round(s_p, 5) if not math.isnan(s_p) else None,
                    'points': points
                }
            except:
                return None

        final_correlations['ipl'] = compute_stats("Initial Planning Latency vs Score", global_correlation_points['ipl'])
        final_correlations['revision_ratio'] = compute_stats("Revision Ratio vs Score", global_correlation_points['revision_ratio'])
        final_correlations['burstiness'] = compute_stats("Burstiness vs Score", global_correlation_points['burstiness'])
        final_correlations['wpm'] = compute_stats("Text Production Rate (WPM) vs Score", global_correlation_points['wpm'])

        # Return single Virtual Slot
        # Sort interactions by date (or we could keep them mixed, but time sort is better for overall timeline)
        # Note: Position is relative 0-100%. If we sort by Absolute time, the timeline component
        # will currently use 'position' which is relative percent.
        # If we have multiple slots, their 0-100% will overlay.
        # This is expected for "Composite" view.
        
        global_slot = {
            'id': 'global-all',
            'label': 'All Quizzes (Global Aggregation)',
            'response_type': 'open_text', # Assumed dominant type
            'interactions': global_interactions,
            'metrics': final_metrics,
            'metric_correlations': final_correlations
        }

        return Response([global_slot])
