import csv
from io import StringIO
import numpy as np
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


def calculate_weighted_kappa(y1, y2):
    # y1, y2 are lists of ratings
    # Assume scale is ordinal integers
    
    # Ensure inputs are numpy arrays
    y1 = np.array(y1, dtype=int)
    y2 = np.array(y2, dtype=int)
    
    # Get unique categories
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
                    # Calculate weighted score? (Assuming simple sum or average for now as not specified)
                    # Frontend expects 'weighted_score'.
                    # Let's sum values for now.
                    weighted_score = sum(ratings_dict.values())
                    
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
                             k = calculate_weighted_kappa(y1, y2)
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
                         k = calculate_weighted_kappa(all_y1, all_y2)
                         pairwise_irr.append({
                             'instructor1': r1,
                             'instructor2': r2,
                             'criteria_id': 'Overall',
                             'n': len(all_y1),
                             'kappa': k
                         })

        return Response({
            'bank': {
                'id': bank.id,
                'name': bank.name,
                'description': bank.description,
            },
            'rubric': bank.get_rubric(),
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
        
        for bank in banks:
            # Similar logic to ProblemBankAnalysisView but summarized
            ratings = InstructorProblemRating.objects.filter(
                problem__problem_bank=bank
            ).prefetch_related('entries', 'entries__scale_option', 'entries__criterion')
            
            if not ratings.exists():
                continue
                
            # Calculate average scores per criterion
            rubric = bank.get_rubric()
            rubric_criteria = {c['id']: c['name'] for c in rubric.get('criteria', [])}
            
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
                
                if pid not in data:
                    data[pid] = {}
                if iid not in data[pid]:
                    data[pid][iid] = {}
                
                for entry in r.entries.all():
                    c_id = entry.criterion.criterion_id
                    c_name = rubric_criteria.get(c_id, c_id)
                    
                    if c_name not in c_totals:
                        c_totals[c_name] = 0
                        c_counts[c_name] = 0
                    
                    c_totals[c_name] += entry.scale_option.value
                    c_counts[c_name] += 1
                    
                    data[pid][iid][c_name] = entry.scale_option.value
            
            means = {c: c_totals[c]/c_counts[c] for c in c_totals}
            
            # IRR
            irr = {}
            raters_list = list(raters)
            if len(raters_list) > 1:
                # Calculate IRR for each criterion
                for c in means.keys():
                    kappas = []
                    for i in range(len(raters_list)):
                        for j in range(i+1, len(raters_list)):
                            r1 = raters_list[i]
                            r2 = raters_list[j]
                            y1, y2 = [], []
                            for pid in data:
                                v1 = data[pid].get(r1, {}).get(c)
                                v2 = data[pid].get(r2, {}).get(c)
                                if v1 is not None and v2 is not None:
                                    y1.append(v1)
                                    y2.append(v2)
                            if len(y1) >= 5:
                                kappas.append(calculate_weighted_kappa(y1, y2))
                    if kappas:
                        irr[c] = np.mean(kappas)

            # Collect criteria values for ANOVA
            criteria_values = {} # criterion -> list of all values
            for r in ratings:
                for entry in r.entries.all():
                    c_id = entry.criterion.criterion_id
                    c_name = rubric_criteria.get(c_id, c_id)
                    if c_name not in criteria_values:
                        criteria_values[c_name] = []
                    criteria_values[c_name].append(entry.scale_option.value)

            results.append({
                'id': bank.id,
                'name': bank.name,
                'means': means,
                'inter_rater_reliability': irr,
                'criteria_values': criteria_values
            })
            
        # Perform ANOVA if requested or always?
        # Let's do ANOVA for each criterion across banks
        
        # We need to know the order of criteria to display them consistently
        # Let's assume a standard set of criteria names if possible, or union them.
        # For now, just return the data.
        
        # To support the "Order Analysis Criteria" requirement, we need to respect the rubric order.
        # Since we are aggregating across banks, they might have different rubrics.
        # But usually they share a rubric structure if they are being compared.
        # Let's try to get a "master" order from the first bank or just alphabetical?
        # The requirement said "as defined by the rubric".
        # If banks have different rubrics, comparison is hard.
        # Let's assume they are similar.
        
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
        sorted_criteria = sorted([c for c in all_criteria if c != 'weighted_score'], key=lambda x: (criteria_order_map.get(x, 999), x))

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
                    f_stat, p_val = stats.f_oneway(*groups)
                except Exception:
                    f_stat, p_val = None, None

                if f_stat is not None and (np.isinf(f_stat) or np.isnan(f_stat)):
                    f_stat = None
                if p_val is not None and (np.isinf(p_val) or np.isnan(p_val)):
                    p_val = None
                
                anova_results.append({
                    'criterion_id': cid,
                    'f_stat': float(f_stat) if f_stat is not None else None,
                    'p_value': float(p_val) if p_val is not None else None,
                    'significant': p_val < 0.05 if p_val is not None else False,
                    'banks_included': group_names
                })

        return Response({
            'banks': [{
                'id': r['id'], 
                'name': r['name'], 
                'means': r['means'],
                'inter_rater_reliability': r['inter_rater_reliability']
            } for r in results],
            'anova': anova_results,
            'criteria_order': sorted_criteria
        })


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
