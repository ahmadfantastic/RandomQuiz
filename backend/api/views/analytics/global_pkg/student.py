import numpy as np
import warnings
from scipy import stats as sp_stats, stats

from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum
from django.db.models.functions import Coalesce

from accounts.models import ensure_instructor
from accounts.permissions import IsInstructor
from quizzes.models import (
    Quiz, QuizAttempt, QuizSlot, QuizAttemptSlot, 
    QuizRatingCriterion, QuizRatingScaleOption
)

class GlobalStudentAnalysisView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request):
        instructor = ensure_instructor(request.user)
        
        # QUIZ ANALYSIS
        # ---------------------------------------------------------------------
        quiz_results = []
        quizzes = Quiz.objects.filter(owner=instructor)
        
        # Collect all criteria used across all quizzes for dynamic table columns
        # Map: criterion_id -> { order: int }
        all_quiz_criteria = {}
        
        # Collection for Quiz Score ANOVA
        all_quiz_scores = []
        
        # Global Rating Distribution Aggregation
        global_rating_counts = {} 
        global_grouped_student_counts = {} # group -> criterion -> value -> count
        global_rating_scales = {} # {criterion_name: set(values)}
        global_criterion_orders = {}
        global_rating_stats = {}

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
            rating_slots = quiz.slots.filter(response_type=QuizSlot.ResponseType.RATING)
            
            quiz_alpha = None
            quiz_criteria_means = {}
            
            if rating_slots.exists():
                rubric_criteria = QuizRatingCriterion.objects.filter(quiz=quiz).order_by('order')
                c_ids = [c.criterion_id for c in rubric_criteria]

                # Populate Map for IDs -> Names (for global agg)
                quiz_criteria_obj_map = {c.criterion_id: c for c in rubric_criteria}

                for c in rubric_criteria:
                    if c.criterion_id not in all_quiz_criteria:
                        all_quiz_criteria[c.criterion_id] = {'order': c.order}
                    else:
                        all_quiz_criteria[c.criterion_id]['order'] = min(
                            all_quiz_criteria[c.criterion_id]['order'], 
                            c.order
                        )
                
                # Fetch scale for this quiz for distribution mapping
                quiz_scale = QuizRatingScaleOption.objects.filter(quiz=quiz)
                current_quiz_scale_values = set(qs.value for qs in quiz_scale)
                scale_labels = {qs.value: qs.label for qs in quiz_scale}

                # Update Global Trackers with this quiz metadata
                for c in rubric_criteria:
                    if c.name not in global_rating_scales:
                        global_rating_scales[c.name] = set()
                    global_rating_scales[c.name].update(current_quiz_scale_values)
                    
                    if c.name not in global_rating_counts:
                         global_rating_counts[c.name] = {}
                         global_rating_stats[c.name] = {'total_score': 0, 'count': 0, 'scale_labels': {}}

                    if c.name not in global_criterion_orders:
                         global_criterion_orders[c.name] = c.order
                    else:
                         global_criterion_orders[c.name] = min(global_criterion_orders[c.name], c.order)

                    # Merge labels
                    if c.name in global_rating_stats:
                        global_rating_stats[c.name]['scale_labels'].update(scale_labels)


                # Collect Ratings
                slot_alphas = []
                c_totals_quiz = {} 
                
                for slot in rating_slots:
                    slot_attempts = QuizAttemptSlot.objects.filter(
                        attempt__in=attempts,
                        slot=slot
                    ).values('answer_data', 'assigned_problem__group')
                    
                    slot_matrix = []
                    slot_c_values = {c_id: [] for c_id in c_ids}
                    
                    for entry in slot_attempts:
                        ans = entry['answer_data']
                        p_group = entry.get('assigned_problem__group') or 'Ungrouped'
                        
                        if ans and 'ratings' in ans:
                            ratings = ans['ratings']
                            
                            # Alpha calc
                            if all(k in ratings for k in c_ids):
                                row = [float(ratings[k]) for k in c_ids]
                                slot_matrix.append(row)
                                
                            for k, v in ratings.items():
                                if k in slot_c_values:
                                     val = float(v)
                                     slot_c_values[k].append(val)
                                     
                                     # --- Global Distribution Aggregation ---
                                     # Find criterion object to get name
                                     if k in quiz_criteria_obj_map:
                                         c_name = quiz_criteria_obj_map[k].name
                                         
                                         # Round/Int check
                                         # Assume scale values are usually ints or simple floats
                                         # We use val directly as key if it matches scale
                                         dist_val = val
                                         if dist_val.is_integer(): dist_val = int(dist_val)
                                         
                                         if dist_val not in global_rating_counts[c_name]:
                                             global_rating_counts[c_name][dist_val] = 0
                                         global_rating_counts[c_name][dist_val] += 1
                                         
                                         # Rating Stats
                                         global_rating_stats[c_name]['total_score'] += dist_val
                                         global_rating_stats[c_name]['count'] += 1
                                         
                                         # Grouped Distribution
                                         if p_group not in global_grouped_student_counts:
                                             global_grouped_student_counts[p_group] = {}
                                         if c_name not in global_grouped_student_counts[p_group]:
                                             global_grouped_student_counts[p_group][c_name] = {}
                                         
                                         if dist_val not in global_grouped_student_counts[p_group][c_name]:
                                             global_grouped_student_counts[p_group][c_name][dist_val] = 0
                                         global_grouped_student_counts[p_group][c_name][dist_val] += 1


                    # Calculate Alpha
                    K = len(c_ids)
                    if K > 1 and len(slot_matrix) > 1:
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
                            name = c_id # Use ID as key for quiz map
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
                'avg_score': avg_quiz_score,
                'score_std_dev': score_std_dev if 'score_std_dev' in locals() else None,
                'cronbach_alpha': quiz_alpha,
                'means': quiz_criteria_means
            })
            
        quiz_analysis = {
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


        # Global Rating Distribution Aggregation Logic
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
            
            # Retrieve code/ID if we had it, but here we just used name
            # We can use name as ID for this purpose
            
            global_rating_distribution_data['criteria'].append({
                'id': c_name,
                'name': c_name,
                'distribution': dist_data,
                'total': total_responses,
                'mean': criterion_stats['total_score'] / criterion_stats['count'] if criterion_stats['count'] > 0 else 0
            })


        # Grouped Distribution
        formatted_grouped_distribution = []
        sorted_groups = sorted(global_grouped_student_counts.keys())
        
        for g_name in sorted_groups:
            g_criteria_list = []
            
            for c_name in sorted_criteria_names:
                # Find or create distribution
                if c_name in global_grouped_student_counts[g_name]:
                    group_c_dist = global_grouped_student_counts[g_name][c_name]
                else:
                    group_c_dist = {}
                
                all_raw_vals = set(global_rating_scales.get(c_name, []))
                # Add observed
                for og in sorted_groups:
                     if c_name in global_grouped_student_counts[og]:
                         all_raw_vals.update(global_grouped_student_counts[og][c_name].keys())
                
                sorted_vals = sorted(list(all_raw_vals))
                
                c_dist_list = []
                total_count = sum(group_c_dist.values())
                
                for v in sorted_vals:
                    count = group_c_dist.get(v, 0)
                    pct = (count / total_count * 100) if total_count > 0 else 0
                    
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


        response_data = {
            'quiz_analysis': quiz_analysis,
            'quiz_score_anova': quiz_score_anova,
            'global_rating_distribution': global_rating_distribution_data,
            'grouped_rating_distribution': formatted_grouped_distribution
        }
        
        return Response(response_data)
