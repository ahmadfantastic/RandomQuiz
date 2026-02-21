import numpy as np
from scipy import stats as sp_stats, stats, optimize
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

def compute_cfa_one_factor(data_rows, criterion_map_order):
    """
    Performs a 1-Factor CFA (Confirmatory Factor Analysis) using Maximum Likelihood estimation.
    Tests the 'Halo Effect' hypothesis (single latent factor).
    
    Args:
        data_rows: List of dicts, each containing ratings for criteria {crit_name: val, ...}
        criterion_map_order: List of criterion names in order.
    
    Returns:
        dict: CFA results including fit indices and loadings, or None if failed.
    """
    # 1. Prepare Data (Listwise Deletion for consistent Covariance Matrix)
    # Filter rows that have ALL target criteria
    clean_rows = []
    for row in data_rows:
        if all(c in row and row[c] is not None for c in criterion_map_order):
            clean_rows.append([row[c] for c in criterion_map_order])
            
    n_samples = len(clean_rows)
    p_vars = len(criterion_map_order)
    
    # Requirements
    if p_vars < 3 or n_samples < 20: 
        return None

    X = np.array(clean_rows)
    
    # 2. Compute Observed Correlation Matrix (S)
    try:
        S = np.corrcoef(X, rowvar=False)
    except Exception:
        return None
        
    if np.any(np.isnan(S)) or np.any(np.isinf(S)):
        return None

    # 3. Define ML Discrepancy Function
    def get_sigma(params):
        lam = params[:p_vars].reshape(-1, 1)
        psi_diag = params[p_vars:]
        psi_diag = np.maximum(psi_diag, 0.001) 
        Sigma = np.dot(lam, lam.T) + np.diag(psi_diag)
        return Sigma

    def objective(params):
        Sigma = get_sigma(params)
        try:
            sign, logdet_sigma = np.linalg.slogdet(Sigma)
            if sign <= 0: return 1e10
            Sigma_inv = np.linalg.inv(Sigma)
            trace_term = np.trace(np.dot(S, Sigma_inv))
            return logdet_sigma + trace_term
        except np.linalg.LinAlgError:
            return 1e10

    initial_guess = np.concatenate([np.full(p_vars, 0.5), np.full(p_vars, 0.5)])
    bounds = [(None, None)] * p_vars + [(0.001, None)] * p_vars
    
    # Optimize
    res = optimize.minimize(objective, initial_guess, method='L-BFGS-B', bounds=bounds)
    
    if not res.success:
        return None
        
    # 4. Calculate Fit Indices
    final_params = res.x
    Sigma_hat = get_sigma(final_params)
    
    sign_s, logdet_s = np.linalg.slogdet(S)
    sign_sigma, logdet_sigma = np.linalg.slogdet(Sigma_hat)
    
    if sign_s <= 0 or sign_sigma <= 0:
        return None
        
    try:
        Sigma_inv = np.linalg.inv(Sigma_hat)
        trace_term = np.trace(np.dot(S, Sigma_inv))
        f_min = logdet_sigma - logdet_s + trace_term - p_vars
        f_min = max(0, f_min)
    except:
        return None

    chi_square = (n_samples - 1) * f_min
    df = (p_vars * (p_vars + 1) / 2) - (2 * p_vars)
    
    rmsea = 0
    if df > 0:
        rmsea = np.sqrt(max(0, chi_square - df) / ((n_samples - 1) * df))

    # CFI
    f_null = -logdet_s 
    chi_null = (n_samples - 1) * f_null
    df_null = (p_vars * (p_vars + 1) / 2) - p_vars 
    
    cfi = 1.0
    if (chi_null - df_null) > 0:
        cfi = 1 - max(0, chi_square - df) / max(0, chi_null - df_null)
    
    loadings = final_params[:p_vars]
    loadings_list = []
    for idx, c_name in enumerate(criterion_map_order):
        loadings_list.append({
            'criterion': c_name,
            'loading': round(float(loadings[idx]), 3)
        })
        
    return {
        'n_samples': n_samples,
        'fit_indices': {
            'chi_square': round(chi_square, 2),
            'df': int(df),
            'rmsea': round(rmsea, 3),
            'cfi': round(cfi, 3)
        },
        'loadings': loadings_list
    }

class GlobalCorrelationAnalysisView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request):
        instructor = ensure_instructor(request.user)
        quizzes = Quiz.objects.filter(owner=instructor)

        # Global Score vs Rating Correlation Data
        global_score_points = {} 
        
        # Global Score vs Time Correlation Data
        global_time_score_points = []
        
        # Global Score vs Word Count Correlation Data
        global_word_count_score_points = []
        
        # Global Time vs Word Count Correlation Data
        global_word_count_vs_time_points = []
        
        # Global Time vs Rating Correlation Data
        global_time_vs_rating_points = {} 
        
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
            
            # DEBUG RAW
            # base_qs removed debug
            
            quiz_rating_slots = QuizAttemptSlot.objects.filter(
                attempt__quiz=quiz,
                attempt__completed_at__isnull=False,
                slot__response_type='rating',
            ).select_related('assigned_problem__problem_bank').values(
                'id', 'answer_data', 'attempt_id', 'assigned_problem__problem_bank__id'
            )
            

            
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
                
                # Calc duration regardless of score
                duration = (attempt['completed_at'] - attempt['started_at']).total_seconds() / 60.0
                if duration > 0:
                     attempt_durations[attempt_id] = duration
                
                if score is not None:
                    if duration > 0:  
                        global_time_score_points.append({'x': score, 'y': duration})


            # --- Score & Time vs Rating Correlation Logic ---
            quiz_rating_slots = QuizAttemptSlot.objects.filter(
                attempt__quiz=quiz,
                attempt__completed_at__isnull=False,
                slot__response_type='rating',
            ).select_related('assigned_problem__problem_bank').values(
                'id', 'answer_data', 'attempt_id', 'assigned_problem__problem_bank__id'
            )
            
            for entry in quiz_rating_slots:
                aid = entry['attempt_id']
                score = quiz_attempt_score_map.get(aid)
                duration = attempt_durations.get(aid)
                
                if True:
                    ratings = entry['answer_data'].get('ratings', {})
                    bank_id = entry['assigned_problem__problem_bank__id']

                    
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
                             # if score is not None:
                             #     global_score_points[c_name].append({'x': score, 'y': val_float})
                             # if duration is not None:
                             #     global_time_vs_rating_points[c_name].append({'x': duration, 'y': val_float})
                             
                             global_score_points[c_name].append({'x': score or 0, 'y': val_float}) # safe append
                             
                             current_row[c_name] = val_float
                             
                    if len(current_row) > 1:
                        global_rating_rows.append(current_row)

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
        def compute_global_correlations(points_map, type_label):
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
                     if np.isnan(r_val): r_val = None
                     
                     # Calculate Pearson
                     try:
                         pres = stats.pearsonr(xs, ys)
                         p_r_val = pres.statistic
                         if np.isnan(p_r_val): p_r_val = None
                         p_p_val = pres.pvalue
                         if np.isnan(p_p_val): p_p_val = None
                     except:
                         p_r_val = None
                         p_p_val = None

                     results.append({
                         'name': c_name, # Frontend uses 'name'
                         'criterion': c_name,
                         'spearman_rho': round(r_val, 4) if r_val is not None else None,
                         'spearman_p': round(res.pvalue, 5) if not np.isnan(res.pvalue) else None,
                         'pearson_r': round(p_r_val, 4) if p_r_val is not None else None,
                         'pearson_p': round(p_p_val, 5) if p_p_val is not None else None,
                         'count': len(pts),
                         'points': pts
                     })
            

             
             return results

        # 1. Score vs Rating
        score_correlation = compute_global_correlations(global_score_points, "Score vs Rating")

        # 2. Score vs Time (Just a single correlation, not per criterion really, but we can structure similar if needed)
        # But this is just [Score, Time].
        # 2. Score vs Time
        time_correlation = []
        if len(global_time_score_points) > 1:
            xs = [p['x'] for p in global_time_score_points]
            ys = [p['y'] for p in global_time_score_points]
            res_t = stats.spearmanr(xs, ys)
            rv = res_t.statistic if hasattr(res_t, 'statistic') else res_t.correlation
            
            try:
                pres = stats.pearsonr(xs, ys)
                pr = pres.statistic
                pp = pres.pvalue
            except:
                pr, pp = None, None

            time_correlation.append({
                'name': 'Total Quiz Score',
                'criterion': 'Total Quiz Score',
                'spearman_rho': round(rv, 4) if rv is not None and not np.isnan(rv) else None,
                'spearman_p': round(res_t.pvalue, 5) if not np.isnan(res_t.pvalue) else None,
                'pearson_r': round(pr, 4) if pr is not None else None,
                'pearson_p': round(pp, 5) if pp is not None else None,
                'count': len(global_time_score_points),
                'points': global_time_score_points
            })
            
        # 3. Time vs Rating
        time_vs_rating_correlation = compute_global_correlations(global_time_vs_rating_points, "Time vs Rating")
        
        # 4. Score vs Word Count
        word_count_correlation = []
        if len(global_word_count_score_points) > 1:
            xs = [p['x'] for p in global_word_count_score_points]
            ys = [p['y'] for p in global_word_count_score_points]
            res_wc = stats.spearmanr(xs, ys)
            rv = res_wc.statistic if hasattr(res_wc, 'statistic') else res_wc.correlation
            
            try:
                pres = stats.pearsonr(xs, ys)
                pr = pres.statistic
                pp = pres.pvalue
            except:
                pr, pp = None, None

            word_count_correlation.append({
                'name': 'Total Word Count',
                'criterion': 'Total Word Count (Text Slots)',
                'spearman_rho': round(rv, 4),
                'spearman_p': round(res_wc.pvalue, 5),
                'pearson_r': round(pr, 4) if pr is not None else None,
                'pearson_p': round(pp, 5) if pp is not None else None,
                'count': len(global_word_count_score_points),
                'points': global_word_count_score_points
            })

        # 5. Time vs Word Count
        word_count_vs_time_correlation = []
        if len(global_word_count_vs_time_points) > 1:
            xs = [p['x'] for p in global_word_count_vs_time_points]
            ys = [p['y'] for p in global_word_count_vs_time_points]
            res_wct = stats.spearmanr(xs, ys)
            rv = res_wct.statistic if hasattr(res_wct, 'statistic') else res_wct.correlation
            
            try:
                pres = stats.pearsonr(xs, ys)
                pr = pres.statistic
                pp = pres.pvalue
            except:
                pr, pp = None, None

            word_count_vs_time_correlation.append({
                'name': 'Word Count vs Time',
                'criterion': 'Word Count vs Time',
                'spearman_rho': round(rv, 4),
                'spearman_p': round(res_wct.pvalue, 5),
                'pearson_r': round(pr, 4) if pr is not None else None,
                'pearson_p': round(pp, 5) if pp is not None else None,
                'count': len(global_word_count_vs_time_points),
                'points': global_word_count_vs_time_points
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
                                 if np.isnan(r_val): r_val = None
                                 
                                 row_res.append({
                                     'r': round(r_val, 4) if r_val is not None else None,
                                     'p': round(r_res.pvalue, 5) if not np.isnan(r_res.pvalue) else None,
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


        # 7. CFA
        cfa_results = None
        if global_rating_rows:
             matrix_c_names = sorted(list(set().union(*(r.keys() for r in global_rating_rows))), key=lambda x: global_criterion_orders.get(x, 999))
             if len(matrix_c_names) >= 3:
                 cfa_results = compute_cfa_one_factor(global_rating_rows, matrix_c_names)

        return Response({
            'score_correlation': score_correlation,
            'time_correlation': time_correlation,
            'time_vs_rating_correlation': time_vs_rating_correlation,
            'word_count_correlation': word_count_correlation,
            'word_count_vs_time_correlation': word_count_vs_time_correlation,
            'inter_criterion_correlation': inter_criterion_correlation,
            'factor_analysis': cfa_results
        })
