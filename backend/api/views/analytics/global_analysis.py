
import numpy as np
import warnings
from scipy import stats
from rest_framework.views import APIView
from rest_framework.response import Response
from accounts.models import ensure_instructor
from accounts.permissions import IsInstructor
from problems.models import ProblemBank, InstructorProblemRating
from quizzes.models import Quiz, QuizAttempt, QuizSlot, QuizAttemptSlot, QuizRatingCriterion
from .utils import calculate_weighted_kappa

class GlobalAnalysisView(APIView):
    permission_classes = [IsInstructor]

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
        all_quiz_criteria = set()

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
                c_names = {c.criterion_id: c.name for c in rubric_criteria}
                
                # Add to global set
                for name in c_names.values():
                    all_quiz_criteria.add(name)

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
                                 mean = sum(col_values)/len(col_values)
                                 var = sum((x - mean)**2 for x in col_values)/(len(col_values)-1)
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
                            name = c_names.get(c_id, c_id)
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
                'cronbach_alpha': quiz_alpha,
                'means': quiz_criteria_means
            })
            
        response_data['quiz_analysis'] = {
            'quizzes': quiz_results,
            'all_criteria': sorted(list(all_quiz_criteria))
        }
        
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
