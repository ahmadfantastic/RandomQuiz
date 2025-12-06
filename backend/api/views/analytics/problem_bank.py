
import numpy as np
from scipy import stats
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from accounts.models import ensure_instructor, Instructor
from accounts.permissions import IsInstructor
from problems.models import ProblemBank, InstructorProblemRating
from .utils import calculate_weighted_kappa

class ProblemBankAnalysisView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, bank_id):
        instructor = ensure_instructor(request.user)
        bank = get_object_or_404(ProblemBank, id=bank_id)
        
        # We want to analyze ratings for problems in this bank.
        # 1. Get all ratings for problems in this bank.
        ratings = InstructorProblemRating.objects.filter(
            problem__problem_bank=bank
        ).select_related('problem', 'instructor').prefetch_related('entries', 'entries__scale_option', 'entries__criterion')
        
        # Structure: Problem -> { Instructor -> { Criterion -> Value } }
        data = {}
        instructors = set()
        criteria = set()
        
        rubric = bank.get_rubric()
        rubric_criteria = {c['id']: c['name'] for c in rubric.get('criteria', [])}
        scale = rubric.get('scale', [])
        
        criteria_list = rubric.get('criteria', [])
        criteria_weights_by_id = {c['id']: c.get('weight', 1) for c in criteria_list}
        
        for r in ratings:
            pid = r.problem_id
            iid = r.instructor.user.username # Use username as identifier
            instructors.add(iid)
            
            if pid not in data:
                data[pid] = {
                    'problem_label': r.problem.display_label,
                    'order': r.problem.order_in_bank,
                    'group': r.problem.group,
                    'ratings': {}
                }
            
            if iid not in data[pid]['ratings']:
                data[pid]['ratings'][iid] = {}
                
            for entry in r.entries.all():
                c_id = entry.criterion.criterion_id
                # c_name = rubric_criteria.get(c_id, c_id) # Name logic removed for key
                criteria.add(c_id) # Store ID
                data[pid]['ratings'][iid][c_id] = entry.scale_option.value # Use ID as key

        # Prepare response structure
        instructors_data = []
        raters_list = sorted(list(instructors))
        
        # Helper to get full instructor object/name. 
        # r.instructor gave us the Instructor model.
        # We need to map username -> {id, name}
        # Let's fetch Instructor objects for these usernames
        instructor_objs = {i.user.username: i for i in Instructor.objects.filter(user__username__in=raters_list).select_related('user')}
        
        for iid in raters_list:
            inst_obj = instructor_objs.get(iid)
            if not inst_obj: continue
            
            inst_data = {
                'id': inst_obj.id,
                'name': inst_obj.user.username, # Or inst_obj.user.get_full_name()
                'ratings': [],
                'group_comparisons': []
            }
            
            # 1. Collect ratings
            inst_ratings_values = [] # For group comparisons later
            
            for pid, p_data in data.items():
                if iid in p_data['ratings']:
                    ratings_dict = p_data['ratings'][iid]
                    # Calculate weighted score with dynamic total weight
                    w_sum = 0
                    dynamic_total_weight = 0
                    
                    for c_id, val in ratings_dict.items():
                        weight = criteria_weights_by_id.get(c_id, 1)
                        w_sum += (val * weight)
                        dynamic_total_weight += weight
                    
                    if dynamic_total_weight > 0:
                        weighted_score = w_sum / dynamic_total_weight
                    else:
                        weighted_score = 0.0
                    
                    inst_data['ratings'].append({
                        'problem_id': pid,
                        'order': p_data['order'],
                        'label': p_data['problem_label'],
                        'group': p_data['group'],
                        'values': ratings_dict,
                        'weighted_score': weighted_score
                    })
                    
                    # Collect for group stats
                    if p_data['group']:
                         inst_ratings_values.append({
                             'group': p_data['group'],
                             'values': ratings_dict
                         })

            inst_data['ratings'].sort(key=lambda x: x['order'])
            instructors_data.append(inst_data)
            
            # 2. Group Comparisons (Pairwise t-tests between groups)
            # Find unique groups
            groups = set(r['group'] for r in inst_ratings_values)
            group_list = sorted(list(groups))
            
            if len(group_list) >= 2:
                import itertools
                for g1, g2 in itertools.combinations(group_list, 2):
                    g1_vals = [r['values'] for r in inst_ratings_values if r['group'] == g1]
                    g2_vals = [r['values'] for r in inst_ratings_values if r['group'] == g2]
                    
                    # Start with Overall (sum of all criteria)? Or per criterion?
                    # Frontend shows 'Criteria' column. Let's do per-criterion + Overall used.
                    
                    # For simplicty, let's just do per-criterion
                    param_criteria_ids = rubric_criteria.keys()
                    for c_id in param_criteria_ids:
                        v1 = [d[c_id] for d in g1_vals if c_id in d]
                        v2 = [d[c_id] for d in g2_vals if c_id in d]
                        
                        if not v1 and not v2:
                            continue
                            
                        mean1 = np.mean(v1) if v1 else 0.0
                        mean2 = np.mean(v2) if v2 else 0.0
                        
                        t_stat = None
                        p_val = None
                        
                        if len(v1) > 1 and len(v2) > 1:
                            try:
                                # Check for zero variance to avoid warnings or useless calcs if possible,
                                # but scipy usually handles it (returns nan).
                                # However, sometimes we want to be explicit.
                                if np.var(v1) == 0 and np.var(v2) == 0:
                                    # Both constant. 
                                    if mean1 == mean2:
                                        p_val = 1.0
                                        t_stat = 0.0
                                    else:
                                        # Distinct constants. t-value is inf, p is 0.
                                        p_val = 0.0
                                        t_stat = 0.0 # Representation choice? Or None.
                                else:
                                    t, p = stats.ttest_ind(v1, v2, equal_var=False)
                                    if not np.isnan(p):
                                        t_stat = t
                                        p_val = p
                            except Exception:
                                pass
                                
                        inst_data['group_comparisons'].append({
                            'criteria_id': c_id,
                            'group1': g1,
                            'group2': g2,
                            'mean1': mean1,
                            'mean2': mean2,
                            't_stat': t_stat,
                            'p_value': p_val
                        })


        # 3. Inter-Rater Reliability (Pairwise)
        pairwise_irr = []
        if len(raters_list) > 1:
             for i in range(len(raters_list)):
                for j in range(i + 1, len(raters_list)):
                    r1 = raters_list[i]
                    r2 = raters_list[j]
                    
                    # Per criterion
                    for c_id in criteria: # Iterating IDs
                        y1 = []
                        y2 = []
                        for pid, p_data in data.items():
                            v1 = p_data['ratings'].get(r1, {}).get(c_id)
                            v2 = p_data['ratings'].get(r2, {}).get(c_id)
                            if v1 is not None and v2 is not None:
                                y1.append(v1)
                                y2.append(v2)
                        
                        count = len(y1)

                        if count >= 3:
                             # Get rubric scale values if possible
                             scale_vals = [s['value'] for s in scale] if scale else None
                             k = calculate_weighted_kappa(y1, y2, all_categories=scale_vals, label=f"Problem Bank - Criterion {c_id}")


                             pairwise_irr.append({
                                 'instructor1': r1,
                                 'instructor2': r2,
                                 'criteria_id': c_id,
                                 'n': count,
                                 'kappa': k
                             })

                    # Overall (concatenate all ratings)
                    all_y1 = []
                    all_y2 = []
                    for c_id in criteria: # Iterating IDs
                         for pid, p_data in data.items():
                            v1 = p_data['ratings'].get(r1, {}).get(c_id)
                            v2 = p_data['ratings'].get(r2, {}).get(c_id)
                            if v1 is not None and v2 is not None:
                                all_y1.append(v1)
                                all_y2.append(v2)
                    
                    if len(all_y1) >= 5:

                         scale_vals = [s['value'] for s in scale] if scale else None
                         k = calculate_weighted_kappa(all_y1, all_y2, all_categories=scale_vals, label="Problem Bank - Overall")


                         pairwise_irr.append({
                             'instructor1': r1,
                             'instructor2': r2,
                             'criteria_id': 'Overall',
                             'n': len(all_y1),
                             'kappa': k
                         })

        # Calculate total max score
        rubric_data = bank.get_rubric()
        scale = rubric_data.get('scale', [])
        criteria_list = rubric_data.get('criteria', [])
        total_max_score = 0
        if scale and criteria_list:
            max_val = max(s['value'] for s in scale)
            total_max_score = max_val * len(criteria_list)

        return Response({
            'bank': {
                'id': bank.id,
                'name': bank.name,
                'description': bank.description,
            },
            'rubric': bank.get_rubric(),
            'total_max_score': total_max_score,
            'instructors': instructors_data,
            'inter_rater': {
                'pairwise': pairwise_irr
            }
        })
