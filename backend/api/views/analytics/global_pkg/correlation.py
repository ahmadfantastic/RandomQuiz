import numpy as np
from scipy import stats as sp_stats, stats
from django.db.models import Sum
from django.db.models.functions import Coalesce

from rest_framework.views import APIView
from rest_framework.response import Response

from accounts.models import ensure_instructor
from accounts.permissions import IsInstructor
from problems.models import ProblemBank
from quizzes.models import (
    Quiz, QuizAttempt, QuizAttemptSlot, 
    QuizRatingCriterion
)

class GlobalCorrelationAnalysisView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request):
        instructor = ensure_instructor(request.user)
        quizzes = Quiz.objects.filter(owner=instructor)

        # Global Score vs Rating Correlation Data
        global_score_points = {} 
        global_weighted_score_points = []
        
        # Global Score vs Time Correlation Data
        global_time_score_points = []
        
        # Global Score vs Word Count Correlation Data
        global_word_count_score_points = []
        
        # Global Time vs Word Count Correlation Data
        global_word_count_vs_time_points = []
        
        # Global Time vs Rating Correlation Data
        global_time_vs_rating_points = {} 
        global_weighted_time_vs_rating_points = []
        
        # Helper map for Bank Weights: BankID -> { InstructorCode -> Weight }
        bank_weights_cache = {}
        
        # Global Rating Rows for Inter-Criterion Correlation
        global_rating_rows = []
        
        global_criterion_orders = {}

        for quiz in quizzes:
            # Metadata
            quiz_criteria = QuizRatingCriterion.objects.filter(quiz=quiz).order_by('order')
            criterion_map = {} # quiz_crit_id -> instructor_crit_code
            criterion_names = {} # quiz_crit_id -> name 
            
            for qc in quiz_criteria:
                if qc.name not in global_score_points:
                    global_score_points[qc.name] = []
                    global_time_vs_rating_points[qc.name] = []
                
                if qc.name not in global_criterion_orders:
                    global_criterion_orders[qc.name] = qc.order
                else:
                    global_criterion_orders[qc.name] = min(global_criterion_orders[qc.name], qc.order)

                if qc.instructor_criterion_code:
                    criterion_map[qc.criterion_id] = qc.instructor_criterion_code
                    criterion_names[qc.criterion_id] = qc.name


            # --- Time Correlation Logic ---
            quiz_attempts = QuizAttempt.objects.filter(
                quiz=quiz,
                completed_at__isnull=False,
                started_at__isnull=False
            ).values('id', 'started_at', 'completed_at')
            
            attempt_scores_qs = QuizAttemptSlot.objects.filter(
                attempt__quiz=quiz,
                attempt__completed_at__isnull=False,
                grade__isnull=False
            ).values('attempt_id').annotate(
                total_score=Coalesce(Sum('grade__items__selected_level__points'), 0.0)
            )
            quiz_attempt_score_map = {item['attempt_id']: item['total_score'] for item in attempt_scores_qs}
            
            attempt_durations = {} # aid -> duration
            
            for attempt in quiz_attempts:
                attempt_id = attempt['id']
                score = quiz_attempt_score_map.get(attempt_id)
                
                if score is not None:
                    duration = (attempt['completed_at'] - attempt['started_at']).total_seconds() / 60.0
                    if duration > 0:  
                        global_time_score_points.append({'x': score, 'y': duration})
                        attempt_durations[attempt_id] = duration


            # --- Score & Time vs Rating Correlation Logic ---
            quiz_rating_slots = QuizAttemptSlot.objects.filter(
                attempt__quiz=quiz,
                attempt__completed_at__isnull=False,
                slot__response_type='rating',
                answer_data__ratings__isnull=False
            ).select_related('assigned_problem__problem_bank').values(
                'id', 'answer_data', 'attempt_id', 'assigned_problem__problem_bank__id'
            )
            
            for entry in quiz_rating_slots:
                aid = entry['attempt_id']
                score = quiz_attempt_score_map.get(aid)
                duration = attempt_durations.get(aid)
                
                if score is not None or duration is not None:
                    ratings = entry['answer_data'].get('ratings', {})
                    bank_id = entry['assigned_problem__problem_bank__id']
                    
                    if bank_id not in bank_weights_cache:
                        try:
                            bank = ProblemBank.objects.get(id=bank_id)
                            rubric = bank.get_rubric()
                            w_map = {c['id']: c.get('weight', 1) for c in rubric.get('criteria', [])}
                            bank_weights_cache[bank_id] = w_map
                        except Exception:
                            bank_weights_cache[bank_id] = {}
                            
                    current_bank_weights = bank_weights_cache.get(bank_id, {})
                    
                    w_sum = 0
                    w_total = 0
                    
                    # Also capture rows for Inter-Criterion Correlation
                    # Note: We need a mapping from ID -> Name to properly group rows globally
                    current_row = {}

                    for q_cid, val in ratings.items():
                        c_name = criterion_names.get(q_cid)
                        i_code = criterion_map.get(q_cid)
                        
                        try:
                            val_float = float(val)
                        except:
                            val_float = None

                        if c_name and val_float is not None:
                             if score is not None:
                                 global_score_points[c_name].append({'x': score, 'y': val_float})
                             if duration is not None:
                                 global_time_vs_rating_points[c_name].append({'x': duration, 'y': val_float})
                             
                             current_row[c_name] = val_float
                             
                        # Weighted Calc
                        if i_code and val_float is not None:
                            weight = current_bank_weights.get(i_code, 1) # Default to 1 if not found
                            w_sum += val_float * weight
                            w_total += weight
                    
                    if len(current_row) > 1:
                        global_rating_rows.append(current_row)

                    if w_total > 0:
                        weighted_avg = w_sum / w_total
                        if score is not None:
                            global_weighted_score_points.append({'x': score, 'y': weighted_avg})
                        if duration is not None:
                            global_weighted_time_vs_rating_points.append({'x': duration, 'y': weighted_avg})

            # --- Word Count Correlation Logic ---
            text_slots = quiz.slots.filter(response_type='open_text')
            if text_slots.exists():
                 valid_attempt_ids = list(quiz_attempt_score_map.keys())
                 
                 text_answers = QuizAttemptSlot.objects.filter(
                     attempt_id__in=valid_attempt_ids,
                     slot__in=text_slots
                 ).values('attempt_id', 'answer_data')
                 
                 attempt_word_counts = {aid: 0 for aid in valid_attempt_ids}
                 
                 for ans in text_answers:
                     aid = ans['attempt_id']
                     if ans['answer_data'] and 'text' in ans['answer_data']:
                         text = ans['answer_data']['text'] or ""
                         words = len(text.split())
                         if aid in attempt_word_counts:
                             attempt_word_counts[aid] += words
                 
                 for aid, wc in attempt_word_counts.items():
                     score = quiz_attempt_score_map.get(aid)
                     if score is not None:
                         global_word_count_score_points.append({'x': score, 'y': wc})
                         
                         if aid in attempt_durations:
                             duration = attempt_durations[aid]
                             global_word_count_vs_time_points.append({'x': duration, 'y': wc})


        # Helper to compute correlations
        def compute_global_correlations(points_map, global_weight_points, type_label):
             results = []
             # Individual Criteria
             # Sort keys
             sorted_keys = sorted(points_map.keys(), key=lambda x: global_criterion_orders.get(x, 999))
             
             for c_name in sorted_keys:
                 pts = points_map[c_name]
                 if len(pts) > 1:
                     xs = [p['x'] for p in pts]
                     ys = [p['y'] for p in pts]
                     
                     res = stats.spearmanr(xs, ys)
                     r_val = res.statistic if hasattr(res, 'statistic') else res.correlation
                     
                     results.append({
                         'criterion': c_name,
                         'r': r_val,
                         'p_value': res.pvalue,
                         'n': len(pts)
                     })
            
             # Weighted Score
             if len(global_weight_points) > 1:
                 xs = [p['x'] for p in global_weight_points]
                 ys = [p['y'] for p in global_weight_points]
                 
                 res_w = stats.spearmanr(xs, ys)
                 r_val_w = res_w.statistic if hasattr(res_w, 'statistic') else res_w.correlation
                 
                 results.append({
                     'criterion': 'Weighted Score',
                     'r': r_val_w,
                     'p_value': res_w.pvalue,
                     'n': len(global_weight_points)
                 })
             
             return results

        # 1. Score vs Rating
        score_correlation = compute_global_correlations(global_score_points, global_weighted_score_points, "Score vs Rating")

        # 2. Score vs Time (Just a single correlation, not per criterion really, but we can structure similar if needed)
        # But this is just [Score, Time].
        time_correlation = []
        if len(global_time_score_points) > 1:
            xs = [p['x'] for p in global_time_score_points]
            ys = [p['y'] for p in global_time_score_points]
            res_t = stats.spearmanr(xs, ys)
            rv = res_t.statistic if hasattr(res_t, 'statistic') else res_t.correlation
            time_correlation.append({
                'criterion': 'Total Quiz Score',
                'r': rv,
                'p_value': res_t.pvalue,
                'n': len(global_time_score_points)
            })
            
        # 3. Time vs Rating
        time_vs_rating_correlation = compute_global_correlations(global_time_vs_rating_points, global_weighted_time_vs_rating_points, "Time vs Rating")
        
        # 4. Score vs Word Count
        word_count_correlation = []
        if len(global_word_count_score_points) > 1:
            xs = [p['x'] for p in global_word_count_score_points]
            ys = [p['y'] for p in global_word_count_score_points]
            res_wc = stats.spearmanr(xs, ys)
            rv = res_wc.statistic if hasattr(res_wc, 'statistic') else res_wc.correlation
            word_count_correlation.append({
                'criterion': 'Total Word Count (Text Slots)',
                'r': rv,
                'p_value': res_wc.pvalue,
                'n': len(global_word_count_score_points)
            })

        # 5. Time vs Word Count
        word_count_vs_time_correlation = []
        if len(global_word_count_vs_time_points) > 1:
            xs = [p['x'] for p in global_word_count_vs_time_points]
            ys = [p['y'] for p in global_word_count_vs_time_points]
            res_wct = stats.spearmanr(xs, ys)
            rv = res_wct.statistic if hasattr(res_wct, 'statistic') else res_wct.correlation
            word_count_vs_time_correlation.append({
                'criterion': 'Word Count vs Time',
                'r': rv,
                'p_value': res_wct.pvalue,
                'n': len(global_word_count_vs_time_points)
            })

        # 6. Inter-Criterion Correlation (Spearman Matrix)
        inter_criterion_correlation = None
        if global_rating_rows:
             # Identify all criteria found in rows
             matrix_c_names = sorted(list(set().union(*(r.keys() for r in global_rating_rows))), key=lambda x: global_criterion_orders.get(x, 999))
             
             if len(matrix_c_names) > 1:
                 corr_matrix = []
                 n_criteria = len(matrix_c_names)
                 
                 for i in range(n_criteria):
                     row_res = []
                     c_i = matrix_c_names[i]
                     
                     for j in range(n_criteria):
                         c_j = matrix_c_names[j]
                         
                         xs = []
                         ys = []
                         for row in global_rating_rows:
                             if c_i in row and c_j in row:
                                 xs.append(row[c_i])
                                 ys.append(row[c_j])
                         
                         if len(xs) >= 2:
                             try:
                                 r_res = stats.spearmanr(xs, ys)
                                 r_val = r_res.statistic if hasattr(r_res, 'statistic') else r_res.correlation
                                 row_res.append({
                                     'r': round(r_val, 4),
                                     'p': round(r_res.pvalue, 5),
                                     'n': len(xs)
                                 })
                             except:
                                 row_res.append(None)
                         else:
                             row_res.append(None)
                     
                     corr_matrix.append(row_res)
                 
                 inter_criterion_correlation = {
                     'criteria': matrix_c_names,
                     'matrix': corr_matrix
                 }


        return Response({
            'score_correlation': score_correlation,
            'time_correlation': time_correlation,
            'time_vs_rating_correlation': time_vs_rating_correlation,
            'word_count_correlation': word_count_correlation,
            'word_count_vs_time_correlation': word_count_vs_time_correlation,
            'inter_criterion_correlation': inter_criterion_correlation
        })
