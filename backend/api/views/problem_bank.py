import csv
from io import StringIO
import numpy as np
import warnings
from scipy import stats
from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework import generics, parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from accounts.permissions import IsInstructor
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import ensure_instructor, Instructor
from problems.models import ProblemBank, Problem, Rubric, InstructorProblemRating
from quizzes.models import Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot, QuizRatingCriterion, QuizSlotGrade
from problems.serializers import (
    ProblemBankSerializer, 
    ProblemSerializer, 
    ProblemSummarySerializer,
    RubricSerializer,
    InstructorProblemRatingSerializer
)


class ProblemBankViewSet(viewsets.ModelViewSet):
    serializer_class = ProblemBankSerializer
    permission_classes = [IsInstructor]

    def get_queryset(self):
        # Allow all instructors to see all banks (for rating/sharing purposes)
        return ProblemBank.objects.all()

    def perform_create(self, serializer):
        serializer.save(owner=ensure_instructor(self.request.user))

    def _ensure_owner(self, bank):
        instructor = ensure_instructor(self.request.user)
        if bank.owner != instructor:
            raise PermissionDenied('You do not own this problem bank.')

    def perform_update(self, serializer):
        self._ensure_owner(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_owner(instance)
        instance.delete()

    @action(detail=True, methods=['post'], parser_classes=[parsers.MultiPartParser])
    def import_from_csv(self, request, *args, **kwargs):
        bank = self.get_object()
        self._ensure_owner(bank)
        
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded_file = file_obj.read().decode('utf-8')
            io_string = StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            created_count = 0
            errors = []
            
            for row in reader:
                # Expected columns: statement, answer, group (optional), display_label (optional)
                statement = row.get('statement')
                answer = row.get('answer')
                
                if not statement or not answer:
                    continue
                    
                group = row.get('group') or ''
                display_label = row.get('display_label') or ''
                
                # Determine order
                last_order = bank.problems.aggregate(max_order=models.Max('order_in_bank'))['max_order'] or 0
                new_order = last_order + 1
                
                Problem.objects.create(
                    problem_bank=bank,
                    statement=statement,
                    answer=answer,
                    group=group,
                    display_label=display_label,
                    order_in_bank=new_order
                )
                created_count += 1
                
            return Response({'detail': f'Imported {created_count} problems.'})
            
        except Exception as e:
            return Response({'detail': f'Error processing file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


class ProblemBankRatingImportView(APIView):
    permission_classes = [IsInstructor]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request, bank_id):
        instructor = ensure_instructor(request.user)
        bank = get_object_or_404(ProblemBank, id=bank_id)
        
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        is_preview = request.data.get('preview') == 'true'

        try:
            # Read and decode file
            # Use utf-8-sig to handle BOM
            content = file_obj.read().decode('utf-8-sig')
            

            
            # Helper to check if a dialect/delimiter yields valid headers
            def get_valid_reader(content, dialect_or_delimiter):
                try:
                    io_string = StringIO(content)
                    reader = csv.DictReader(io_string, dialect=dialect_or_delimiter)
                    if not reader.fieldnames:
                        return None, None
                    
                    # Normalize headers
                    original_headers = reader.fieldnames
                    header_map = {h.strip().lower(): h for h in original_headers}
                    
                    if 'problem' in header_map:
                        return reader, header_map
                    return None, None
                except csv.Error:
                    return None, None

            reader = None
            header_map = None
            
            # 1. Try Sniffer
            try:
                dialect = csv.Sniffer().sniff(content[:1024])
                reader, header_map = get_valid_reader(content, dialect)
            except csv.Error:
                pass
            
            # 2. If Sniffer failed or didn't yield "Problem" column, try explicit delimiters
            if not reader:
                delimiters = [',', ';', '\t']
                for d in delimiters:
                    # Create a simple dialect with this delimiter
                    class SimpleDialect(csv.Dialect):
                        delimiter = d
                        quotechar = '"'
                        doublequote = True
                        skipinitialspace = True
                        lineterminator = '\r\n'
                        quoting = csv.QUOTE_MINIMAL
                    
                    reader, header_map = get_valid_reader(content, SimpleDialect)
                    if reader:
                        break
            
            if not reader or not header_map:
                 return Response({'detail': 'CSV must have a "Problem" column. Could not detect valid CSV format.'}, status=status.HTTP_400_BAD_REQUEST)
            
            original_headers = reader.fieldnames
            problem_col = header_map['problem']

            # If preview, return first 5 rows
            if is_preview:
                preview_rows = []
                for i, row in enumerate(reader):
                    if i >= 5:
                        break
                    preview_rows.append(row)
                
                return Response({
                    'preview': True,
                    'headers': original_headers,
                    'rows': preview_rows
                })

            # Import logic
            imported_count = 0
            
            # Identify criterion columns
            # All columns except the problem column are treated as criteria
            criterion_names = [h for h in original_headers if h != problem_col]
            
            for row in reader:
                problem_label = row.get(problem_col)
                if not problem_label:
                    continue
                
                # Find problem by label (display_label) or order?
                # display_label is a property, so we can't filter by it.
                # We expect the label to be the order number or "Problem X".
                
                problem = None
                
                # Try to parse order from label
                try:
                    # If label is just a number
                    order = int(problem_label)
                    problem = bank.problems.filter(order_in_bank=order).first()
                except ValueError:
                    # If label is "Problem X"
                    if problem_label.lower().startswith('problem '):
                        try:
                            order = int(problem_label.split(' ')[1])
                            problem = bank.problems.filter(order_in_bank=order).first()
                        except (ValueError, IndexError):
                            pass

                if not problem:
                    continue
                
                # Get or create rating object
                rating, _ = InstructorProblemRating.objects.get_or_create(
                    problem=problem,
                    instructor=instructor
                )
                
                for c_name in criterion_names:
                    val_str = row.get(c_name)
                    if not val_str:
                        continue
                    try:
                        # Support floats (e.g. 0.5)
                        val = float(val_str)
                    except ValueError:
                        continue
                        
                    # Find criterion ID
                    rubric = bank.get_rubric() # Returns dict
                    criteria = rubric.get('criteria', [])
                    
                    # Match by name OR id (case-insensitive)
                    c_id = None
                    c_name_clean = c_name.strip().lower()
                    
                    for c in criteria:
                        if c['name'].strip().lower() == c_name_clean:
                            c_id = c['id']
                            break
                        if str(c['id']).strip().lower() == c_name_clean:
                            c_id = c['id']
                            break
                            
                    if not c_id:
                        continue
                    
                    from problems.models import InstructorProblemRatingEntry, RubricCriterion, RubricScaleOption
                    
                    # We need the actual RubricCriterion model instance
                    criterion_obj = RubricCriterion.objects.filter(rubric__id=bank.rubric.id, criterion_id=c_id).first()

                    # Find the scale option
                    # We have `val` which is the value.
                    # Handle float comparison carefully? Exact match for now.
                    scale_option = RubricScaleOption.objects.filter(rubric__id=bank.rubric.id, value=val).first()
                    
                    if criterion_obj and scale_option:
                        InstructorProblemRatingEntry.objects.update_or_create(
                            rating=rating,
                            criterion=criterion_obj,
                            defaults={'scale_option': scale_option}
                        )
                        
                imported_count += 1

            return Response({'detail': f'Imported ratings for {imported_count} problems.'})

        except Exception as e:
            return Response({'detail': f'Error processing file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


def calculate_weighted_kappa(y1, y2, all_categories=None, label=None):
    # y1, y2 are lists of ratings
    # Assume scale is ordinal integers
    # all_categories: Optional list of all possible scale values to ensure matrix shape
    # label: Optional string description for logging

    
    # Ensure inputs are numpy arrays
    y1 = np.array(y1)
    y2 = np.array(y2)
    
    # Get unique categories
    if all_categories is not None:
        categories = np.array(all_categories)
        categories.sort()
    else:
        categories = np.unique(np.concatenate((y1, y2)))
        categories.sort()

    
    # Map categories to 0..k-1
    cat_map = {c: i for i, c in enumerate(categories)}
    y1_idx = np.array([cat_map[c] for c in y1])
    y2_idx = np.array([cat_map[c] for c in y2])
    
    k = len(categories)
    n = len(y1)
    
    if k < 2:
        return 1.0 # Perfect agreement if only 1 category
        
    # Confusion matrix
    conf_mat = np.zeros((k, k))
    for i in range(n):
        conf_mat[y1_idx[i], y2_idx[i]] += 1
        
    # Weights matrix (quadratic)
    w_mat = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            w_mat[i, j] = ((i - j) ** 2) / ((k - 1) ** 2)
            
    # Expected matrix
    row_sums = np.sum(conf_mat, axis=1)
    col_sums = np.sum(conf_mat, axis=0)
    expected_mat = np.outer(row_sums, col_sums) / n
    
    # Calculate Kappa
    numerator = np.sum(w_mat * conf_mat)
    denominator = np.sum(w_mat * expected_mat)
    
    if denominator == 0:
        return 1.0 if numerator == 0 else 0.0
        
    return 1.0 - (numerator / denominator)




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
            
            # Add weighted score and max score to each group's stats that appeared in this problem
            # Note: A problem belongs to one group. We just processed entries for one rating (one problem).
            # So `p_group` is consistent for this inner loop (iterating entries of one rating).
            # We need to perform this AFTER the entries loop.
            # But wait, the entries loop iterates `rating.entries.all()`. 
            # `p_group` variable will hold the last entry's group, which is correct (same problem).
            # This block was removed as the new group_stats accumulation handles it more generically.
            # if p_group:
            #      if 'weighted_score' not in group_stats[p_group]: group_stats[p_group]['weighted_score'] = []
            #      # We need the calculated weighted score for this specific rating instance.
            #      # Let's calculate it locally for this rating.
            #      current_rating_w_score = 0
            #      for entry in rating.entries.all():
            #          current_rating_w_score += entry.scale_option.value
            #      
            #      group_stats[p_group]['weighted_score'].append(current_rating_w_score)

            #      if 'total_max_score' not in group_stats[p_group]: group_stats[p_group]['total_max_score'] = []
            #      group_stats[p_group]['total_max_score'].append(total_max_score)

            means = {c: c_totals[c]/c_counts[c] for c in c_totals}

            
            # Add weighted score
            # Add weighted score (Problem-First Approach)
            # Calculate weighted score for EACH problem, then average them.
            bank_problem_weighted_scores = []
            
            for pid, p_data in problem_scores.items():
                # We only care about problems in THIS bank loop.
                # problem_scores accumulates globally? No, `problem_scores` variable is defined OUTSIDE the loop in line 598.
                # WAIT. `problem_scores` accumulates across ALL banks if defined outside.
                # However, inside this loop we only want problems for the CURRENT bank.
                # Checking line 598... yes, it is outside.
                # So `problem_scores` contains problems from previous iterations too?
                # Actually, I should filter `problem_scores` for the current bank or just calculate it locally.
                
                # Let's check if p_data['group'] corresponds to this bank? No, group doesn't link to bank directly easily here.
                # Easier: I have `data` (pid -> ratings) for this bank locally in this loop (lines 636-680).
                # But `problem_scores` has the nice pre-calculated structure.
                
                # Correct approach: Calculate weighted score for the problems we just processed in `data`.
                # We can re-use the logic or just do it on `data`.
                pass

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
                                global_criteria_data[c]['y1'].extend(c_y1)
                                global_criteria_data[c]['y2'].extend(c_y2)
                                # Note: Assuming scale is consistent across banks for the same criterion name.
                                # If mixed scales, this might be tricky. We use the most recent one found.
                                global_criteria_data[c]['scale'] = scale_vals
                
                # Calculate Overall if we have enough data

                # Since we iterate pairs, this might concatenate multiple pairs.
                # Usually Overall is calculated pairwise and then averaged, OR pooled.

                # The implementation in ProblemBankView was pooled per pair then averaged? 
                # Actually ProblemBankView separated pairs. 
                # Here we are inside `results` loop (per bank).
                # We want "Overall" for this bank.
                # If multiple raters, we should probably average the pairwise overall kappas? 
                
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
                # 'criteria' stores LIST of values (from multiple raters), so we average them first.
                
                # Check if we should use averaged values from logic above? 
                # The logic above populated `group_stats`. `problem_scores` is raw.
                
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
            
            # Average Weighted Score (normalized 0-1 usually, but here raw scores)
            # Actually frontend calculates normalized. Let's send raw weighted_score mean.
            w_scores = [r['means'].get('weighted_score', 0) for r in results]
            if w_scores:
                overall_bank_stats['weighted_score'] = np.mean(w_scores)
                
            # Average Total Max Score (needed for normalization in frontend)
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
                     # Usually 'Overall' is what we want? Or mean of dict?
                     # The frontend logic for displaying bank row IRR:
                     # if object, mean of values.
                     # Let's mirror that logic.
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
                # For groups logic, we might want 'total_max_score' mean too
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



class ProblemViewSet(viewsets.ModelViewSet):
    serializer_class = ProblemSerializer
    permission_classes = [IsInstructor]

    def get_queryset(self):
        return Problem.objects.select_related('problem_bank', 'problem_bank__owner').all()

    def perform_create(self, serializer):
        instructor = ensure_instructor(self.request.user)
        bank_id = self.request.data.get('problem_bank')
        bank = get_object_or_404(ProblemBank, id=bank_id)
        if bank.owner != instructor:
            raise PermissionDenied('Only the owner can add problems to this bank.')
        order = serializer.validated_data.get('order_in_bank')
        if order is None:
            last_order = bank.problems.aggregate(max_order=models.Max('order_in_bank'))['max_order'] or 0
            order = last_order + 1
        serializer.save(problem_bank=bank, order_in_bank=order)

    def perform_update(self, serializer):
        instructor = ensure_instructor(self.request.user)
        problem = serializer.instance
        if problem.problem_bank.owner != instructor:
            raise PermissionDenied('Only the bank owner can edit this problem.')
        bank = serializer.validated_data.get('problem_bank')
        if bank and bank.owner != instructor:
            raise PermissionDenied('Cannot move problem to another instructor bank')
        serializer.save()

    def perform_destroy(self, instance):
        instructor = ensure_instructor(self.request.user)
        if instance.problem_bank.owner != instructor:
            raise PermissionDenied('Only the bank owner can delete this problem.')
        super().perform_destroy(instance)


class ProblemBankProblemListCreate(generics.ListCreateAPIView):
    permission_classes = [IsInstructor]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ProblemSummarySerializer
        return ProblemSerializer

    def get_queryset(self):
        bank = self._get_bank()
        return Problem.objects.filter(problem_bank=bank)

    def perform_create(self, serializer):
        instructor = ensure_instructor(self.request.user)
        bank = self._get_bank()
        if bank.owner != instructor:
            raise PermissionDenied('Only the owner can add problems to this bank.')
        order = serializer.validated_data.get('order_in_bank')
        if order is None:
            last_order = bank.problems.aggregate(max_order=models.Max('order_in_bank'))['max_order'] or 0
            order = last_order + 1
        serializer.save(problem_bank=bank, order_in_bank=order)

    def _get_bank(self):
        if not hasattr(self, '_bank_cache'):
            self._bank_cache = get_object_or_404(ProblemBank, id=self.kwargs['bank_id'])
        return self._bank_cache


class ProblemBankRubricView(APIView):
    permission_classes = [IsInstructor]

    def _get_bank(self, request, bank_id):
        instructor = ensure_instructor(request.user)
        return get_object_or_404(ProblemBank, id=bank_id, owner=instructor)

    def get(self, request, bank_id):
        bank = get_object_or_404(ProblemBank, id=bank_id)
        # Check if user is owner or has access (for now just owner for editing, but maybe public for viewing?)
        # The requirement says "Add feature for instructors to rate problems in problem bank".
        # Assuming the owner sets the rubric.
        return Response(bank.get_rubric())

    def put(self, request, bank_id):
        bank = self._get_bank(request, bank_id)
        
        rubric_id = request.data.get('rubric_id')
        if rubric_id is not None:
            if rubric_id == '':
                bank.rubric = None
            else:
                rubric = get_object_or_404(Rubric, id=rubric_id)
                bank.rubric = rubric
            bank.save()
            return Response(bank.get_rubric())
        
        return Response({'detail': 'Rubric ID is required.'}, status=status.HTTP_400_BAD_REQUEST)


class InstructorProblemRatingView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, problem_id):
        instructor = ensure_instructor(request.user)
        problem = get_object_or_404(Problem, id=problem_id)
        
        # Check if rating exists
        try:
            rating = InstructorProblemRating.objects.get(problem=problem, instructor=instructor)
            serializer = InstructorProblemRatingSerializer(rating)
            return Response(serializer.data)
        except InstructorProblemRating.DoesNotExist:
            return Response({'entries': []})

    def put(self, request, problem_id):
        instructor = ensure_instructor(request.user)
        problem = get_object_or_404(Problem, id=problem_id)
        
        try:
            rating = InstructorProblemRating.objects.get(problem=problem, instructor=instructor)
            serializer = InstructorProblemRatingSerializer(rating, data=request.data)
        except InstructorProblemRating.DoesNotExist:
            serializer = InstructorProblemRatingSerializer(data=request.data)
            
        serializer.is_valid(raise_exception=True)
        serializer.save(problem=problem, instructor=instructor)
        return Response(serializer.data)
