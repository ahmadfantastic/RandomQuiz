from django.db import models
from django.db.models import Avg, Min, Max, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import ensure_instructor
from problems.models import Problem
from quizzes.models import Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot, QuizAttemptInteraction, QuizSlotGrade


class QuizAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(Quiz, id=quiz_id)
        if quiz.owner != instructor and not quiz.allowed_instructors.filter(id=instructor.id).exists():
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        # Get optional per-slot problem filters
        # Format: slot_filters={"slot_id": "problem_label", ...}
        slot_filters_param = request.query_params.get('slot_filters')
        slot_filters = {}
        if slot_filters_param:
            try:
                import json
                slot_filters = json.loads(slot_filters_param)
            except:
                pass
        
        # Get optional global problem filter (legacy support)
        problem_id = request.query_params.get('problem_id')
        
        attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False)
        
        # If filtering by problem, only include attempts that have that problem assigned
        if problem_id:
            attempts = attempts.filter(
                attempt_slots__assigned_problem_id=problem_id
            ).distinct()
        
        total_attempts = attempts.count()
        
        # Completion stats - since we only query completed attempts, completion rate is 100%
        # unless we want to compare against all attempts (including incomplete ones)
        all_attempts = QuizAttempt.objects.filter(quiz=quiz).count()
        completion_rate = (total_attempts / all_attempts * 100) if all_attempts > 0 else 0
        
        # Time distribution
        durations = []
        for attempt in attempts:
            if attempt.started_at and attempt.completed_at:
                diff = (attempt.completed_at - attempt.started_at).total_seconds()
                if diff > 0:
                    durations.append(diff / 60.0) # minutes

        time_stats = {
            'min': min(durations) if durations else 0,
            'max': max(durations) if durations else 0,
            'mean': sum(durations) / len(durations) if durations else 0,
            'median': sorted(durations)[len(durations) // 2] if durations else 0,
            'count': len(durations),
            'raw_values': durations
        }

        # Slot analytics
        slots_data = []
        quiz_slots = quiz.slots.all().order_by('order')
        
        # Pre-fetch all interactions for this quiz's attempts to avoid N+1 and reduce memory
        # Group by slot_id
        interactions_by_slot = {}
        # Use values() to avoid creating model instances
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
            
            # Calculate relative position if possible
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

        rubric = quiz.get_rubric()
        criteria = rubric.get('criteria', [])
        scale = rubric.get('scale', [])
        scale_values = [s['value'] for s in scale] if scale else []

        # Pre-fetch all attempt slots for these attempts to avoid N+1 and reduce memory
        # Use values() to avoid creating model instances
        all_attempt_slots = QuizAttemptSlot.objects.filter(
            attempt__in=attempts
        ).values(
            'id',
            'slot_id',
            'assigned_problem__order_in_bank',
            'assigned_problem__id',
            'assigned_problem__group',
            'answer_data',
            'attempt__started_at',
            'attempt__completed_at',
            'attempt__student_identifier',
            'attempt_id'
        )

        # Fetch grades and items
        # We need to map attempt_slot_id -> grade info
        grades = QuizSlotGrade.objects.filter(
            attempt_slot__attempt__in=attempts
        ).prefetch_related('items__rubric_item', 'items__selected_level')
        
        grades_map = {}
        for grade in grades:
            items_data = {}
            total_score = 0
            for item in grade.items.all():
                items_data[item.rubric_item.id] = item.selected_level.points
                total_score += item.selected_level.points
            
            grades_map[grade.attempt_slot_id] = {
                'total_score': total_score,
                'items': items_data
            }

        # Group attempt slots by slot_id
        attempt_slots_by_slot = {}
        for attempt_slot in all_attempt_slots:
            slot_id = attempt_slot['slot_id']
            if slot_id not in attempt_slots_by_slot:
                attempt_slots_by_slot[slot_id] = []
            
            # Calculate duration
            start = attempt_slot['attempt__started_at']
            end = attempt_slot['attempt__completed_at']
            duration = (end - start).total_seconds() / 60.0 if start and end else None
            attempt_slot['attempt__duration'] = duration
            
            # Attach grade info
            if attempt_slot['id'] in grades_map:
                attempt_slot['grade'] = grades_map[attempt_slot['id']]
            
            attempt_slots_by_slot[slot_id].append(attempt_slot)

        # Collect all word counts for global average
        all_word_counts = []

        for slot in quiz_slots:
            # Get pre-fetched slots for this slot
            slot_attempts_list = attempt_slots_by_slot.get(slot.id, [])
            
            # Check if this slot has a specific problem filter
            slot_filter = slot_filters.get(str(slot.id))
            
            filtered_slot_attempts = []
            if slot_filter and slot_filter != 'all':
                # Filter by problem label (order in bank)
                try:
                    filter_order = int(slot_filter.split()[-1])
                    filtered_slot_attempts = [
                        sa for sa in slot_attempts_list 
                        if sa['assigned_problem__order_in_bank'] == filter_order
                    ]
                except (ValueError, IndexError):
                    filtered_slot_attempts = slot_attempts_list
            elif problem_id:
                # Fall back to global filter
                try:
                    pid = int(problem_id)
                    filtered_slot_attempts = [
                        sa for sa in slot_attempts_list 
                        if sa['assigned_problem__id'] == pid
                    ]
                except ValueError:
                    filtered_slot_attempts = slot_attempts_list
            else:
                filtered_slot_attempts = slot_attempts_list
            
            # Problem distribution
            prob_stats = {}
            prob_order = {}  # Track order_in_bank for each problem
            group_stats = {} # group_name -> { criterion_id -> { value -> count } }
            
            for sa in filtered_slot_attempts:
                order = sa['assigned_problem__order_in_bank']
                label = f"Problem {order}"
                group_name = sa.get('assigned_problem__group') or 'Ungrouped'
                
                if group_name not in group_stats:
                    group_stats[group_name] = {}
                
                if label not in prob_stats:
                    prob_stats[label] = {
                        'count': 0,
                        'total_score': 0,
                        'total_time': 0,
                        'total_words': 0,
                        'scores_count': 0, # Denominator for score avg (only graded)
                        'times_count': 0, # Denominator for time avg (only completed attempts)
                        'words_count': 0, # Denominator for word avg (only text answers)
                        'criteria_scores': {}, # criterion_id -> {total, count}
                        'rating_counts': {}, # criterion_id -> {value -> count}
                        'problem_id': sa['assigned_problem__id']
                    }
                
                stats = prob_stats[label]
                stats['count'] += 1
                prob_order[label] = order
                
                # Time
                if sa.get('attempt__duration') is not None:
                     stats['total_time'] += sa['attempt__duration']
                     stats['times_count'] += 1

                # Word count
                if sa['answer_data'] and 'text' in sa['answer_data']:
                    text = sa['answer_data']['text']
                    count = len(text.split())
                    stats['total_words'] += count
                    stats['words_count'] += 1
                
                # Score
                if 'grade' in sa:
                    grade = sa['grade']
                    stats['total_score'] += grade['total_score']
                    stats['scores_count'] += 1
                    
                    for c_id, score in grade['items'].items():
                        if c_id not in stats['criteria_scores']:
                            stats['criteria_scores'][c_id] = {'total': 0, 'count': 0}
                        stats['criteria_scores'][c_id]['total'] += score
                        stats['criteria_scores'][c_id]['count'] += 1

                # Rating distribution
                if sa['answer_data'] and 'ratings' in sa['answer_data']:
                    ratings = sa['answer_data']['ratings']
                    for c_id, val in ratings.items():
                        if c_id not in stats['rating_counts']:
                            stats['rating_counts'][c_id] = {}
                        if val not in stats['rating_counts'][c_id]:
                            stats['rating_counts'][c_id][val] = 0
                        stats['rating_counts'][c_id][val] += 1

                        # Aggregate for average calculation
                        if c_id not in stats['criteria_scores']:
                            stats['criteria_scores'][c_id] = {'total': 0, 'count': 0}
                        stats['criteria_scores'][c_id]['total'] += val
                        stats['criteria_scores'][c_id]['total'] += val
                        stats['criteria_scores'][c_id]['count'] += 1

                        # Group aggregation
                        if c_id not in group_stats[group_name]:
                            group_stats[group_name][c_id] = {}
                        if val not in group_stats[group_name][c_id]:
                            group_stats[group_name][c_id][val] = 0
                        group_stats[group_name][c_id][val] += 1

            prob_dist_list = []
            for label, stats in prob_stats.items():
                avg_criteria = {}
                for c_id, c_stats in stats['criteria_scores'].items():
                    avg_criteria[c_id] = c_stats['total'] / c_stats['count'] if c_stats['count'] > 0 else 0

                prob_dist_list.append({
                    'label': label,
                    'problem_id': stats['problem_id'],
                    'count': stats['count'],
                    'avg_score': stats['total_score'] / stats['scores_count'] if stats['scores_count'] > 0 else 0,
                    'avg_time': stats['total_time'] / stats['times_count'] if stats['times_count'] > 0 else 0,
                    'avg_words': stats['total_words'] / stats['words_count'] if stats['words_count'] > 0 else 0,
                    'avg_words': stats['total_words'] / stats['words_count'] if stats['words_count'] > 0 else 0,
                    'avg_criteria_scores': avg_criteria,
                    'criteria_distributions': []
                })
                
                # Format rating distribution for this problem
                if stats['rating_counts']:
                    c_dists = []
                    for criterion in criteria:
                        c_id = criterion['id']
                        c_name = criterion['name']
                        
                        counts = stats['rating_counts'].get(c_id, {})
                        # Ensure all scale values are present
                        dist_data = []
                        total_responses = sum(counts.values())
                        
                        for val in scale_values:
                            count = counts.get(val, 0)
                            percentage = (count / total_responses * 100) if total_responses > 0 else 0
                            label = next((s['label'] for s in scale if s['value'] == val), str(val))
                            dist_data.append({
                                'value': val,
                                'label': label,
                                'count': count,
                                'percentage': percentage
                            })
                            
                        c_dists.append({
                            'criterion_id': c_id,
                            'name': c_name,
                            'distribution': dist_data,
                            'total': total_responses
                        })
                    prob_dist_list[-1]['criteria_distributions'] = c_dists

            # Sort by order in bank
            prob_dist_list.sort(key=lambda x: prob_order.get(x['label'], 0))

            slot_data = {
                'id': slot.id,
                'label': slot.label,
                'response_type': slot.response_type,
                'problem_distribution': prob_dist_list,
                'interactions': interactions_by_slot.get(slot.id, [])
            }

            if slot.response_type == QuizSlot.ResponseType.OPEN_TEXT:
                word_counts = []
                for sa in filtered_slot_attempts:
                    answer_data = sa['answer_data']
                    if answer_data and 'text' in answer_data:
                        text = answer_data['text']
                        count = len(text.split())
                        if count > 0:
                            word_counts.append(count)
                            all_word_counts.append(count)
                
                slot_data['data'] = {
                    'min': min(word_counts) if word_counts else 0,
                    'max': max(word_counts) if word_counts else 0,
                    'mean': sum(word_counts) / len(word_counts) if word_counts else 0,
                    'median': sorted(word_counts)[len(word_counts) // 2] if word_counts else 0,
                    'count': len(word_counts),
                    'raw_values': word_counts
                }
            
            elif slot.response_type == QuizSlot.ResponseType.RATING:
                # Per-criterion distribution
                criteria_stats = []
                
                for criterion in criteria:
                    c_id = criterion['id']
                    c_name = criterion['name']
                    
                    # Initialize counts for each scale value
                    counts = {val: 0 for val in scale_values}
                    total_responses = 0
                    
                    for sa in filtered_slot_attempts:
                        answer_data = sa['answer_data']
                        if answer_data and 'ratings' in answer_data:
                            ratings = answer_data['ratings']
                            if c_id in ratings:
                                val = ratings[c_id]
                                if val in counts:
                                    counts[val] += 1
                                    total_responses += 1
                    
                    # Format for chart
                    dist_data = []
                    for val in scale_values:
                        count = counts[val]
                        percentage = (count / total_responses * 100) if total_responses > 0 else 0
                        # Find label for value
                        label = next((s['label'] for s in scale if s['value'] == val), str(val))
                        dist_data.append({
                            'value': val,
                            'label': label,
                            'count': count,
                            'percentage': percentage
                        })
                    
                    criteria_stats.append({
                        'criterion_id': c_id,
                        'name': c_name,
                        'distribution': dist_data,
                        'total': total_responses
                    })
                
                # Format group stats
                grouped_charts_data = []
                sorted_group_names = sorted(group_stats.keys())
                for group_name in sorted_group_names:
                    g_counts = group_stats[group_name]
                    g_criteria_data = []
                    for criterion in criteria:
                        c_id = criterion['id']
                        c_name = criterion['name']
                        c_counts = g_counts.get(c_id, {})
                        
                        dist_data = []
                        total_c = sum(c_counts.values())
                        
                        for s_opt in scale:
                            val = s_opt['value']
                            count = c_counts.get(val, 0)
                            percentage = (count / total_c * 100) if total_c > 0 else 0
                            dist_data.append({
                                'label': s_opt['label'],
                                'value': val,
                                'count': count,
                                'percentage': percentage
                            })
                        g_criteria_data.append({
                            'name': c_name,
                            'distribution': dist_data
                        })
                    grouped_charts_data.append({
                        'group': group_name,
                        'data': {'criteria': g_criteria_data}
                    })

                slot_data['data'] = {
                    'criteria': criteria_stats,
                    'grouped_data': grouped_charts_data
                }

            slots_data.append(slot_data)

        # Get all unique problems used in this quiz for the filter dropdown
        all_problems = Problem.objects.filter(
            slot_links__quiz_slot__quiz=quiz
        ).distinct().order_by('order_in_bank')
        
        available_problems = [
            {'id': p.id, 'label': p.display_label}
            for p in all_problems
        ]
        
        word_count_stats = {
            'min': min(all_word_counts) if all_word_counts else 0,
            'max': max(all_word_counts) if all_word_counts else 0,
            'mean': sum(all_word_counts) / len(all_word_counts) if all_word_counts else 0,
            'median': sorted(all_word_counts)[len(all_word_counts) // 2] if all_word_counts else 0,
        }

        # Calculate average quiz score
        # We need to sum up all grades for each attempt
        # We already fetched grades in 'grades_map' (attempt_slot_id -> grade info)
        # But we need to group by attempt
        
        attempt_scores = {}
        for attempt_slot in all_attempt_slots:
            attempt_id = attempt_slot.get('attempt_id') # We didn't fetch attempt_id explicitly in values() but we can get it
            # Wait, we fetched 'attempt__student_identifier' etc but not 'attempt_id' directly in the values() call?
            # Let's check the values() call again.
            pass
        
        # Calculate score stats
        # We annotate each attempt with its total score, then aggregate min/max/avg
        
        score_stats = attempts.annotate(
            score=Coalesce(models.Sum('attempt_slots__grade__items__selected_level__points'), 0.0)
        ).aggregate(
            min_score=models.Min('score'),
            max_score=models.Max('score'),
            avg_score=models.Avg('score')
        )
        
        avg_score = score_stats['avg_score'] or 0
        min_score = score_stats['min_score'] or 0
        max_score = score_stats['max_score'] or 0

        # Calculate Cronbach's Alpha
        cronbach_alpha = None
        try:
            # 1. Identify rating slots and criteria
            rating_slots = [s for s in quiz_slots if s.response_type == QuizSlot.ResponseType.RATING]
            if rating_slots and criteria:
                # Items are (slot_id, criterion_id)
                # We need to map attempt_id -> { (slot_id, c_id): value }
                attempt_ratings = {}
                
                # We need to iterate all_attempt_slots again
                for sa in all_attempt_slots:
                    a_id = sa['attempt_id']
                    if a_id not in attempt_ratings:
                        attempt_ratings[a_id] = {}
                    
                    if sa['answer_data'] and 'ratings' in sa['answer_data']:
                        ratings = sa['answer_data']['ratings']
                        for c_id, val in ratings.items():
                            # Key: slot_id_criterion_id
                            key = f"{sa['slot_id']}_{c_id}"
                            attempt_ratings[a_id][key] = val

                # 2. Build matrix
                # Columns: all combinations of rating_slot.id and criterion.id
                item_keys = []
                for s in rating_slots:
                    for c in criteria:
                        item_keys.append(f"{s.id}_{c['id']}")
                
                K = len(item_keys)
                
                if K > 1:
                    # Rows
                    scores_matrix = []
                    for a_id, ratings in attempt_ratings.items():
                        # Check if complete (listwise deletion)
                        if all(k in ratings for k in item_keys):
                            row = [float(ratings[k]) for k in item_keys]
                            scores_matrix.append(row)
                    
                    N = len(scores_matrix)
                    if N > 1:
                        # 3. Calculate variances
                        item_variances = []
                        for col_idx in range(K):
                            col_values = [row[col_idx] for row in scores_matrix]
                            mean = sum(col_values) / N
                            var = sum((x - mean) ** 2 for x in col_values) / (N - 1) # Sample variance
                            item_variances.append(var)
                        
                        total_scores = [sum(row) for row in scores_matrix]
                        mean_total = sum(total_scores) / N
                        var_total = sum((x - mean_total) ** 2 for x in total_scores) / (N - 1)
                        
                        if var_total > 0:
                            cronbach_alpha = (K / (K - 1)) * (1 - (sum(item_variances) / var_total))
        except Exception as e:
            print(f"Error calculating Cronbach's Alpha: {e}")
            pass

        return Response({
            'avg_score': avg_score,
            'min_score': min_score,
            'max_score': max_score,
            'completion_rate': completion_rate,
            'total_attempts': total_attempts,
            'time_distribution': time_stats,
            'slots': slots_data,
            'interactions': [],
            'available_problems': available_problems,
            'available_problems': available_problems,
            'word_count_stats': word_count_stats,
            'cronbach_alpha': cronbach_alpha
        })


class QuizSlotProblemStudentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id, slot_id, problem_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(Quiz, id=quiz_id)
        if quiz.owner != instructor and not quiz.allowed_instructors.filter(id=instructor.id).exists():
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        slot = get_object_or_404(QuizSlot, id=slot_id, quiz=quiz)
        
        # Fetch attempts that have this problem assigned for this slot
        attempts = QuizAttempt.objects.filter(
            quiz=quiz,
            attempt_slots__slot=slot,
            attempt_slots__assigned_problem_id=problem_id,
            completed_at__isnull=False
        ).select_related('quiz').prefetch_related('attempt_slots')

        students_data = []
        
        for attempt in attempts:
            # Find the specific slot attempt
            # Since we filtered by attempt_slots, we know it exists.
            # But we need to grab the specific one efficiently.
            # We can use the prefetch or just query again if list is small.
            # Let's iterate the prefetched slots.
            target_slot_attempt = None
            for sa in attempt.attempt_slots.all():
                if sa.slot_id == slot.id and sa.assigned_problem_id == problem_id:
                    target_slot_attempt = sa
                    break
            
            if not target_slot_attempt:
                continue

            # Calculate duration
            duration = 0
            if attempt.started_at and attempt.completed_at:
                duration = (attempt.completed_at - attempt.started_at).total_seconds() / 60.0

            # Get grade info
            grade_info = {
                'total_score': 0,
                'items': {}
            }
            try:
                grade = QuizSlotGrade.objects.get(attempt_slot=target_slot_attempt)
                for item in grade.items.all():
                    grade_info['items'][item.rubric_item.id] = item.selected_level.points
                    grade_info['total_score'] += item.selected_level.points
            except QuizSlotGrade.DoesNotExist:
                pass

            # Word count
            word_count = 0
            if target_slot_attempt.answer_data and 'text' in target_slot_attempt.answer_data:
                word_count = len(target_slot_attempt.answer_data['text'].split())

            # Ratings
            ratings = {}
            if target_slot_attempt.answer_data and 'ratings' in target_slot_attempt.answer_data:
                ratings = target_slot_attempt.answer_data['ratings']

            students_data.append({
                'student_identifier': attempt.student_identifier,
                'attempt_id': attempt.id,
                'score': grade_info['total_score'],
                'criteria_scores': grade_info['items'],
                'time_taken': duration,
                'word_count': word_count,
                'ratings': ratings,
            })

        return Response(students_data)


class QuizOverviewAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(Quiz, id=quiz_id)
        if quiz.owner != instructor and not quiz.allowed_instructors.filter(id=instructor.id).exists():
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False).annotate(
            score=Sum('attempt_slots__grade__items__selected_level__points')
        )
        total_attempts = attempts.count()
        
        all_attempts = QuizAttempt.objects.filter(quiz=quiz).count()
        completion_rate = (total_attempts / all_attempts * 100) if all_attempts > 0 else 0
        
        durations = []
        for attempt in attempts:
            if attempt.started_at and attempt.completed_at:
                diff = (attempt.completed_at - attempt.started_at).total_seconds()
                if diff > 0:
                    durations.append(diff / 60.0) # minutes

        time_stats = {
            'min': min(durations) if durations else 0,
            'max': max(durations) if durations else 0,
            'mean': sum(durations) / len(durations) if durations else 0,
            'median': sorted(durations)[len(durations) // 2] if durations else 0,
            'count': len(durations),
            'raw_values': durations
        }

        return Response({
            'total_attempts': total_attempts,
            'completion_rate': completion_rate,
            'avg_score': attempts.aggregate(Avg('score'))['score__avg'] or 0,
            'min_score': attempts.aggregate(Min('score'))['score__min'] or 0,
            'max_score': attempts.aggregate(Max('score'))['score__max'] or 0,
            'time_distribution': time_stats,
        })


class QuizInteractionAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(Quiz, id=quiz_id)
        if quiz.owner != instructor and not quiz.allowed_instructors.filter(id=instructor.id).exists():
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False)
        
        # Optional problem filter
        problem_id = request.query_params.get('problem_id')
        if problem_id:
            attempts = attempts.filter(attempt_slots__assigned_problem_id=problem_id).distinct()

        quiz_slots = quiz.slots.all().order_by('order')
        
        interactions_by_slot = {}
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

        slots_data = []
        for slot in quiz_slots:
            if slot.id in interactions_by_slot:
                slots_data.append({
                    'id': slot.id,
                    'label': slot.label,
                    'interactions': interactions_by_slot[slot.id]
                })

        return Response(slots_data)


class QuizSlotAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id, slot_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(Quiz, id=quiz_id)
        if quiz.owner != instructor and not quiz.allowed_instructors.filter(id=instructor.id).exists():
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        slot = get_object_or_404(QuizSlot, id=slot_id, quiz=quiz)
        
        attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False)
        
        # Optional problem filter
        problem_id = request.query_params.get('problem_id')
        if problem_id:
            attempts = attempts.filter(attempt_slots__assigned_problem_id=problem_id).distinct()

        # Fetch attempt slots for this slot
        attempt_slots = QuizAttemptSlot.objects.filter(
            attempt__in=attempts,
            slot=slot
        ).select_related('assigned_problem')
        
        # Problem distribution
        problem_counts = {}
        problem_details = {}
        problem_stats = {} # pid -> {total_score, total_time, total_words, total_ratings, count}
        
        for attempt_slot in attempt_slots:
            problem = attempt_slot.assigned_problem
            if problem:
                pid = problem.id
                if pid not in problem_counts:
                    problem_counts[pid] = 0
                    problem_details[pid] = {
                        'id': pid,
                        'statement': problem.statement, # Assuming statement is what we want
                        'display_label': problem.display_label,
                        'order_in_bank': problem.order_in_bank,
                        'group': problem.group
                    }
                    problem_stats[pid] = {
                        'total_score': 0,
                        'total_time': 0,
                        'total_words': 0,
                        'ratings': {} # criterion_name -> total_value
                    }
                
                problem_counts[pid] += 1
                
                # Calculate stats
                stats = problem_stats[pid]
                
                # Score
                try:
                    if hasattr(attempt_slot, 'grade'):
                        grade = attempt_slot.grade
                        for item in grade.items.all():
                            stats['total_score'] += item.selected_level.points
                except:
                    pass

                # Time
                if attempt_slot.attempt.started_at and attempt_slot.attempt.completed_at:
                    diff = (attempt_slot.attempt.completed_at - attempt_slot.attempt.started_at).total_seconds()
                    if diff > 0:
                        stats['total_time'] += diff / 60.0

                # Words
                if slot.response_type == 'open_text':
                    answer = attempt_slot.answer_data.get('text', '') if attempt_slot.answer_data else ''
                    if answer:
                        stats['total_words'] += len(answer.split())
                
                # Ratings
                if slot.response_type == 'rating':
                    ratings = attempt_slot.answer_data.get('ratings', {}) if attempt_slot.answer_data else {}
                    for c_name, value in ratings.items():
                        if c_name not in stats['ratings']:
                            stats['ratings'][c_name] = {'total': 0, 'count': 0}
                        stats['ratings'][c_name]['total'] += value
                        stats['ratings'][c_name]['count'] += 1

        problem_distribution = []
        for pid, count in problem_counts.items():
            details = problem_details[pid]
            stats = problem_stats[pid]
            
            avg_criteria_scores = {}
            for c_name, c_data in stats['ratings'].items():
                if c_data['count'] > 0:
                    avg_criteria_scores[c_name] = c_data['total'] / c_data['count']

            problem_distribution.append({
                'problem_id': pid,
                'count': count,
                'percentage': (count / len(attempt_slots) * 100) if len(attempt_slots) > 0 else 0,
                'label': details['display_label'], # Use display_label for frontend
                'statement': details['statement'],
                'order_in_bank': details['order_in_bank'],
                'group': details['group'],
                'avg_score': stats['total_score'] / count if count > 0 else 0,
                'avg_time': stats['total_time'] / count if count > 0 else 0,
                'avg_words': stats['total_words'] / count if count > 0 else 0,
                'avg_criteria_scores': avg_criteria_scores
            })
        
        problem_distribution.sort(key=lambda x: x['order_in_bank'])

        data = {}
        if slot.response_type == 'open_text':
            word_counts = []
            for attempt_slot in attempt_slots:
                answer = attempt_slot.answer_data.get('text', '') if attempt_slot.answer_data else ''
                if answer:
                    word_counts.append(len(answer.split()))
            
            data = {
                'min': min(word_counts) if word_counts else 0,
                'max': max(word_counts) if word_counts else 0,
                'mean': sum(word_counts) / len(word_counts) if word_counts else 0,
                'count': len(word_counts),
                'raw_values': word_counts
            }
        
        elif slot.response_type == 'rating':
            # Rating analysis logic
            rubric = quiz.get_rubric()
            criteria = rubric.get('criteria', [])
            scale = rubric.get('scale', [])
            
            # Use rubric scale if available, otherwise we'll discover values
            known_scale_values = set(s['value'] for s in scale) if scale else set()
            
            # Create a map of value -> label
            value_to_label = {s['value']: s['label'] for s in scale} if scale else {}
            
            # We will store stats in a more flexible way
            # criteria_stats[name] = { 'values': [], 'distribution': { val: count } }
            criteria_stats = {} 
            
            # Create a mapping from ID/Name to canonical Name
            # We want to merge "SC" (id) and "Scenario Quality (SC)" (name) into one entry
            canonical_names = {} # key -> canonical_name
            
            # Pre-populate with rubric criteria to ensure order/existence
            for c in criteria:
                c_name = c['name']
                c_id = c.get('id')
                
                criteria_stats[c_name] = {
                    'distribution': {v: 0 for v in known_scale_values}, 
                    'values': []
                }
                
                # Map name to itself
                canonical_names[c_name] = c_name
                canonical_names[c_name.lower()] = c_name # case insensitive
                
                # Map ID to name if available
                if c_id:
                    canonical_names[c_id] = c_name
                    canonical_names[c_id.lower()] = c_name

            groups = set()
            grouped_stats = {} # group -> { criteria_name -> { distribution, values } }

            for attempt_slot in attempt_slots:
                group = attempt_slot.assigned_problem.group if attempt_slot.assigned_problem else 'Ungrouped'
                groups.add(group)
                if group not in grouped_stats:
                    grouped_stats[group] = {}

                ratings = attempt_slot.answer_data.get('ratings', {}) if attempt_slot.answer_data else {}
                for raw_c_name, value in ratings.items():
                    # Normalize name (strip whitespace)
                    normalized_key = raw_c_name.strip()
                    
                    # Resolve to canonical name if possible
                    if normalized_key in canonical_names:
                        c_name = canonical_names[normalized_key]
                    elif normalized_key.lower() in canonical_names:
                        c_name = canonical_names[normalized_key.lower()]
                    else:
                        # Unknown criterion, treat as new
                        c_name = normalized_key
                        # Add to mapping for future consistency in this loop
                        canonical_names[normalized_key] = c_name
                        canonical_names[normalized_key.lower()] = c_name
                    
                    # Ensure criterion exists in stats
                    if c_name not in criteria_stats:
                        criteria_stats[c_name] = {'distribution': {}, 'values': []}
                    
                    # Ensure criterion exists in grouped stats
                    if c_name not in grouped_stats[group]:
                        grouped_stats[group][c_name] = {'distribution': {}, 'values': []}

                    # Update Overall
                    if value not in criteria_stats[c_name]['distribution']:
                        criteria_stats[c_name]['distribution'][value] = 0
                    criteria_stats[c_name]['distribution'][value] += 1
                    criteria_stats[c_name]['values'].append(value)
                    
                    # Update Grouped
                    if value not in grouped_stats[group][c_name]['distribution']:
                        grouped_stats[group][c_name]['distribution'][value] = 0
                    grouped_stats[group][c_name]['distribution'][value] += 1
                    grouped_stats[group][c_name]['values'].append(value)
                    
                    # Track seen values for scale
                    known_scale_values.add(value)

            # Re-construct scale from all seen values + rubric values, sorted
            final_scale_values = sorted(list(known_scale_values))
            
            # Format for response
            formatted_criteria = []
            # Use rubric order for known criteria, then append others
            rubric_c_names = [c['name'] for c in criteria]
            all_c_names = rubric_c_names + [name for name in criteria_stats.keys() if name not in rubric_c_names]
            
            for c_name in all_c_names:
                dist = []
                total_count = len(criteria_stats[c_name]['values'])
                for v in final_scale_values:
                    count = criteria_stats[c_name]['distribution'].get(v, 0)
                    percentage = (count / total_count * 100) if total_count > 0 else 0
                    dist.append({
                        'value': v,
                        'label': value_to_label.get(v, str(v)), # Use label from rubric or value as string
                        'count': count,
                        'percentage': percentage
                    })
                formatted_criteria.append({
                    'name': c_name,
                    'distribution': dist
                })
            
            data['criteria'] = formatted_criteria
            
            # Format grouped data
            formatted_grouped = []
            for group in sorted(list(groups)):
                g_criteria = []
                for c_name in all_c_names:
                    dist = []
                    # Check if this group has data for this criterion
                    if c_name in grouped_stats[group]:
                        total_count = len(grouped_stats[group][c_name]['values'])
                        for v in final_scale_values:
                            count = grouped_stats[group][c_name]['distribution'].get(v, 0)
                            percentage = (count / total_count * 100) if total_count > 0 else 0
                            dist.append({
                                'value': v,
                                'label': value_to_label.get(v, str(v)),
                                'count': count,
                                'percentage': percentage
                            })
                    else:
                        # Empty distribution for this group/criterion
                        for v in final_scale_values:
                            dist.append({
                                'value': v, 
                                'label': value_to_label.get(v, str(v)),
                                'count': 0,
                                'percentage': 0
                            })
                            
                    g_criteria.append({
                        'name': c_name,
                        'distribution': dist
                    })
                formatted_grouped.append({
                    'group': group,
                    'data': {'criteria': g_criteria}
                })
            
            data['grouped_data'] = formatted_grouped

        return Response({
            'id': slot.id,
            'label': slot.label,
            'response_type': slot.response_type,
            'data': data,
            'problem_distribution': problem_distribution
        })
