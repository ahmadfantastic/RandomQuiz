import numpy as np
from statistics import mean
from scipy import stats as sp_stats, stats
import warnings

from rest_framework.views import APIView
from rest_framework.response import Response

from accounts.models import ensure_instructor
from accounts.permissions import IsInstructor
from problems.models import Problem, InstructorProblemRating
from quizzes.models import (
    Quiz, QuizAttempt, QuizSlot, QuizAttemptSlot, 
    QuizRatingCriterion, QuizRatingScaleOption
)
from ..utils import calculate_average_nearest, calculate_cohens_d_paired, aggregate_ratings
from ..kappa import quadratic_weighted_kappa

class GlobalAgreementAnalysisView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request):
        instructor = ensure_instructor(request.user)
        quizzes = Quiz.objects.filter(owner=instructor)

        instructor_agg = request.query_params.get('instructor_agg', 'average_nearest')
        student_agg = request.query_params.get('student_agg', 'average_nearest')

        # Accumulators
        agreement_data = [] # Summary rows
        detailed_comparisons = {} # Composite Key -> Details
        
        # We need to track all unique criterion codes encountered to build columns
        all_criteria_columns_map = {} # criterion_name -> {id, name, code}
        
        # For overall kappa
        all_student_ratings_list = []
        all_instructor_ratings_list = []
        possible_ratings_overall = set()
        
        # Per criterion lists for kappa
        # criterion_name -> {'i_list': [], 's_list': [], 'scale': []}
        criterion_kappa_data = {}

        global_criterion_orders = {}

        for quiz in quizzes:
            # 1. Get Criteria Mapping & Scale Mapping 
            quiz_criteria = QuizRatingCriterion.objects.filter(quiz=quiz).order_by('order')
            criterion_map = {} # quiz_crit_id -> instructor_crit_code
            criterion_names = {} # quiz_crit_id -> name (or code, for grouping globals)
            criterion_name_map = {} # instructor_crit_code -> global_name
            
            # Map for quick lookup
            quiz_criteria_map = {c.criterion_id: c for c in quiz_criteria}

            for qc in quiz_criteria:
                if qc.name not in global_criterion_orders:
                    global_criterion_orders[qc.name] = qc.order
                else:
                    global_criterion_orders[qc.name] = min(global_criterion_orders[qc.name], qc.order)
                
                if qc.instructor_criterion_code:
                    criterion_map[qc.criterion_id] = qc.instructor_criterion_code
                    criterion_names[qc.criterion_id] = qc.name
                    criterion_name_map[qc.instructor_criterion_code] = qc.name
                    
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
            
            for qs in quiz_scale:
                if qs.mapped_value is not None:
                    scale_map[qs.value] = qs.mapped_value
                
            if not scale_map:
                continue

            possible_ratings = sorted(list(scale_map.values()))
            possible_ratings_overall.update(possible_ratings)
            valid_raw_values = list(scale_map.keys())

            # 3. Identify Problems & Student Ratings
            attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False)
            
            # ProblemID -> { InstructorCriterionCode -> [List of dicts {'raw':, 'mapped':}] }
            student_ratings_data = {} 
            
            # Fetch slots
            attempt_slots = QuizAttemptSlot.objects.filter(
                attempt__in=attempts,
                slot__in=quiz.slots.filter(response_type=QuizSlot.ResponseType.RATING),
                answer_data__ratings__isnull=False
            ).values('assigned_problem_id', 'answer_data', 'attempt__student_identifier')

            for entry in attempt_slots:
                ratings = entry['answer_data'].get('ratings', {})
                pid = entry['assigned_problem_id']
                sid = entry['attempt__student_identifier']
                
                if pid not in student_ratings_data:
                    student_ratings_data[pid] = {}
                
                for q_cid, val in ratings.items():
                    # Try matching roughly
                    mapped_val = scale_map.get(val)
                    if mapped_val is None:
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
                present_codes = set(student_ratings_data.get(pid, {}).keys()) | set(instructor_ratings_data.get(pid, {}).keys())
                
                for i_code in present_codes:
                     c_name = criterion_name_map.get(i_code)
                     if not c_name: continue 

                     s_vals_objs = student_ratings_data.get(pid, {}).get(i_code, [])
                     i_vals_objs = instructor_ratings_data.get(pid, {}).get(i_code, [])

                     if s_vals_objs and i_vals_objs:
                        # Student Aggregation: Average Raw -> Nearest Raw -> Map
                        s_raw_vals = [float(x['raw']) for x in s_vals_objs]
                        
                        nearest_raw = aggregate_ratings(s_raw_vals, valid_raw_values, method=student_agg)
                        s_median = scale_map.get(nearest_raw)
                        # retry float if missed
                        if s_median is None: s_median = scale_map.get(float(nearest_raw) if nearest_raw is not None else None)

                        # Instructor Aggregation
                        i_vals = [x['value'] for x in i_vals_objs]
                        i_mean_val = mean(i_vals) if i_vals else 0
                        i_median = aggregate_ratings(i_vals, possible_ratings, method=instructor_agg)

                        if s_median is not None and i_median is not None:
                            # Add to global accumulators
                            if c_name not in criterion_kappa_data:
                                criterion_kappa_data[c_name] = {'i_list': [], 's_list': [], 'scale': possible_ratings} 
                            
                            criterion_kappa_data[c_name]['i_list'].append(i_median)
                            criterion_kappa_data[c_name]['s_list'].append(s_median)
                            
                            all_instructor_ratings_list.append(i_median)
                            all_student_ratings_list.append(s_median)
                            
                            # Add to Details
                            details_key = f"{quiz.id}-{pid}"
                            
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
                k = quadratic_weighted_kappa(
                    data['i_list'], 
                    data['s_list'], 
                    possible_ratings=possible_ratings_list, 
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
        details_list = [d for d in detailed_comparisons.values() if d['ratings']]
        details_list.sort(key=lambda x: (x.get('quiz_title', ''), x.get('order', 0)))

        # ---------------------------------------------------------------------
        # GLOBAL COMPARISON (T-Tests & Weighted Score)
        # ---------------------------------------------------------------------
        global_comparison_rows = []
        global_detailed_comparisons = []
        
        # Accumulators for Global T-Tests
        # group -> criterion_code -> { 's_norm': [], 'i_raw': [] }
        # Note: We will use 'Overall' as a special group that accumulates everything.
        global_comparison_acc = {} 
        
        # Helper to init group acc
        def init_group_acc(grp):
            if grp not in global_comparison_acc:
                global_comparison_acc[grp] = {}

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
            
            # Map: pid -> { code -> val }
            i_data_map = {}
            # Map: pid -> order
            i_order_map = {}
            # Map: pid -> group
            i_group_map = {}
            
            for r in q_i_ratings:
                pid = r.problem_id
                if pid not in i_data_map: i_data_map[pid] = {}
                i_order_map[pid] = r.problem.order_in_bank
                i_group_map[pid] = r.problem.group

                for entry in r.entries.all():
                     code = entry.criterion.criterion_id 
                     val = entry.scale_option.value
                     
                     i_data_map[pid][code] = val

            # 4. Compare Per Problem
            for pid in relevant_pids:
                if pid not in i_data_map:
                    continue
                
                # We have student ratings and instructor ratings for this problem
                p_s_data = s_data_map[pid]
                p_i_data = i_data_map[pid]
                problem_order = i_order_map.get(pid, pid)
                problem_group = i_group_map.get(pid, '') or '-'
                
                target_groups = [problem_group, 'Overall']
                for g in target_groups:
                    init_group_acc(g)
                
                # Detail Object
                detail_obj = {
                    'problem_id': pid,
                    'problem_label': f"{quiz.title}: Problem {problem_order}",
                    'problem_group': problem_group,
                    'ratings': {}
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
                            # Suppress warnings
                            with warnings.catch_warnings():
                                 warnings.simplefilter("ignore", RuntimeWarning)
                                 res = stats.ttest_rel(s_list, i_list)
                                 t_stat, p_val = res.statistic, res.pvalue
                        except: pass
                        
                    cohens_d = calculate_cohens_d_paired(s_list, i_list)
                    
                    if t_stat is not None and np.isnan(t_stat): t_stat = None
                    if p_val is not None and np.isnan(p_val): p_val = None
                    if cohens_d is not None and np.isnan(cohens_d): cohens_d = None
                else:
                    cohens_d = None
                    
                
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
                    'cohens_d': round(cohens_d, 4) if cohens_d is not None else None,
                    'instructor_mean': round(avg_i, 4),
                    'student_mean_norm': round(avg_s, 4),
                    'mean_difference': round(avg_s - avg_i, 4),
                    'df': n - 1 if n > 0 else 0
                })
                


        # Columns for Frontend
        t_criteria_columns = []
        all_icodes = sorted(list(global_code_to_order.keys()), key=lambda x: global_code_to_order.get(x, 999))
        for c in all_icodes:
            t_criteria_columns.append({
                'id': c,
                'name': global_code_to_name.get(c, c),
                'code': c
            })

        return Response({
            'global_quiz_agreement': {
                'agreement': agreement_data,
                'details': details_list,
                'criteria_columns': criteria_columns
            },
            'global_comparison': {
                'comparison': global_comparison_rows,
                'details': sorted(global_detailed_comparisons, key=lambda x: x['problem_id']),
                'criteria_columns': t_criteria_columns
            }
        })
