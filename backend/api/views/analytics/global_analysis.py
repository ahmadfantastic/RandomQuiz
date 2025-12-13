import numpy as np
import warnings
import math
from statistics import mean
from collections import defaultdict
from scipy import stats as sp_stats, stats

from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum
from django.db.models.functions import Coalesce

from accounts.models import ensure_instructor
from accounts.permissions import IsInstructor
from problems.models import ProblemBank, InstructorProblemRating
from quizzes.models import (
    Quiz, QuizAttempt, QuizSlot, QuizAttemptSlot, 
    QuizRatingCriterion, QuizRatingScaleOption, 
    QuizAttemptInteraction, QuizSlotGrade
)
from .utils import (
    calculate_weighted_kappa, calculate_average_nearest, 
    calculate_typing_metrics
)
from .kappa import quadratic_weighted_kappa
class GlobalAnalysisView(APIView):
    permission_classes = [IsInstructor]

    def update_global_criteria_data(self, global_data, criterion, y1, y2, scale):
        if criterion not in global_data:
            global_data[criterion] = {'y1': [], 'y2': [], 'scale': scale}
        
        global_data[criterion]['y1'].extend(y1)
        global_data[criterion]['y2'].extend(y2)
        if not global_data[criterion]['scale'] and scale:
             global_data[criterion]['scale'] = scale

    def get(self, request):
        instructor = ensure_instructor(request.user)
        
        # Analyze all banks owned by instructor
        banks = ProblemBank.objects.filter(owner=instructor)
        
        results = []
        
        # Accumulate data for global criteria analysis (across ALL banks)
        # Structure: criterion_name -> { 'y1': [], 'y2': [], 'scale': [] }
        global_criteria_data = {}
        
        # Accumulate data by Problem Group
        # Structure: group_name -> { criterion: [values], 'weighted_score': [values], 'total_max_score': [values] }
        group_stats = {}
        
        # Temporary storage for aggregating scores per problem
        # pid -> { 'group': group_name, 'criteria': { c_name: [scores] } }
        all_problem_scores = {}
        
        for bank in banks:
            # Temporary storage for aggregating scores per problem within this bank
            problem_scores = {}

            # Similar logic to ProblemBankAnalysisView but summarized
            ratings = InstructorProblemRating.objects.filter(
                problem__problem_bank=bank
            ).select_related('problem').prefetch_related('entries', 'entries__scale_option', 'entries__criterion')
            
            if not ratings.exists():
                continue
                
            # Calculate total max score for this bank
            rubric = bank.get_rubric()
            rubric_criteria = {c['id']: c['name'] for c in rubric.get('criteria', [])}
            scale = rubric.get('scale', [])
            criteria_list = rubric.get('criteria', [])
            
            # Map criterion name to weight
            criteria_weights = {c['name']: c.get('weight', 1) for c in criteria_list}
            
            total_max_score = 0
            total_weight = 0
            if scale and criteria_list:
                max_val = max(s['value'] for s in scale)
                # Max score = max_scale_val * sum(weights)
                total_weight = sum(criteria_weights.values())
                total_max_score = max_val * total_weight

            c_totals = {}
            c_counts = {}
            
            # Also calculate IRR if possible
            # Need to reconstruct the data structure
            data = {} # pid -> { rater -> { c -> val } }
            raters = set()
            
            for r in ratings:
                pid = r.problem_id
                iid = r.instructor_id
                raters.add(iid)
                p_group = r.problem.group

                if pid not in data:
                    data[pid] = {}
                if iid not in data[pid]:
                    data[pid][iid] = {}
                
                for entry in r.entries.all():
                    c_id = entry.criterion.criterion_id
                    c_name = rubric_criteria.get(c_id, c_id)
                    if pid not in problem_scores:
                        problem_scores[pid] = {
                            'group': p_group if p_group else "Ungrouped",
                            'max_score': total_max_score,
                            'total_weight': total_weight,
                            'weights': criteria_weights,
                            'criteria': {}
                        }

                    if c_name not in problem_scores[pid]['criteria']:
                        problem_scores[pid]['criteria'][c_name] = []
                    problem_scores[pid]['criteria'][c_name].append(entry.scale_option.value)

                    if c_name not in c_totals:
                        c_totals[c_name] = 0.0
                        c_counts[c_name] = 0

                    c_totals[c_name] += entry.scale_option.value
                    c_counts[c_name] += 1
                    
                    data[pid][iid][c_name] = entry.scale_option.value

            
            # Calculate total max score
            scale = rubric.get('scale', [])
            criteria_list = rubric.get('criteria', [])
            total_max_score = 0
            if scale and criteria_list:
                max_val = max(s['value'] for s in scale)
                total_max_score = max_val * len(criteria_list)
                max_val = max(s['value'] for s in scale)
                total_max_score = max_val * len(criteria_list)
            
            means = {c: c_totals[c]/c_counts[c] for c in c_totals}

            # Add weighted score (Problem-First Approach)
            # Calculate weighted score for EACH problem, then average them.
            bank_problem_weighted_scores = []
            
            # Let's iterate `data` keys (pids for this bank) and check `problem_scores`.
            for pid in data.keys():
                if pid in problem_scores:
                    p_data = problem_scores[pid]
                    
                    # Calculate per-problem weighted score
                    p_w_sum = 0
                    p_means = []
                    
                    current_p_weights = p_data.get('weights', {})
                    current_total_weight = p_data.get('total_weight', 0)
                    
                    # Calculate mean for each criterion
                    dynamic_total_weight = 0
                    for c_name, c_vals in p_data.get('criteria', {}).items():
                        if c_vals:
                            avg = sum(c_vals) / len(c_vals)
                            w = current_p_weights.get(c_name, 1)
                            p_w_sum += (avg * w)
                            dynamic_total_weight += w
                    
                    if dynamic_total_weight > 0:
                        bank_problem_weighted_scores.append(p_w_sum / dynamic_total_weight)

            if bank_problem_weighted_scores:
                means['weighted_score'] = sum(bank_problem_weighted_scores) / len(bank_problem_weighted_scores)
            else:
                means['weighted_score'] = 0.0

            # IRR
            irr = {}
            raters_list = list(raters)

            # Global Analysis Overall Kappa for this bank
            if len(raters_list) > 1:
                all_y1_global = []
                all_y2_global = []
                for i in range(len(raters_list)):
                    for j in range(i+1, len(raters_list)):
                        r1 = raters_list[i]
                        r2 = raters_list[j]
                        
                        # Gather ALL ratings for this pair across all criteria
                        pair_y1 = []
                        pair_y2 = []
                        
                        for c in means.keys():
                            for pid in data:
                                v1 = data[pid].get(r1, {}).get(c)
                                v2 = data[pid].get(r2, {}).get(c)
                                if v1 is not None and v2 is not None:
                                    pair_y1.append(v1)
                                    pair_y2.append(v2)
                        
                        all_y1_global.extend(pair_y1)
                        all_y2_global.extend(pair_y2)
                        
                        # Add to global criteria accumulators
                        if scale:
                             scale_vals = [s['value'] for s in scale]
                        else:
                             scale_vals = None
                             
                        # Re-iterate to separate by criterion for proper aggregation
                        for c in means.keys():
                            c_y1 = []
                            c_y2 = []
                            for pid in data:
                                v1 = data[pid].get(r1, {}).get(c)
                                v2 = data[pid].get(r2, {}).get(c)
                                if v1 is not None and v2 is not None:
                                    c_y1.append(v1)
                                    c_y2.append(v2)
                            
                            if c_y1:
                                if c not in global_criteria_data:
                                    global_criteria_data[c] = {'y1': [], 'y2': [], 'scale': scale_vals}
                                self.update_global_criteria_data(global_criteria_data, c, c_y1, c_y2, scale_vals)
                
                overall_kappas = []
                for i in range(len(raters_list)):
                    for j in range(i+1, len(raters_list)):
                        r1 = raters_list[i]
                        r2 = raters_list[j]
                        p_y1 = []
                        p_y2 = []
                        for c in means.keys():
                             for pid in data:
                                v1 = data[pid].get(r1, {}).get(c)
                                v2 = data[pid].get(r2, {}).get(c)
                                if v1 is not None and v2 is not None:
                                    p_y1.append(v1)
                                    p_y2.append(v2)
                        
                        if len(p_y1) >= 5:
                            scale_vals = [s['value'] for s in scale] if scale else None
                            k = calculate_weighted_kappa(
                                p_y1, p_y2, 
                                all_categories=scale_vals, 
                                label=f"Global Analysis - Bank {bank.name} - Overall"
                            )
                            overall_kappas.append(k)
                
                if overall_kappas:
                    irr['Overall'] = np.mean(overall_kappas)

            # Collect criteria values for ANOVA
            # We must average between raters for the same problem before adding to the ANOVA list
            criteria_values = {}
            for pid, p_data in problem_scores.items():
                 for c_name, scores in p_data['criteria'].items():
                      if scores:
                           avg = sum(scores) / len(scores)
                           if c_name not in criteria_values: 
                                criteria_values[c_name] = []
                           criteria_values[c_name].append(avg)

                 # Add weighted score for ANOVA
                 p_w_sum = 0
                 d_tot_w = 0
                 current_p_weights = p_data.get('weights', {})
                 for c_name, scores in p_data['criteria'].items():
                      if scores:
                           avg = sum(scores)/len(scores)
                           w = current_p_weights.get(c_name, 1)
                           p_w_sum += avg * w
                           d_tot_w += w
                 
                 if d_tot_w > 0:
                      w_score = p_w_sum / d_tot_w
                      if 'weighted_score' not in criteria_values:
                           criteria_values['weighted_score'] = []
                      criteria_values['weighted_score'].append(w_score)

            results.append({
                'id': bank.id,
                'name': bank.name,
                'means': means,
                'total_max_score': total_max_score,
                'inter_rater_reliability': irr,
                'criteria_values': criteria_values
            })
            
            # Populate group_stats from problem_scores
            for pid, p_data in problem_scores.items():
                group = p_data['group']
                if group not in group_stats:
                    group_stats[group] = {}
                
                for c_name, scores in p_data['criteria'].items():
                    if scores:
                        # Average the scores for this problem (across raters)
                        # Use float to ensure no rounding up/integer division issues
                        avg_score = float(sum(scores)) / len(scores)
                        
                        if c_name not in group_stats[group]:
                            group_stats[group][c_name] = []
                        group_stats[group][c_name].append(avg_score)
                
                # Add weighted score to group stats
                # Recalculate per-problem weighted score locally
                p_w_sum = 0.0
                d_tot_w = 0.0
                current_p_weights = p_data.get('weights', {})
                for c_name, scores in p_data['criteria'].items():
                    if scores:
                        avg = float(sum(scores)) / len(scores)
                        w = float(current_p_weights.get(c_name, 1))
                        p_w_sum += avg * w
                        d_tot_w += w
                
                if d_tot_w > 0:
                    w_score = p_w_sum / d_tot_w
                    if 'weighted_score' not in group_stats[group]:
                        group_stats[group]['weighted_score'] = []
                    group_stats[group]['weighted_score'].append(w_score)
                
            # Accumulate to global problem scores
            all_problem_scores.update(problem_scores)

        criteria_order_map = {}

        if banks.exists():
            # Use the first bank's rubric for ordering
            first_rubric = banks.first().get_rubric()
            for idx, c in enumerate(first_rubric.get('criteria', [])):
                criteria_order_map[c['name']] = idx
                
        all_criteria = set()
        for res in results:
            all_criteria.update(res['means'].keys())
            
        # Sort all_criteria based on the collected order
        sorted_criteria = sorted([c for c in all_criteria], key=lambda x: (criteria_order_map.get(x, 999), x))

        anova_results = []
        
        for cid in sorted_criteria:
            groups = []
            group_names = []
            
            for res in results:
                if cid in res['criteria_values'] and len(res['criteria_values'][cid]) > 1:
                    groups.append(res['criteria_values'][cid])
                    group_names.append(res['name'])
            
            if len(groups) > 1:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        f_stat, p_val = stats.f_oneway(*groups)
                except Exception:
                    f_stat, p_val = None, None

                if f_stat is not None and (np.isinf(f_stat) or np.isnan(f_stat)):
                    f_stat = None
                if p_val is not None and (np.isinf(p_val) or np.isnan(p_val)):
                    p_val = None
                
                significant = p_val < 0.05 if p_val is not None else False
                tukey_results = []

                if significant and len(groups) > 2:
                    try:
                        # Perform Tukey's HSD
                        res = stats.tukey_hsd(*groups)
                        # res.pvalue is a matrix where [i, j] is p-value between group i and j
                        # group_names maps to indices
                        matrix = res.pvalue
                        for i in range(len(group_names)):
                            for j in range(i + 1, len(group_names)):
                                if matrix[i, j] < 0.05:
                                    tukey_results.append(f"{group_names[i]} vs {group_names[j]} (p={matrix[i, j]:.3f})")
                    except Exception:
                        pass # Fallback if tukey fails

                anova_results.append({
                    'criterion_id': 'Weighted Score' if cid == 'weighted_score' else cid,
                    'f_stat': float(f_stat) if f_stat is not None else None,
                    'p_value': float(p_val) if p_val is not None else None,
                    'significant': significant,
                    'banks_included': group_names,
                    'tukey_results': tukey_results
                })


        # Calculate Global Criteria Kappas
        global_criteria_results = []
        for c_name, c_data in global_criteria_data.items():
            if len(c_data['y1']) >= 5:
                k = calculate_weighted_kappa(
                    c_data['y1'], c_data['y2'], 
                    all_categories=c_data['scale'], 
                    label=f"Global Criteria Analysis - {c_name}"
                )
                # T-test Calculation if exactly 2 groups
                t_test_result = None
                if len(group_stats) == 2:
                    groups = list(group_stats.keys())
                    g1 = groups[0]
                    g2 = groups[1]
                    # Get values for this criterion from each group
                    vals1 = group_stats[g1].get(c_name, [])
                    vals2 = group_stats[g2].get(c_name, [])
                    
                    if len(vals1) > 1 and len(vals2) > 1:
                        # unequal variance (Welch's)
                        try:
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore", RuntimeWarning)
                                t_stat, p_val_2 = stats.ttest_ind(vals1, vals2, equal_var=False)
                        except Exception:
                            t_stat, p_val_2 = None, None
                            
                        # 1-tailed: p/2 if t-stat assumption matches, but user usually just wants p/2
                        t_test_result = {
                            'p_2_tailed': p_val_2,
                            'p_1_tailed': p_val_2 / 2 if p_val_2 is not None else None,
                            't_stat': t_stat
                        }

                global_criteria_results.append({
                    'criterion': c_name,
                    'kappa': k,
                    'n': len(c_data['y1']),
                    'mean': np.mean(c_data['y1'] + c_data['y2']),
                    't_test': t_test_result
                })

        
        # Sort by criterion order
        global_criteria_results.sort(key=lambda x: (criteria_order_map.get(x['criterion'], 999), x['criterion']))


        # Calculate Overall Stats for Criteria Table (Pooled)
        all_criteria_y1 = []
        all_criteria_y2 = []
        all_criteria_scale = [] # Scale usually constant, but let's grab one valid scale
        
        for c_data in global_criteria_data.values():
            all_criteria_y1.extend(c_data['y1'])
            all_criteria_y2.extend(c_data['y2'])
            if not all_criteria_scale and c_data['scale']:
                all_criteria_scale = c_data['scale']
        
        # Calculate Overall Stats
        overall_criteria_stats = None
        if all_problem_scores:
            # Weighted Score Calculation (Sum of criteria averages per problem)
            # all_problem_scores [pid] -> criteria -> avg_score
            
            group_weighted_vals = {}
            all_weighted_vals = []
            
            for pid, p_data in all_problem_scores.items():
                # Let's recalculate per-problem weighted score correctly:
                current_p_weights = p_data.get('weights', {})
                current_p_weighted_sum = 0
                
                # Iterate items to get c_name
                dynamic_total_weight = 0
                for c_name, c_vals in p_data.get('criteria', {}).items():
                    if c_vals:
                         avg_val = sum(c_vals)/len(c_vals)
                         weight = current_p_weights.get(c_name, 1)
                         current_p_weighted_sum += (avg_val * weight)
                         dynamic_total_weight += weight
                
                if p_data.get('criteria'): # if any criteria existed
                    p_w_score = current_p_weighted_sum

                    # Normalize by dynamic total weight if available (Weighted Average Rating)
                    if dynamic_total_weight > 0:
                        p_w_score = p_w_score / dynamic_total_weight
                    else:
                        p_w_score = 0.0 # fallback

                    group = p_data['group']

                    if group not in group_weighted_vals:
                         group_weighted_vals[group] = []
                    group_weighted_vals[group].append(p_w_score)
                    all_weighted_vals.append(p_w_score)


            overall_n = len(all_weighted_vals)
            overall_mean = np.mean(all_weighted_vals) if all_weighted_vals else 0.0
            
            # Group Means for Weighted Score
            group_means = {g: np.mean(vals) for g, vals in group_weighted_vals.items()}

            # Overall T-Test: Pool all rating values for G1 vs G2
            overall_t_test = None
            if len(group_weighted_vals) == 2:
                groups = list(group_weighted_vals.keys())
                g1_vals = group_weighted_vals[groups[0]]
                g2_vals = group_weighted_vals[groups[1]]
                
                if len(g1_vals) > 1 and len(g2_vals) > 1:
                     try:
                         with warnings.catch_warnings():
                             warnings.simplefilter("ignore", RuntimeWarning)
                             t_stat, p_val_2 = stats.ttest_ind(g1_vals, g2_vals, equal_var=False)
                     except Exception:
                         t_stat, p_val_2 = None, None

                     overall_t_test = {
                        'p_2_tailed': p_val_2,
                        'p_1_tailed': p_val_2 / 2 if p_val_2 is not None else None,
                        't_stat': t_stat
                     }

            overall_criteria_stats = {
                'kappa': None, # Hide Kappa
                'n': overall_n,
                'mean': overall_mean,
                'group_means': group_means,
                't_test': overall_t_test
            }



        # Calculate Overall Stats for Banks Table (Averages)
        overall_bank_stats = {}
        if results:
            # Averages per criterion
            for cid in sorted_criteria:
                vals = [r['means'][cid] for r in results if cid in r['means'] and r['means'][cid] is not None]
                if vals:
                    overall_bank_stats[cid] = np.mean(vals)
            
            # Average Weighted Score
            w_scores = [r['means'].get('weighted_score', 0) for r in results]
            if w_scores:
                overall_bank_stats['weighted_score'] = np.mean(w_scores)
                
            # Average Total Max Score
            t_scores = [r['total_max_score'] for r in results if r['total_max_score']]
            if t_scores:
                overall_bank_stats['total_max_score'] = np.mean(t_scores)

            # Average IRR
            irrs = []
            for r in results:
                ival = r['inter_rater_reliability']
                if isinstance(ival, (int, float)):
                    irrs.append(ival)
                elif isinstance(ival, dict):
                     v = list(ival.values())
                     if v:
                         irrs.append(np.mean(v))
            
            if irrs:
                overall_bank_stats['inter_rater_reliability'] = np.mean(irrs)

        # Process Group Stats
        problem_groups = []
        for g_name, g_data in group_stats.items():
            g_means = {}
            for k, vals in g_data.items():
                if vals:
                    g_means[k] = np.mean(vals)
            
            problem_groups.append({
                'name': g_name,
                'means': g_means,
                'total_max_score': g_means.get('total_max_score', 0)
            })
        
        # Sort groups by name
        problem_groups.sort(key=lambda x: x['name'])

        response_data = {
            'banks': [{
                'id': r['id'], 
                'name': r['name'], 
                'means': r['means'],
                'total_max_score': r['total_max_score'],
                'inter_rater_reliability': r['inter_rater_reliability']
            } for r in results],
            'problem_groups': problem_groups,
            'anova': anova_results,
            'criteria_order': sorted_criteria,
            'global_criteria_irr': global_criteria_results,
            'overall_criteria_stats': overall_criteria_stats,
            'overall_bank_stats': overall_bank_stats
        }

        # QUIZ ANALYSIS
        # ---------------------------------------------------------------------
        quiz_results = []
        quizzes = Quiz.objects.filter(owner=instructor)
        
        # Collect all criteria used across all quizzes for dynamic table columns
        # Map: criterion_id -> { order: int }
        all_quiz_criteria = {}
        
        # Collection for Quiz Score ANOVA
        all_quiz_scores = []

        for quiz in quizzes:
            # 1. Attempts
            attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False)
            response_count = attempts.count()
            
            # 2. Average Time
            durations = []
            for a in attempts:
                if a.started_at and a.completed_at:
                    d = (a.completed_at - a.started_at).total_seconds() / 60.0
                    if d > 0: durations.append(d)
            avg_time = sum(durations)/len(durations) if durations else None
            
            # 3. Average Word Count (Open Text Slots)
            # Find open text slots
            text_slots = quiz.slots.filter(response_type=QuizSlot.ResponseType.OPEN_TEXT)
            avg_word_count = None
            if text_slots.exists():
                # Get all answers
                # Optimized way:
                answers = QuizAttemptSlot.objects.filter(
                    attempt__in=attempts,
                    slot__in=text_slots
                ).values_list('answer_data', flat=True)
                
                counts = []
                for ans in answers:
                    if ans and 'text' in ans:
                        text = ans['text']
                        counts.append(len(text.split()))
                
                if counts:
                    avg_word_count = sum(counts) / len(counts)

            # 3.5 Average Student Score & Attempt processing for Ratings
            # Calculate Total Quiz Score per Attempt for this quiz using existing attempts
            avg_quiz_score = None
            if attempts.exists():
                attempt_scores = QuizAttemptSlot.objects.filter(
                    attempt__in=attempts,
                    grade__isnull=False
                ).values('attempt_id').annotate(
                    total_score=Coalesce(Sum('grade__items__selected_level__points'), 0.0)
                )
                
                scores_list = [item['total_score'] for item in attempt_scores]
                if scores_list:
                    avg_quiz_score = sum(scores_list) / len(scores_list)
                    score_std_dev = None
                    if len(scores_list) > 1:
                        score_std_dev = float(np.std(scores_list, ddof=1))
                        
                    # Collect for ANOVA (min 2 samples to be useful)
                    if len(scores_list) > 1:
                        all_quiz_scores.append({
                            'id': quiz.id,
                            'title': quiz.title,
                            'scores': scores_list
                        })
            
            # 4. Ratings & Cronbach Alpha
            # Find rating slots
            rating_slots = quiz.slots.filter(response_type=QuizSlot.ResponseType.RATING)
            
            quiz_alpha = None
            quiz_criteria_means = {}
            
            if rating_slots.exists():
                # Get criteria for this quiz
                # We assume criteria are defined on the quiz level or rubric
                rubric_criteria = QuizRatingCriterion.objects.filter(quiz=quiz).order_by('order')
                
                c_ids = [c.criterion_id for c in rubric_criteria]
                # Collect unique criteria IDs and their minimum order
                for c in rubric_criteria:
                    if c.criterion_id not in all_quiz_criteria:
                        all_quiz_criteria[c.criterion_id] = {'order': c.order}
                    else:
                        # Keep minimum order just in case of conflicts (should be consistent though)
                        all_quiz_criteria[c.criterion_id]['order'] = min(
                            all_quiz_criteria[c.criterion_id]['order'], 
                            c.order
                        )

                # Collect ratings
                slot_alphas = []
                c_totals_quiz = {} # c_name -> list of means per slot
                
                for slot in rating_slots:
                    # Get attempts for this slot
                    slot_attempts = QuizAttemptSlot.objects.filter(
                        attempt__in=attempts,
                        slot=slot
                    ).values_list('answer_data', flat=True)
                    
                    slot_matrix = [] # list of lists
                    
                    # Store values for means
                    slot_c_values = {c_id: [] for c_id in c_ids}
                    
                    for ans in slot_attempts:
                        if ans and 'ratings' in ans:
                            ratings = ans['ratings']
                            # Check if complete
                            if all(k in ratings for k in c_ids):
                                row = [float(ratings[k]) for k in c_ids]
                                slot_matrix.append(row)
                                
                            for k, v in ratings.items():
                                if k in slot_c_values:
                                     slot_c_values[k].append(float(v))

                    # Calculate Alpha
                    K = len(c_ids)
                    if K > 1 and len(slot_matrix) > 1:
                         # Variance calc
                         item_variances = []
                         for col_idx in range(K):
                             col_values = [r[col_idx] for r in slot_matrix]
                             if col_values:
                                 col_mean = sum(col_values)/len(col_values)
                                 var = sum((x - col_mean)**2 for x in col_values)/(len(col_values)-1)
                                 item_variances.append(var)
                             else:
                                 item_variances.append(0)
                         
                         total_scores = [sum(r) for r in slot_matrix]
                         mean_t = sum(total_scores)/len(total_scores)
                         var_t = sum((x - mean_t)**2 for x in total_scores)/(len(total_scores)-1)
                         
                         if var_t > 0:
                             alpha = (K/(K-1)) * (1 - (sum(item_variances)/var_t))
                             slot_alphas.append(alpha)
                    
                    # Collect means
                    for c_id, vals in slot_c_values.items():
                        if vals:
                            name = c_id # Use ID as key
                            if name not in c_totals_quiz: c_totals_quiz[name] = []
                            c_totals_quiz[name].append(sum(vals)/len(vals))
                
                # Average Alpha
                if slot_alphas:
                    quiz_alpha = sum(slot_alphas)/len(slot_alphas)
                
                # Average Means
                for name, slot_means in c_totals_quiz.items():
                    quiz_criteria_means[name] = sum(slot_means)/len(slot_means)

            quiz_results.append({
                'id': quiz.id,
                'title': quiz.title,
                'response_count': response_count,
                'avg_time_minutes': avg_time,
                'avg_word_count': avg_word_count,
                 # Average Student Score
                'avg_score': avg_quiz_score,
                'score_std_dev': score_std_dev if 'score_std_dev' in locals() else None,
                'cronbach_alpha': quiz_alpha,
                'means': quiz_criteria_means
            })
            
        response_data['quiz_analysis'] = {
            'quizzes': quiz_results,
            # Sort IDs by order map
            'all_criteria': sorted(
                list(all_quiz_criteria.keys()), 
                key=lambda cid: (all_quiz_criteria[cid]['order'], cid)
            )
        }
        
        # 4.5 Quiz Score ANOVA
        quiz_score_anova = None
        if len(all_quiz_scores) > 1:
            try:
                groups = [q['scores'] for q in all_quiz_scores]
                group_names = [q['title'] for q in all_quiz_scores]
                
                with warnings.catch_warnings():
                     warnings.simplefilter("ignore", RuntimeWarning)
                     f_stat, p_val = stats.f_oneway(*groups)
                
                if f_stat is not None and (np.isinf(f_stat) or np.isnan(f_stat)):
                     f_stat = None
                if p_val is not None and (np.isinf(p_val) or np.isnan(p_val)):
                     p_val = None
                
                significant = p_val < 0.05 if p_val is not None else False
                tukey_results = []
                
                if significant and len(groups) > 2:
                    try:
                        res = stats.tukey_hsd(*groups)
                        matrix = res.pvalue
                        for i in range(len(group_names)):
                            for j in range(i + 1, len(group_names)):
                                if matrix[i, j] < 0.05:
                                    tukey_results.append(f"{group_names[i]} vs {group_names[j]} (p={matrix[i, j]:.3f})")
                    except Exception:
                        pass

                quiz_score_anova = {
                    'f_stat': float(f_stat) if f_stat is not None else None,
                    'p_value': float(p_val) if p_val is not None else None,
                    'significant': significant,
                    'quizzes_included': group_names,
                    'tukey_results': tukey_results
                }
            except Exception:
                pass

        if quiz_score_anova:
            response_data['quiz_analysis']['score_anova'] = quiz_score_anova
        

        if quiz_score_anova:
            response_data['quiz_score_anova'] = quiz_score_anova

            # 5. Global Quiz Agreement (Aggregated across ALL quizzes)
        # Refactored to match Quiz Analytics structure for consistent UI
        
        # Accumulators
        agreement_data = [] # Summary rows
        detailed_comparisons = {} # Composite Key -> Details
        
        # We need to track all unique criterion codes encountered to build columns
        all_criteria_columns_map = {} # criterion_name -> {id, name, code}
        
        # For overall kappa
        all_student_ratings_list = []
        all_instructor_ratings_list = []
        possible_ratings_overall = set()
        total_common_problems = 0
        
        # Per criterion lists for kappa
        # criterion_name -> {'i_list': [], 's_list': [], 'scale': []}
        criterion_kappa_data = {}

        # Global Rating Distribution (for Chart/Table)
        global_rating_counts = {} 
        global_grouped_student_counts = {} # group -> criterion -> value -> count
        # criterion_name -> { total_score: float, count: int, scale_labels: {} }
        global_rating_stats = {}
        global_criterion_orders = {} # {criterion_name: min_order}
        global_rating_scales = {} # {criterion_name: set(values)}

        # Global Score vs Rating Correlation Data
        # criterion_name -> list of {x: score, y: rating}
        global_score_points = {} 
        global_weighted_score_points = []
        
        # Global Score vs Time Correlation Data
        # list of {x: score, y: duration_minutes}
        global_time_score_points = []

        # Global Score vs Word Count Correlation Data
        # list of {x: score, y: word_count}
        global_word_count_score_points = []
        
        # Global Time vs Word Count Correlation Data
        # list of {x: duration_minutes, y: word_count}
        global_word_count_vs_time_points = []
        
        # Global Time vs Rating Correlation Data
        global_time_vs_rating_points = {} # name -> list of {x: duration, y: rating}
        global_weighted_time_vs_rating_points = [] # list of {x: duration, y: weighted_rating}

        # Helper map for Bank Weights: BankID -> { InstructorCode -> Weight }
        bank_weights_cache = {}

        # Global Rating Rows for Inter-Criterion Correlation
        global_rating_rows = []

        for quiz in quizzes:
            # 1. Get Criteria Mapping & Scale Mapping 
            quiz_criteria = QuizRatingCriterion.objects.filter(quiz=quiz).order_by('order')
            criterion_map = {} # quiz_crit_id -> instructor_crit_code
            criterion_names = {} # quiz_crit_id -> name (or code, for grouping globals)
            
            # Pre-populate global tracking with known criteria from this quiz
            for qc in quiz_criteria:
                if qc.name not in global_score_points:
                    global_score_points[qc.name] = []
                
                if qc.name not in global_rating_counts:
                    global_rating_counts[qc.name] = {}
                    global_rating_stats[qc.name] = {'total_score': 0, 'count': 0, 'scale_labels': {}}
                
                if qc.name not in global_criterion_orders:
                    global_criterion_orders[qc.name] = qc.order
                else:
                    global_criterion_orders[qc.name] = min(global_criterion_orders[qc.name], qc.order)
                
                if qc.name not in global_rating_scales:
                    global_rating_scales[qc.name] = set()

                if qc.name not in global_time_vs_rating_points:
                    global_time_vs_rating_points[qc.name] = []

                if qc.instructor_criterion_code:
                    criterion_map[qc.criterion_id] = qc.instructor_criterion_code
                    criterion_names[qc.criterion_id] = qc.name
                    # ...
            
            # --- Time Correlation Logic ---
            # Collect duration for each completed attempt
            # We need this map for the Score Correlation loop below
            quiz_attempts = QuizAttempt.objects.filter(
                quiz=quiz,
                completed_at__isnull=False,
                started_at__isnull=False
            ).values('id', 'started_at', 'completed_at')
            
            # 1. Calculate Total Quiz Score per Attempt for this quiz
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
                    # Calculate duration in minutes
                    duration = (attempt['completed_at'] - attempt['started_at']).total_seconds() / 60.0
                    if duration > 0:  # Only include positive durations
                        global_time_score_points.append({'x': score, 'y': duration})
                        attempt_durations[attempt_id] = duration


            # --- Score & Time vs Rating Correlation Logic ---
            # Now that maps are ready, we can process slots for this quiz
            
            # 2. Fetch rating slots with attempt_id and bank info
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
                
                # Check for score OR duration (we can plot one without the other technically, but logic usually requires score for standard plots)
                # But here we are collecting points.
                
                if score is not None or duration is not None:
                    ratings = entry['answer_data'].get('ratings', {})
                    bank_id = entry['assigned_problem__problem_bank__id']
                    
                    # Fetch weights if not in cache
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
                    
                    for q_cid, val in ratings.items():
                        c_name = criterion_names.get(q_cid)
                        i_code = criterion_map.get(q_cid)
                        
                        if c_name:
                             if score is not None:
                                 global_score_points[c_name].append({'x': score, 'y': val})
                             if duration is not None:
                                 global_time_vs_rating_points[c_name].append({'x': duration, 'y': val})
                             
                        # Weighted Calc
                        if i_code:
                            weight = current_bank_weights.get(i_code, 1) # Default to 1 if not found
                            w_sum += val * weight
                            w_total += weight
                            
                    if w_total > 0:
                        weighted_avg = w_sum / w_total
                        if score is not None:
                            global_weighted_score_points.append({'x': score, 'y': weighted_avg})
                        if duration is not None:
                            global_weighted_time_vs_rating_points.append({'x': duration, 'y': weighted_avg})


            # --- Word Count Correlation Logic ---
            text_slots = quiz.slots.filter(response_type='open_text')
            if text_slots.exists():
                 # Calculate total word count for each attempt that has a score
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
                         
                         # Time vs Word Count
                         if aid in attempt_durations:
                             duration = attempt_durations[aid]
                             global_word_count_vs_time_points.append({'x': duration, 'y': wc})


            quiz_criteria = QuizRatingCriterion.objects.filter(quiz=quiz).order_by('order')
            criterion_map = {} # quiz_crit_id -> instructor_crit_code
            criterion_names = {} # quiz_crit_id -> name (or code, for grouping globals)
            
            # We map local quiz criterion to Global Criterion Name for aggregation
            # (Assuming criterion names like 'Accuracy' are consistent across quizzes)
            criterion_name_map = {} # instructor_crit_code -> global_name

            # Map for quick lookup
            quiz_criteria_map = {c.criterion_id: c for c in quiz_criteria}

            # Pre-populate global tracking with known criteria from this quiz
            for qc in quiz_criteria:
                if qc.name not in global_rating_counts:
                    global_rating_counts[qc.name] = {}
                    global_rating_stats[qc.name] = {'total_score': 0, 'count': 0, 'scale_labels': {}}
                
                # Track order (take the minimum order found across quizzes for stability)
                if qc.name not in global_criterion_orders:
                    global_criterion_orders[qc.name] = qc.order
                else:
                    global_criterion_orders[qc.name] = min(global_criterion_orders[qc.name], qc.order)
                
                if qc.name not in global_rating_scales:
                    global_rating_scales[qc.name] = set()

                if qc.instructor_criterion_code:
                    criterion_map[qc.criterion_id] = qc.instructor_criterion_code
                    criterion_names[qc.criterion_id] = qc.name
                    criterion_name_map[qc.instructor_criterion_code] = qc.name
                    
                    # Track columns
                    if qc.name not in all_criteria_columns_map:
                         all_criteria_columns_map[qc.name] = {
                             'id': qc.name,
                             'name': qc.name,
                             'code': qc.instructor_criterion_code
                         }
                         
            if not criterion_map:
                continue

            quiz_scale = QuizRatingScaleOption.objects.filter(quiz=quiz)
            scale_map = {} # quiz_value -> mapped_value
            # Build Scale Map for Labels (Raw Value -> Label)
            scale_labels = {} # raw_value -> label
            current_quiz_scale_values = set()
            
            for qs in quiz_scale:
                if qs.mapped_value is not None:
                    # Handle float/int discrepancy by forcing float where possible or keeping checking strict
                    scale_map[qs.value] = qs.mapped_value
                # Store label for the RAW value
                scale_labels[qs.value] = qs.label
                current_quiz_scale_values.add(qs.value)
            
            # Add all scale values to global tracking for all criteria in this quiz
            # Assuming all criteria in the same quiz share the same scale options (which is how Quiz model works)
            for qc in quiz_criteria:
                if qc.name in global_rating_scales:
                    global_rating_scales[qc.name].update(current_quiz_scale_values)
            
            if not scale_map:
                continue

            possible_ratings = sorted(list(scale_map.values()))
            possible_ratings_overall.update(possible_ratings)
            valid_raw_values = list(scale_map.keys())

            # Update global scale labels
            for c_name in global_rating_counts.keys():
                # We merge labels. If conflict, last one wins. Ideally scales are consistent globally.
                if c_name in global_rating_stats:
                    global_rating_stats[c_name]['scale_labels'].update(scale_labels)

            # 3. Identify Problems & Student Ratings
            attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False)
            
            # ProblemID -> { InstructorCriterionCode -> [List of dicts {'raw':, 'mapped':}] }
            student_ratings_data = {} 
            
            # Fetch slots
            # Fetch slots
            attempt_slots = QuizAttemptSlot.objects.filter(
                attempt__in=attempts,
                slot__in=quiz.slots.filter(response_type=QuizSlot.ResponseType.RATING),
                answer_data__ratings__isnull=False
            ).values('assigned_problem_id', 'answer_data', 'attempt__student_identifier', 'assigned_problem__group')

            for entry in attempt_slots:
                # Accumulate for Global Rating Distribution
                ratings = entry['answer_data'].get('ratings', {})
                p_group = entry.get('assigned_problem__group') or 'Ungrouped'
                
                # Capture row for correlation
                current_row = {}

                for c_id, raw_val in ratings.items():
                    # Find criterion name
                    c_obj = quiz_criteria_map.get(c_id)
                    if c_obj:
                        c_name = c_obj.name
                        
                        # Ensure initialized (should be from pre-population, but safety check)
                        if c_name not in global_rating_counts:
                            global_rating_counts[c_name] = {}
                            global_rating_stats[c_name] = {'total_score': 0, 'count': 0, 'scale_labels': {}}
                            if c_name not in global_criterion_orders:
                                global_criterion_orders[c_name] = c_obj.order
                        
                        # Use RAW value directly
                        val = raw_val
                        # Convert to int/float if possible for consistency
                        try:
                             val = float(raw_val)
                             if val.is_integer():
                                 val = int(val)
                        except (ValueError, TypeError):
                             pass

                        if val not in global_rating_counts[c_name]:
                            global_rating_counts[c_name][val] = 0
                        
                        global_rating_counts[c_name][val] += 1
                        
                        # Add to correlation row
                        try:
                             current_row[c_name] = float(val)
                        except: pass
                        
                        # --- Accumulate for Group Comparison (Student Ratings) ---
                        if p_group not in global_grouped_student_counts:
                            global_grouped_student_counts[p_group] = {}
                        if c_name not in global_grouped_student_counts[p_group]:
                            global_grouped_student_counts[p_group][c_name] = {}
                        
                        if val not in global_grouped_student_counts[p_group][c_name]:
                            global_grouped_student_counts[p_group][c_name][val] = 0
                        global_grouped_student_counts[p_group][c_name][val] += 1
                        # -------------------------------------------------------
                        
                        # Stats
                        if isinstance(val, (int, float)):
                            global_rating_stats[c_name]['total_score'] += val
                            global_rating_stats[c_name]['count'] += 1
                            
                        # Update label (using the raw value as key)
                        if raw_val in scale_labels:
                            global_rating_stats[c_name]['scale_labels'][val] = scale_labels[raw_val]

                if len(current_row) > 1:
                     global_rating_rows.append(current_row)

                pid = entry['assigned_problem_id']
                sid = entry['attempt__student_identifier']
                
                # ... existing logic for detailed analysis ...
                # Re-extract and map for detailed
                # (The original logic below this block needs the mapped values for ANOVA/IRR)
                # But notice I replaced the whole block up to the loop start.
                # I need to ensure the detailed logic (which I might have cut off in previous replacement or verification) is intact.
                # Let's verify what I am replacing.
                # My previous edit ended at `pass` inside the loop, effectively truncating the detailed processing logic.
                # Oh wait, `pass` was my manual cutoff in the replace tool content, but `replace_file_content` replaces exact ranges.
                # The previous edit replaced lines 751-850+.
                # I need to be careful to NOT delete the detailed analysis logic which resides AFTER the rating accumulation loop.
                # For this edit, I focus on the setup and the accumulation loop.
                # The detailed analysis part (student_ratings_data population) was INSIDE the attempt_slots loop in original code.

                if pid not in student_ratings_data:
                    student_ratings_data[pid] = {}
                
                for q_cid, val in ratings.items():
                    # Strict matching as per quiz.py
                    # Cast val to type of keys if needed? usually keys are floats in DB? 
                    # qs.value is float field?
                    
                    # Try matching roughly
                    mapped_val = scale_map.get(val)
                    if mapped_val is None:
                        # try float conversion
                        try:
                             mapped_val = scale_map.get(float(val))
                        except (ValueError, TypeError):
                             pass
                    
                    if q_cid in criterion_map and mapped_val is not None:
                        i_code = criterion_map[q_cid]
                        
                        if i_code not in student_ratings_data[pid]:
                            student_ratings_data[pid][i_code] = []
                            
                        student_ratings_data[pid][i_code].append({
                            'raw': val,
                            'mapped': mapped_val,
                            'sid': sid
                        })

            # 4. Fetch Instructor Ratings
            instructor_ratings_data = {}
            relevant_problem_ids = list(student_ratings_data.keys())
            
            # Fetch Problems to get order_in_bank for labeling
            from problems.models import Problem
            problems_map = {
                p.id: p.order_in_bank 
                for p in Problem.objects.filter(id__in=relevant_problem_ids)
            }
            
            instructor_ratings = InstructorProblemRating.objects.filter(
                problem_id__in=relevant_problem_ids
            ).prefetch_related('entries__criterion')
            
            for rating in instructor_ratings:
                pid = rating.problem_id
                if pid not in instructor_ratings_data:
                    instructor_ratings_data[pid] = {}
                
                for entry in rating.entries.all():
                    code = entry.criterion.criterion_id
                    val = entry.scale_option.value
                    
                    if code not in instructor_ratings_data[pid]:
                        instructor_ratings_data[pid][code] = []
                    instructor_ratings_data[pid][code].append({
                        'value': val
                    })

            # 5. Aggregate per Problem (Per Quiz logic)
            for pid in relevant_problem_ids:
                # We iterate unique CODES now, not just criteria objects, 
                # but to know the 'Name', we use criterion_name_map
                
                # Iterate through all known codes for this quiz to ensure we catch everything
                present_codes = set(student_ratings_data.get(pid, {}).keys()) | set(instructor_ratings_data.get(pid, {}).keys())
                
                for i_code in present_codes:
                     c_name = criterion_name_map.get(i_code)
                     if not c_name: continue # Skip if not part of this quiz mapping

                     s_vals_objs = student_ratings_data.get(pid, {}).get(i_code, [])
                     i_vals_objs = instructor_ratings_data.get(pid, {}).get(i_code, [])

                     if s_vals_objs and i_vals_objs:
                        # Student Aggregation: Average Raw -> Nearest Raw -> Map
                        s_raw_vals = [float(x['raw']) for x in s_vals_objs]
                        
                        # We need valid_raw_values for nearest calc.
                        # Assuming scale_map keys are valid raws.
                        # Note: we might need to handle float/int types in valid_raw_values
                        
                        nearest_raw = calculate_average_nearest(s_raw_vals, valid_raw_values)
                        s_median = scale_map.get(nearest_raw)
                        # retry float if missed
                        if s_median is None: s_median = scale_map.get(float(nearest_raw) if nearest_raw is not None else None)

                        # Instructor Aggregation
                        i_vals = [x['value'] for x in i_vals_objs]
                        i_mean_val = mean(i_vals) if i_vals else 0
                        i_median = calculate_average_nearest(i_vals, possible_ratings)

                        if s_median is not None and i_median is not None:
                            # Add to global accumulators
                            if c_name not in criterion_kappa_data:
                                criterion_kappa_data[c_name] = {'i_list': [], 's_list': [], 'scale': possible_ratings} # scale might mix, handled later
                            
                            criterion_kappa_data[c_name]['i_list'].append(i_median)
                            criterion_kappa_data[c_name]['s_list'].append(s_median)
                            
                            all_instructor_ratings_list.append(i_median)
                            all_student_ratings_list.append(s_median)
                            total_common_problems += 1 
                            
                            # Add to Details
                            # Composite key needs to be unique globally. 
                            details_key = f"{quiz.id}-{pid}"
                            
                            # Label Construction
                            order = problems_map.get(pid, 0)
                            problem_label = f"{quiz.title}: Problem {order}"
                            
                            if details_key not in detailed_comparisons:
                                detailed_comparisons[details_key] = {
                                    'problem_id': pid,
                                    'order': order,
                                    'quiz_title': quiz.title,
                                    'problem_label': problem_label,
                                    'ratings': {}
                                }
                                

                            
                            detailed_comparisons[details_key]['ratings'][c_name] = {
                                'instructor': i_median,
                                'instructor_mean': i_mean_val,
                                'student': s_median,
                                'student_mean': mean(s_raw_vals) if s_raw_vals else 0,
                                'instructor_details': i_vals_objs,
                                'student_details': s_vals_objs
                            }
        
        # Process Agreement Data (Summary Table)
        possible_ratings_list = sorted(list(possible_ratings_overall)) if possible_ratings_overall else [1, 2, 3, 4]

        # Individual Criteria Rows
        for c_name, data in criterion_kappa_data.items():
            k = None
            if len(data['i_list']) >= 5:
                # Use pooled scale or specific? Pooled seems safer for global view if scales mix
                k = quadratic_weighted_kappa(
                    data['i_list'], 
                    data['s_list'], 
                    possible_ratings=possible_ratings_list, # Normalize to union of scales
                    context=f"Global Quiz Agreement - {c_name}"
                )
            
            agreement_data.append({
                'criterion_id': c_name,
                'criterion_name': c_name,
                'instructor_code': all_criteria_columns_map.get(c_name, {}).get('code', '-'),
                'common_problems': len(data['i_list']),
                'kappa_score': round(k, 4) if k is not None else None
            })
            
        agreement_data.sort(key=lambda x: global_criterion_orders.get(x['criterion_name'], 999))

        # Overall Row
        if all_student_ratings_list:
            overall_kappa = quadratic_weighted_kappa(
                all_instructor_ratings_list, 
                all_student_ratings_list, 
                possible_ratings=possible_ratings_list,
                context="Global Quiz Agreement - Overall"
            )
            agreement_data.append({
                'criterion_id': 'all',
                'criterion_name': 'Overall (All Criteria)',
                'instructor_code': '-',
                'common_problems': sum(len(d['i_list']) for d in criterion_kappa_data.values()),
                'kappa_score': round(overall_kappa, 4) if overall_kappa is not None else None
            })

        # Columns
        criteria_columns = sorted(list(all_criteria_columns_map.values()), key=lambda x: global_criterion_orders.get(x['name'], 999))
        
        # Details List
        # Filter out empty comparisons
        details_list = [d for d in detailed_comparisons.values() if d['ratings']]
        details_list.sort(key=lambda x: (x.get('quiz_title', ''), x.get('order', 0)))

        response_data['global_quiz_agreement'] = {
            'agreement': agreement_data,
            'details': details_list,
            'criteria_columns': criteria_columns
        }
        
        
        # Format Global Rating Distribution for Chart
        global_rating_distribution_data = {'criteria': []}
        
        # Sort by ORDER instead of Name
        sorted_criteria_names = sorted(global_rating_counts.keys(), key=lambda x: global_criterion_orders.get(x, 999))
        
        for c_name in sorted_criteria_names:
            counts = global_rating_counts[c_name]
            criterion_stats = global_rating_stats[c_name]
            labels = criterion_stats['scale_labels']
            
            total_responses = sum(counts.values())
            
            # Use ALL collected scale values for this criterion, filling with 0 if needed
            all_values = sorted(list(global_rating_scales.get(c_name, []))) if c_name in global_rating_scales else sorted(counts.keys())
            
            dist_data = []
            for val in all_values:
                count = counts.get(val, 0)
                percentage = (count / total_responses * 100) if total_responses > 0 else 0
                label = labels.get(val, str(val))
                
                dist_data.append({
                    'value': val,
                    'label': label,
                    'count': count,
                    'percentage': percentage
                })
            
            # Retrieve code/ID
            c_code = all_criteria_columns_map.get(c_name, {}).get('code', c_name)
            
            global_rating_distribution_data['criteria'].append({
                'id': c_code,
                'name': c_name,
                'distribution': dist_data,
                'total': total_responses,
                'mean': criterion_stats['total_score'] / criterion_stats['count'] if criterion_stats['count'] > 0 else 0
            })

        response_data['global_rating_distribution'] = global_rating_distribution_data

        # Calculate Inter-Criterion Correlation Matrix
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

        response_data['inter_criterion_correlation'] = inter_criterion_correlation

        # --- Grouped Rating Distribution (for Group Comparison Chart) ---
        formatted_grouped_distribution = []
        
        # We need to construct the data structure:
        # [ { group: "G1", data: { criteria: [ {name, distribution: []} ] } } ]
        
        # We have 'group_stats' which currently only holds MEANS: group -> criterion -> [list of avg scores]
        # But we need DISTRIBUTIONS (counts of values).
        # 'group_stats' was populated from 'problem_scores' around line 273.
        # 'problem_scores' (line 91) keys are problem_ids, and it has 'criteria' -> {c_name -> [list of ratings]}
        
        # We need to re-scan `all_problem_scores` (which aggregates problem_scores from all banks)
        # to build distributions per group.
        
        # --- Grouped Rating Distribution (for Group Comparison Chart) ---
        formatted_grouped_distribution = []
        
        # Now using STUDENT RATINGS accumulated in global_grouped_student_counts
        # Structure: global_grouped_student_counts[group][c_name][value] = count
        
        group_dist_acc = global_grouped_student_counts # Alias for reuse of below logic structure if matches
        
        # Note: Previous logic iterated 'all_problem_scores' to build 'group_dist_acc'.
        # We already built 'global_grouped_student_counts' in the quiz loop.
        # So we just use it directly.
        
        # (Deleted the block that re-scanned all_problem_scores)
        
        # Now format it
        
        # Now format it
        # Sorted groups
        sorted_groups = sorted(group_dist_acc.keys())
        
        # We need a unified list of criteria names that exist in at least one group
        # Or better, iterate over `sorted_criteria` (from earlier) to keep order
        
        for g_name in sorted_groups:
            g_criteria_list = []
            
            # Use sorted_criteria (which is sorted by rubric order)
            # but also include any that might not be in sorted_criteria if any (though unlikely if gathered correctly)
            # Let's iterate sorted_criteria
            
            for c_name in sorted_criteria_names:
                # Find or create distribution
                group_c_dist = group_dist_acc[g_name].get(c_name, {})
                
                # Get all possible values (scale) for this criterion across ALL GLOBAL DATA
                # 'global_rating_scales' tracks all observed scale values for each criterion across all quizzes
                
                all_raw_vals = set(global_rating_scales.get(c_name, []))
                
                # Also include observed values in this specific distribution just in case
                for og in sorted_groups:
                    all_raw_vals.update(group_dist_acc[og].get(c_name, {}).keys())
                
                sorted_vals = sorted(list(all_raw_vals))
                
                c_dist_list = []
                total_count = sum(group_c_dist.values())
                
                for v in sorted_vals:
                    count = group_c_dist.get(v, 0)
                    pct = (count / total_count * 100) if total_count > 0 else 0
                    # Label? logic is tricky without explicit scale object handy per value.
                    # We can use str(v). Or try to fallback to known labels if they were gathered.
                    # In `global_rating_stats` we gathered labels!
                    label = str(v)
                    if c_name in global_rating_stats and 'scale_labels' in global_rating_stats[c_name]:
                         label = global_rating_stats[c_name]['scale_labels'].get(v, str(v))
                    
                    c_dist_list.append({
                        'value': v,
                        'label': label,
                        'count': count,
                        'percentage': pct
                    })
                    
                g_criteria_list.append({
                    'name': c_name,
                    'distribution': c_dist_list
                })
                
            formatted_grouped_distribution.append({
                'group': g_name,
                'data': { 'criteria': g_criteria_list }
            })
            
        response_data['grouped_rating_distribution'] = formatted_grouped_distribution

        # 6. Global Student vs Instructor Comparison
        # ---------------------------------------------------------------------
        global_comparison_rows = []
        global_detailed_comparisons = []
        
        # Accumulators for Global T-Tests
        # group -> criterion_code -> { 's_norm': [], 'i_raw': [] }
        # Note: We will use 'Overall' as a special group that accumulates everything.
        global_comparison_acc = {} 
        
        # Weighted Score Accumulators
        # group -> { 's': [], 'i': [] }
        global_weighted_acc = {}
        
        # Helper to init group acc
        def init_group_acc(grp):
            if grp not in global_comparison_acc:
                global_comparison_acc[grp] = {}
            if grp not in global_weighted_acc:
                global_weighted_acc[grp] = {'s': [], 'i': []}

        # We need a map of criterion code to display name (taking first available)
        global_code_to_name = {}
        global_code_to_order = {}
        
        for quiz in quizzes:
            # Re-fetch ratings/students for this specific purpose to ensure clean context (or reuse if optimized)
            # We need student ratings mapped to instructor codes.
            
            # 1. Get Criteria
            q_criteria = QuizRatingCriterion.objects.filter(quiz=quiz).order_by('order')
            if not q_criteria.exists():
                continue
                
            q_criterion_map = {} # quiz_crit_id -> instructor_code
            for qc in q_criteria:
                if qc.instructor_criterion_code:
                    q_criterion_map[qc.criterion_id] = qc.instructor_criterion_code
                    if qc.instructor_criterion_code not in global_code_to_name:
                         global_code_to_name[qc.instructor_criterion_code] = qc.name
                    if qc.instructor_criterion_code not in global_code_to_order:
                         global_code_to_order[qc.instructor_criterion_code] = qc.order

            if not q_criterion_map:
                continue
            
            # 2. Get Scale Lookup (Raw -> Mapped)
            q_scale = QuizRatingScaleOption.objects.filter(quiz=quiz)
            # Map: value (int/float) -> mapped_value
            # Python dict treats 5 and 5.0 as same key.
            scale_lookup = {qs.value: qs.mapped_value for qs in q_scale}

            # 3. Fetch Data
            # Instructor Ratings
            
            # Optimization: Get all completed attempts for this quiz
            q_attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False)
            if not q_attempts.exists():
                continue
                
            q_attempt_slots = QuizAttemptSlot.objects.filter(attempt__in=q_attempts).select_related('assigned_problem', 'slot')
            
            # Map: pid -> { code -> [raw_values] }
            s_data_map = {}
            for qas in q_attempt_slots:
                pid = qas.assigned_problem_id
                if not pid: continue
                
                # Check rating data
                if qas.answer_data and 'ratings' in qas.answer_data:
                     ratings = qas.answer_data['ratings']
                     for cid, val in ratings.items():
                         if cid in q_criterion_map:
                             icode = q_criterion_map[cid]
                             if pid not in s_data_map: s_data_map[pid] = {}
                             if icode not in s_data_map[pid]: s_data_map[pid][icode] = []
                             try:
                                 s_data_map[pid][icode].append(float(val))
                             except: pass

            if not s_data_map:
                continue

            # Instructor Ratings for these problems
            relevant_pids = list(s_data_map.keys())
            q_i_ratings = InstructorProblemRating.objects.filter(
                problem_id__in=relevant_pids, 
                instructor=instructor
            ).select_related('problem', 'problem__problem_bank', 'problem__problem_bank__rubric').prefetch_related('entries', 'entries__criterion')
            
            # Map: pid -> { code -> val, weight }
            i_data_map = {}
            # Also need weights for weighted score
            i_weights_map = {} # pid -> { code -> weight }
            # Map: pid -> order
            i_order_map = {}
            # Map: pid -> group
            i_group_map = {}
            
            for r in q_i_ratings:
                pid = r.problem_id
                if pid not in i_data_map: i_data_map[pid] = {}
                if pid not in i_weights_map: i_weights_map[pid] = {}
                i_order_map[pid] = r.problem.order_in_bank
                i_group_map[pid] = r.problem.group

                for entry in r.entries.all():
                     code = entry.criterion.criterion_id 
                     val = entry.scale_option.value
                     weight = entry.criterion.weight
                     
                     i_data_map[pid][code] = val
                     i_weights_map[pid][code] = weight

            # 4. Compare Per Problem
            for pid in relevant_pids:
                if pid not in i_data_map:
                    continue
                
                # We have student ratings and instructor ratings for this problem
                p_s_data = s_data_map[pid]
                p_i_data = i_data_map[pid]
                p_weights = i_weights_map.get(pid, {})
                problem_order = i_order_map.get(pid, pid)
                problem_group = i_group_map.get(pid, '') or '-'
                
                target_groups = [problem_group, 'Overall']
                for g in target_groups:
                    init_group_acc(g)
                
                # For weighted calculation
                p_s_w_sum = 0
                p_i_w_sum = 0
                p_w_tot = 0
                has_w_data = False
                
                # Detail Object
                detail_obj = {
                    'problem_id': pid,
                    'problem_label': f"{quiz.title}: Problem {problem_order}",
                    'problem_group': problem_group,
                    'ratings': {},
                    'weighted_instructor': 0, 'weighted_student': 0, 'weighted_diff': 0
                }
                
                for icode, s_raw_list in p_s_data.items():
                    if icode in p_i_data:
                        # Instructor Value
                        i_val = p_i_data[icode]
                        
                        # Student Value (Map each rating then average)
                        s_mapped_list = []
                        s_details_list = []
                        
                        for v in s_raw_list:
                            # Use explicit mapping
                            single_mapped = scale_lookup.get(v)
                            # Fallback if None (not configured)
                            if single_mapped is None:
                                single_mapped = v
                            
                            s_mapped_list.append(single_mapped)
                            s_details_list.append({'raw': v, 'mapped': single_mapped})
                            
                        # Mapped Mean
                        s_mapped = mean(s_mapped_list) if s_mapped_list else 0
                        
                        # Add to Global Accumulators for all target groups
                        for g in target_groups:
                             if icode not in global_comparison_acc[g]:
                                 global_comparison_acc[g][icode] = {'s_norm': [], 'i_raw': [], 'common': 0}
                             
                             global_comparison_acc[g][icode]['s_norm'].append(s_mapped)
                             global_comparison_acc[g][icode]['i_raw'].append(i_val)
                             global_comparison_acc[g][icode]['common'] += 1
                        
                        detail_obj['ratings'][icode] = {
                            'instructor': i_val,
                            'instructor_mean': i_val,
                            'student_mean_norm': s_mapped,
                            'diff': s_mapped - i_val,
                            'student_details': s_details_list,
                            'instructor_details': [{'value': i_val}]
                        }
                        
                        # Weighted Calc
                        w = p_weights.get(icode, 1)
                        p_s_w_sum += s_mapped * w
                        p_i_w_sum += i_val * w
                        p_w_tot += w
                        has_w_data = True
                
                if has_w_data and p_w_tot > 0:
                    w_s = p_s_w_sum / p_w_tot
                    w_i = p_i_w_sum / p_w_tot
                    
                    for g in target_groups:
                        global_weighted_acc[g]['s'].append(w_s)
                        global_weighted_acc[g]['i'].append(w_i)
                    
                    detail_obj['weighted_instructor'] = w_i
                    detail_obj['weighted_student'] = w_s
                    detail_obj['weighted_diff'] = w_s - w_i
                    
                    global_detailed_comparisons.append(detail_obj)

        # 5. Compute Statistics for Global Rows
        # Iterate over all groups found
        
        for g_name in sorted(global_comparison_acc.keys()):
            # Per Criterion
            group_c_acc = global_comparison_acc[g_name]
            sorted_icodes = sorted(list(group_c_acc.keys()), key=lambda x: global_code_to_order.get(x, 999))
            
            for icode in sorted_icodes:
                acc = group_c_acc[icode]
                s_list = acc['s_norm']
                i_list = acc['i_raw']
                n = len(s_list)
                
                t_stat, p_val = None, None
                if n > 1:
                    # check identical
                    if all(a==b for a,b in zip(s_list, i_list)):
                        t_stat, p_val = 0.0, 1.0
                    else:
                        try:
                            res = stats.ttest_rel(s_list, i_list)
                            t_stat, p_val = res.statistic, res.pvalue
                        except: pass
                
                avg_s = mean(s_list) if s_list else 0
                avg_i = mean(i_list) if i_list else 0
                
                global_comparison_rows.append({
                    'group': g_name,
                    'criterion_id': icode,
                    'criterion_name': global_code_to_name.get(icode, icode),
                    'order': global_code_to_order.get(icode, 999),
                    'common_problems': n,
                    't_statistic': round(t_stat, 4) if t_stat is not None else None,
                    'p_value': round(p_val, 5) if p_val is not None else None,
                    'instructor_mean': round(avg_i, 4),
                    'student_mean_norm': round(avg_s, 4),
                    'mean_difference': round(avg_s - avg_i, 4),
                    'df': n - 1 if n > 0 else 0
                })
                
            # Weighted Score Row for this group
            if g_name in global_weighted_acc:
                ws_list = global_weighted_acc[g_name]['s']
                wi_list = global_weighted_acc[g_name]['i']
                wn = len(ws_list)
                wt_stat, wp_val = None, None
                
                if wn > 1:
                     if all(a==b for a,b in zip(ws_list, wi_list)):
                         wt_stat, wp_val = 0.0, 1.0
                     else:
                         try:
                             res = stats.ttest_rel(ws_list, wi_list)
                             wt_stat, wp_val = res.statistic, res.pvalue
                         except: pass
                
                w_avg_s = mean(ws_list) if ws_list else 0
                w_avg_i = mean(wi_list) if wi_list else 0
                
                global_comparison_rows.append({
                    'group': g_name,
                    'criterion_id': 'weighted',
                    'criterion_name': 'Weighted Score',
                    'order': 9999,
                    'common_problems': wn,
                    't_statistic': round(wt_stat, 4) if wt_stat is not None else None,
                    'p_value': round(wp_val, 5) if wp_val is not None else None,
                    'instructor_mean': round(w_avg_i, 4),
                    'student_mean_norm': round(w_avg_s, 4),
                    'mean_difference': round(w_avg_s - w_avg_i, 4),
                    'df': wn - 1 if wn > 0 else 0
                })

        # ... after global_comparison_acc population ...


        # Columns for Frontend
        criteria_columns = []
        all_icodes = sorted(list(global_code_to_order.keys()), key=lambda x: global_code_to_order.get(x, 999))
        for c in all_icodes:
            criteria_columns.append({
                'id': c,
                'name': global_code_to_name.get(c, c),
                'code': c
            })

        response_data['global_comparison'] = {
            'comparison': global_comparison_rows,
            'details': sorted(global_detailed_comparisons, key=lambda x: x['problem_id']),
            'criteria_columns': criteria_columns
        }

        # ANOVA for Student Ratings Across Quizzes
        # ---------------------------------------------------------------------
        # Collect student rating values grouped by quiz for each criterion
        quiz_student_rating_values = {} # quiz_id -> {criterion_name: [values]}
        
        for quiz in quizzes:
            quiz_criteria = QuizRatingCriterion.objects.filter(quiz=quiz).order_by('order')
            if not quiz_criteria.exists():
                continue
                
            quiz_criteria_map = {c.criterion_id: c for c in quiz_criteria}
            
            # Get rating scale for this quiz
            quiz_scale = QuizRatingScaleOption.objects.filter(quiz=quiz)
            # We'll use raw values directly (no mapping needed for ANOVA)
            
            # Get completed attempts
            attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False)
            if not attempts.exists():
                continue
            
            # Get all rating slots for this quiz
            rating_slots = quiz.slots.filter(response_type=QuizSlot.ResponseType.RATING)
            if not rating_slots.exists():
                continue
                
            # Collect all student ratings
            attempt_slots = QuizAttemptSlot.objects.filter(
                attempt__in=attempts,
                slot__in=rating_slots,
                answer_data__ratings__isnull=False
            ).values_list('answer_data', flat=True)
            
            # Initialize storage for this quiz
            if quiz.id not in quiz_student_rating_values:
                quiz_student_rating_values[quiz.id] = {'quiz_title': quiz.title, 'criteria': {}}
            
            # Aggregate ratings by criterion
            for answer_data in attempt_slots:
                if answer_data and 'ratings' in answer_data:
                    ratings = answer_data['ratings']
                    for c_id, raw_val in ratings.items():
                        c_obj = quiz_criteria_map.get(c_id)
                        if c_obj:
                            c_name = c_obj.name
                            
                            if c_name not in quiz_student_rating_values[quiz.id]['criteria']:
                                quiz_student_rating_values[quiz.id]['criteria'][c_name] = []
                            
                            # Convert to float for consistency
                            try:
                                val = float(raw_val)
                                quiz_student_rating_values[quiz.id]['criteria'][c_name].append(val)
                            except (ValueError, TypeError):
                                pass
        
        # Calculate ANOVA for each criterion
        quiz_anova_results = []
        
        # Collect all unique criteria across all quizzes
        all_quiz_student_criteria = set()
        for quiz_data in quiz_student_rating_values.values():
            all_quiz_student_criteria.update(quiz_data['criteria'].keys())
        
        # Sort criteria by the global order we established earlier
        sorted_quiz_student_criteria = sorted(
            list(all_quiz_student_criteria),
            key=lambda x: (global_criterion_orders.get(x, 999), x)
        )
        
        for criterion_name in sorted_quiz_student_criteria:
            groups = []
            group_names = []
            
            for quiz_id, quiz_data in quiz_student_rating_values.items():
                if criterion_name in quiz_data['criteria']:
                    values = quiz_data['criteria'][criterion_name]
                    if len(values) > 1:  # Need at least 2 values per group
                        groups.append(values)
                        group_names.append(quiz_data['quiz_title'])
            
            if len(groups) > 1:  # Need at least 2 groups to compare
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        f_stat, p_val = stats.f_oneway(*groups)
                except Exception:
                    f_stat, p_val = None, None

                if f_stat is not None and (np.isinf(f_stat) or np.isnan(f_stat)):
                    f_stat = None
                if p_val is not None and (np.isinf(p_val) or np.isnan(p_val)):
                    p_val = None
                
                significant = p_val < 0.05 if p_val is not None else False
                tukey_results = []

                if significant and len(groups) > 2:
                    try:
                        # Perform Tukey's HSD
                        res = stats.tukey_hsd(*groups)
                        matrix = res.pvalue
                        for i in range(len(group_names)):
                            for j in range(i + 1, len(group_names)):
                                if matrix[i, j] < 0.05:
                                    tukey_results.append(f"{group_names[i]} vs {group_names[j]} (p={matrix[i, j]:.3f})")
                    except Exception:
                        pass

                quiz_anova_results.append({
                    'criterion_id': criterion_name,
                    'f_stat': float(f_stat) if f_stat is not None else None,
                    'p_value': float(p_val) if p_val is not None else None,
                    'significant': significant,
                    'quizzes_included': group_names,
                    'tukey_results': tukey_results
                })
        
        response_data['quiz_anova'] = quiz_anova_results

        # Calculate Correlations based on global point lists
        score_correlation = []
        
        def calculate_global_correlations(points, label):
             n = len(points)
             if n < 2:
                 return {
                     'name': label,
                     'count': n,
                     'pearson_r': None,
                     'pearson_p': None,
                     'spearman_rho': None,
                     'spearman_p': None,
                     'points': points
                 }
             
             x = [p['x'] for p in points]
             y = [p['y'] for p in points]
             
             # Pearson
             try:
                 pr, pp = stats.pearsonr(x, y)
                 if np.isnan(pr): pr, pp = None, None
             except Exception:
                 pr, pp = None, None
                 
             # Spearman
             try:
                 # Spearman can fail if input is constant
                 sr, sp = stats.spearmanr(x, y)
                 if np.isnan(sr): sr, sp = None, None
             except Exception as e:
                 sr, sp = None, None

             return {
                 'name': label,
                 'count': n,
                 'pearson_r':  round(pr, 4) if pr is not None else None,
                 'pearson_p':  round(pp, 5) if pp is not None else None,
                 'spearman_rho': round(sr, 4) if sr is not None else None,
                 'spearman_p': round(sp, 5) if sp is not None else None,
                 'points': points # Include for frontend plotting
             }

        for c_name, points in global_score_points.items():
            score_correlation.append(calculate_global_correlations(points, c_name))
            
        score_correlation.append(calculate_global_correlations(global_weighted_score_points, "Weighted Rating"))
        
        # Sort by global criteria order
        score_correlation.sort(key=lambda x: (global_criterion_orders.get(x['name'], 999), x['name']))
        
        response_data['score_correlation'] = score_correlation
        
        # Calculate Time Correlation (only if we have valid duration data)
        if global_time_score_points:
            time_correlation = calculate_global_correlations(global_time_score_points, "Quiz Duration")
            response_data['time_correlation'] = [time_correlation]

        # Calculate Word Count Correlation (only if we have word count data)
        if global_word_count_score_points:
             wc_correlation = calculate_global_correlations(global_word_count_score_points, "Word Count")
             response_data['word_count_correlation'] = [wc_correlation]

        # Calculate Time vs Word Count Correlation
        if global_word_count_vs_time_points:
             wc_time_correlation = calculate_global_correlations(global_word_count_vs_time_points, "Time vs Word Count")
             response_data['word_count_vs_time_correlation'] = [wc_time_correlation]
             
        # Calculate Time vs Rating Correlation
        time_vs_rating_correlation = []
        for c_name, points in global_time_vs_rating_points.items():
            time_vs_rating_correlation.append(calculate_global_correlations(points, c_name))
            
        time_vs_rating_correlation.append(calculate_global_correlations(global_weighted_time_vs_rating_points, "Weighted Rating"))
        
        # Sort
        time_vs_rating_correlation.sort(key=lambda x: (global_criterion_orders.get(x['name'], 999), x['name']))
        
        response_data['time_vs_rating_correlation'] = time_vs_rating_correlation
        
        return Response(self.sanitize_data(response_data))

    def update_global_criteria_data(self, global_criteria_data, c, c_y1, c_y2, scale_vals):
         if c not in global_criteria_data:
             global_criteria_data[c] = {'y1': [], 'y2': [], 'scale': scale_vals}
         global_criteria_data[c]['y1'].extend(c_y1)
         global_criteria_data[c]['y2'].extend(c_y2)
         global_criteria_data[c]['scale'] = scale_vals

    def sanitize_data(self, data):
        """Recursively replace NaN/Inf with None for JSON compliance"""
        if isinstance(data, dict):
            return {k: self.sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_data(v) for v in data]
        elif isinstance(data, float):
            if np.isnan(data) or np.isinf(data):
                return None
        return data


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
