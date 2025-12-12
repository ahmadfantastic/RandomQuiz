from django.db import models
from django.db.models import Avg, Min, Max, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import ensure_instructor
from problems.models import Problem, InstructorProblemRating
from .utils import calculate_weighted_kappa, calculate_average_nearest
from .kappa import quadratic_weighted_kappa
from scipy import stats as sp_stats
from statistics import median_low, mean
from django.http import HttpResponse
from quizzes.models import Quiz, QuizSlot, QuizAttempt, QuizAttemptSlot, QuizAttemptInteraction, QuizSlotGrade, QuizRatingCriterion, QuizRatingScaleOption
import csv


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

                # Calculate Cronbach's Alpha for this slot
                slot_cronbach_alpha = None
                try:
                    # 1. Gather data: attempt_id -> { criterion_id: value }
                    # We need to filter attempts that have answered this slot
                    # Calculate Cronbach's Alpha
                    slot_cronbach_alpha = None
                    try:
                        criteria = QuizRatingCriterion.objects.filter(quiz=quiz).order_by('order')
                        if criteria:
                            slot_attempt_ratings = {}
                            for attempt_slot in attempt_slots:
                                a_id = attempt_slot.attempt_id
                                if attempt_slot.answer_data and 'ratings' in attempt_slot.answer_data:
                                    slot_attempt_ratings[a_id] = attempt_slot.answer_data['ratings']
                            
                            # Build matrix
                            # Columns: criteria ids
                            existing_c_ids = set()
                            for r_map in slot_attempt_ratings.values():
                                existing_c_ids.update(r_map.keys())
                            
                            active_criteria = [c for c in criteria if c.criterion_id in existing_c_ids]
                            item_keys = [c.criterion_id for c in active_criteria]
                            K = len(item_keys)
                            
                            if K > 1:
                                scores_matrix = []
                                for ratings in slot_attempt_ratings.values():
                                    # Listwise deletion
                                    if all(k in ratings for k in item_keys):
                                        row = [float(ratings[k]) for k in item_keys]
                                        scores_matrix.append(row)
                                
                                N = len(scores_matrix)

                                if N > 1:
                                    item_variances = []
                                    for col_idx in range(K):
                                        col_values = [row[col_idx] for row in scores_matrix]
                                        mean = sum(col_values) / N
                                        var = sum((x - mean) ** 2 for x in col_values) / (N - 1)
                                        item_variances.append(var)
                                    
                                    total_scores = [sum(row) for row in scores_matrix]
                                    mean_total = sum(total_scores) / N
                                    var_total = sum((x - mean_total) ** 2 for x in total_scores) / (N - 1)
                                    
                                    if var_total > 0:
                                        slot_cronbach_alpha = (K / (K - 1)) * (1 - (sum(item_variances) / var_total))

                    except Exception as e:
                        print(f"Error calculating slot alpha in view: {e}")

                    data = {
                        'criteria': criteria_stats,
                        'grouped_data': grouped_charts_data,
                        'cronbach_alpha': slot_cronbach_alpha
                    }
                except Exception as e:
                    print(f"Error calculating per-slot Cronbach's Alpha: {e}")

                slot_data['data'] = {
                    'criteria': criteria_stats,
                    'grouped_data': grouped_charts_data,
                    'cronbach_alpha': slot_cronbach_alpha
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
            'word_count_stats': word_count_stats
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

        # Calculate word count stats for open text responses
        all_word_counts = []
        text_slots_data = QuizAttemptSlot.objects.filter(
            attempt__quiz=quiz,
            attempt__completed_at__isnull=False,
            slot__response_type=QuizSlot.ResponseType.OPEN_TEXT
        ).values_list('answer_data', flat=True)
        
        for data in text_slots_data:
            if data and 'text' in data:
                text = data['text']
                count = len(text.split())
                if count > 0:
                    all_word_counts.append(count)

        word_count_stats = {
            'min': min(all_word_counts) if all_word_counts else 0,
            'max': max(all_word_counts) if all_word_counts else 0,
            'mean': sum(all_word_counts) / len(all_word_counts) if all_word_counts else 0,
            'median': sorted(all_word_counts)[len(all_word_counts) // 2] if all_word_counts else 0,
            'count': len(all_word_counts),
        }

        return Response({
            'total_attempts': total_attempts,
            'completion_rate': completion_rate,
            'avg_score': attempts.aggregate(Avg('score'))['score__avg'] or 0,
            'min_score': attempts.aggregate(Min('score'))['score__min'] or 0,
            'max_score': attempts.aggregate(Max('score'))['score__max'] or 0,
            'time_distribution': time_stats,
            'word_count_stats': word_count_stats,
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
        
        # Check for CSV download
        if request.query_params.get('download') == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{quiz.title}_interactions.csv"'
            
            writer = csv.writer(response)
            writer.writerow([
                'Student ID', 
                'Slot', 
                'Event Type', 
                'Timestamp', 
                'Relative Position (%)', 
                'Metadata', 
                'Attempt Started', 
                'Attempt Completed'
            ])
            
            # Map slot IDs to labels
            slot_map = {s.id: s.label or f"Slot {s.order}" for s in quiz_slots}
            
            interactions = QuizAttemptInteraction.objects.filter(
                attempt_slot__attempt__in=attempts
            ).select_related('attempt_slot', 'attempt_slot__attempt', 'attempt_slot__slot').order_by('created_at')
            
            for interaction in interactions:
                # Calculate relative position
                position = 0
                attempt = interaction.attempt_slot.attempt
                start = attempt.started_at
                end = attempt.completed_at
                
                if start and end:
                    total_duration = (end - start).total_seconds()
                    if total_duration > 0:
                        event_time = (interaction.created_at - start).total_seconds()
                        position = min(max(event_time / total_duration, 0), 1) * 100
                
                writer.writerow([
                    attempt.student_identifier,
                    slot_map.get(interaction.attempt_slot.slot_id, 'Unknown Slot'),
                    interaction.event_type,
                    interaction.created_at.isoformat() if interaction.created_at else '',
                    f"{position:.1f}",
                    interaction.metadata,
                    start.isoformat() if start else '',
                    end.isoformat() if end else ''
                ])
                
            return response

        # Check for Metrics CSV download
        if request.query_params.get('download') == 'metrics':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{quiz.title}_interaction_metrics.csv"'
            
            writer = csv.writer(response)
            writer.writerow([
                'Student ID', 
                'Slot', 
                'Initial Planning Latency (s)', 
                'Revision Ratio', 
                'Burstiness (>10s)', 
                'Text Production Rate (WPM)',
                'Active Writing Time (min)',
                'Final Word Count'
            ])
            
            slot_map = {s.id: s.label or f"Slot {s.order}" for s in quiz_slots}
            
            # Group interactions by attempt_slot
            # optimizing query to fetch related data
            interactions = QuizAttemptInteraction.objects.filter(
                attempt_slot__attempt__in=attempts,
                attempt_slot__slot__response_type='open_text'
            ).select_related('attempt_slot', 'attempt_slot__attempt') \
             .order_by('attempt_slot_id', 'created_at')
            
            from collections import defaultdict
            grouped = defaultdict(list)
            for i in interactions:
                grouped[i.attempt_slot_id].append(i)
                
            for attempt_slot_id, slot_interactions in grouped.items():
                if not slot_interactions:
                    continue
                    
                first_i = slot_interactions[0]
                attempt = first_i.attempt_slot.attempt
                slot_label = slot_map.get(first_i.attempt_slot.slot_id, 'Unknown Slot')
                
                # Filter for typing events
                typing_events = [i for i in slot_interactions if i.event_type == 'typing']
                
                ipl = 0
                revision_ratio = 0
                burstiness = 0
                wpm = 0
                active_time = 0
                final_word_count = 0
                
                if typing_events:
                    # A. Initial Planning Latency
                    first_typing = typing_events[0]
                    if attempt.started_at:
                        ipl = (first_typing.created_at - attempt.started_at).total_seconds()
                        ipl = max(0, ipl)
                    
                    # B. Revision Ratio
                    total_removed = 0
                    total_added = 0
                    for event in typing_events:
                        meta = event.metadata or {}
                        diff = meta.get('diff')
                        if diff:
                            removed = diff.get('removed', '')
                            added = diff.get('added', '')
                            total_removed += len(removed)
                            total_added += len(added)
                        
                        # Get final length from last event metadata if available
                        if 'text_length' in meta:
                            # Estimate word count roughly chars / 5 or grab actual text if we had it (we don't store full text in interaction)
                            # Actually, we might need to rely on 'text_length' to estimate words
                            # Or if we have access to the attempt_slot.answer_data['text'] but that's not in interaction
                            # Using text_length / 5 is a reasonable proxy for WPM if actual word count isn't in metadata
                            final_word_count = meta['text_length'] / 5
                    
                    if total_added > 0:
                        revision_ratio = total_removed / total_added
                        
                    # C. Burstiness
                    # Gaps > 10s between keystrokes (typing events)
                    # Note: event timestamp is when the flush happened or when the typing started?
                    # The frontend flushes every 1.2s or on specific triggers.
                    # This metric might be sensitive to the flush interval.
                    # Defining burstiness here as per spec: gaps > 10s between captured events.
                    for j in range(1, len(typing_events)):
                        gap = (typing_events[j].created_at - typing_events[j-1].created_at).total_seconds()
                        if gap > 10:
                            burstiness += 1
                            
                    # D. WPM
                    # (Final Word Count) / (Active Writing Time)
                    # Active Writing Time = Time from first typing to last typing
                    last_typing = typing_events[-1]
                    active_writing_seconds = (last_typing.created_at - first_typing.created_at).total_seconds()
                    
                    if active_writing_seconds > 0:
                        active_time = active_writing_seconds / 60.0
                        wpm = final_word_count / active_time
                    
                    # Fetch actual word count from answer_data if possible?
                    # We only have interactions here. The View has access to attempts. 
                    # We can optimistically use the text_length/5 proxy or try to join with attempt_slots answer_data logic.
                    # For accuracy, let's try to get actual word count if the loop above is just proxy.
                    # However, strictly for the interaction export, using the metadata is safer than specific join unless we fetch attempts slots too.
                    # Let's stick to metadata proxy or improve if final_word_count is 0 but we have events.
                    
                writer.writerow([
                    attempt.student_identifier,
                    slot_label,
                    f"{ipl:.2f}",
                    f"{revision_ratio:.4f}",
                    burstiness,
                    f"{wpm:.2f}",
                    f"{active_time:.2f}",
                    int(final_word_count)
                ])

            return response
        
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
            name_to_id = {} # canonical_name -> id
            
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
                    
                    # Store ID for this name
                    name_to_id[c_name] = c_id

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
                    'id': name_to_id.get(c_name, c_name),
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
                        'id': name_to_id.get(c_name, c_name),
                        'name': c_name,
                        'distribution': dist
                    })
                formatted_grouped.append({
                    'group': group,
                    'data': {'criteria': g_criteria}
                })
            
            data['grouped_data'] = formatted_grouped

            # Calculate Cronbach's Alpha
            slot_cronbach_alpha = None
            try:
                # Reuse criteria loaded earlier? Not really available as 'criteria' variable is inside loop above?
                # Actually, wait. 'criteria' IS NOT available here scope-wise if it was defined inside the 'if' block.
                # But looking at line 1005 `rubric_c_names = [c['name'] for c in criteria]` suggests `criteria` is available list of dicts.
                # However, for calculation we need criterion IDs. The `criteria` variable in my previous snippets was `QuizRatingCriterion` objects.
                # Let's re-fetch or assume availability.
                # The Loop at line 1005 implies `criteria` is a list of dicts? No, `[c['name'] for c in criteria]`.
                # If `criteria` is objects, `c.name` would be used.
                # Let's check where `criteria` was defined. It seems I didn't see the definition in the previous view.
                # Warning: `criteria` might not be defined or might be a list of serialized dicts.
                
                # To be safe, let's re-fetch clean objects for calculation.
                alpha_criteria = QuizRatingCriterion.objects.filter(quiz=quiz).order_by('order')
                if alpha_criteria:
                    slot_attempt_ratings = {}
                    for attempt_slot in attempt_slots:
                        a_id = attempt_slot.attempt_id
                        if attempt_slot.answer_data and 'ratings' in attempt_slot.answer_data:
                            slot_attempt_ratings[a_id] = attempt_slot.answer_data['ratings']
                    
                    # Build matrix
                    existing_c_ids = set()
                    for r_map in slot_attempt_ratings.values():
                        existing_c_ids.update(r_map.keys())
                    
                    active_criteria = [c for c in alpha_criteria if c.criterion_id in existing_c_ids]
                    item_keys = [c.criterion_id for c in active_criteria]
                    K = len(item_keys)
                    
                    if K > 1:
                        scores_matrix = []
                        for ratings in slot_attempt_ratings.values():
                            if all(k in ratings for k in item_keys):
                                row = [float(ratings[k]) for k in item_keys]
                                scores_matrix.append(row)
                        
                        N = len(scores_matrix)
                        if N > 1:
                            item_variances = []
                            for col_idx in range(K):
                                col_values = [row[col_idx] for row in scores_matrix]
                                mean = sum(col_values) / N
                                var = sum((x - mean) ** 2 for x in col_values) / (N - 1)
                                item_variances.append(var)
                            
                            total_scores = [sum(row) for row in scores_matrix]
                            mean_total = sum(total_scores) / N
                            var_total = sum((x - mean_total) ** 2 for x in total_scores) / (N - 1)
                            
                            if var_total > 0:
                                slot_cronbach_alpha = (K / (K - 1)) * (1 - (sum(item_variances) / var_total))

            except Exception as e:
                print(f"Error calculating slot alpha: {e}")
            
            data['cronbach_alpha'] = slot_cronbach_alpha

            # Inter-Criterion Correlation for this Slot
            slot_inter_criterion_correlation = None
            try:
                 # Reuse logic from alpha calculation if available, or fetch fresh
                 # We need `scores_matrix` and `item_keys` (criterion IDs)
                 
                 # Ensure we have the data
                 alpha_criteria_corr = QuizRatingCriterion.objects.filter(quiz=quiz).order_by('order')
                 if alpha_criteria_corr:
                    slot_attempt_ratings_corr = {}
                    for attempt_slot in attempt_slots:
                        a_id = attempt_slot.attempt_id
                        if attempt_slot.answer_data and 'ratings' in attempt_slot.answer_data:
                            slot_attempt_ratings_corr[a_id] = attempt_slot.answer_data['ratings']
                    
                    existing_c_ids_corr = set()
                    for r_map in slot_attempt_ratings_corr.values():
                        existing_c_ids_corr.update(r_map.keys())
                    
                    active_criteria_corr = [c for c in alpha_criteria_corr if c.criterion_id in existing_c_ids_corr]
                    item_keys_corr = [c.criterion_id for c in active_criteria_corr]
                    item_names_corr = [c.name for c in active_criteria_corr]
                    
                    K_corr = len(item_keys_corr)
                    
                    if K_corr > 1:
                        # Build columns for correlation
                        # cid -> list of values
                        c_columns = {cid: [] for cid in item_keys_corr}
                        
                        # Populate columns (dense)
                        # We should likely use only complete cases for pairwise, or handle missing
                        # Let's iterate attempts
                        for ratings in slot_attempt_ratings_corr.values():
                            # We don't strictly require 'all' keys for pairwise correlation, just presence
                            for cid in item_keys_corr:
                                c_columns[cid].append(ratings.get(cid)) # Might be None
                        
                        corr_matrix = []
                        for i in range(K_corr):
                            row_res = []
                            cid_i = item_keys_corr[i]
                            vals_i = c_columns[cid_i]
                            
                            for j in range(K_corr):
                                cid_j = item_keys_corr[j]
                                vals_j = c_columns[cid_j]
                                
                                
                                xs = []
                                ys = []
                                for idx in range(len(vals_i)):
                                    if vals_i[idx] is not None and vals_j[idx] is not None:
                                        try:
                                            xs.append(float(vals_i[idx]))
                                            ys.append(float(vals_j[idx]))
                                        except Exception:
                                            pass
                                
                                if len(xs) >= 2:
                                    try:
                                        r_res = sp_stats.spearmanr(xs, ys)
                                        r_val = r_res.statistic if hasattr(r_res, 'statistic') else r_res.correlation
                                        p_val = r_res.pvalue
                                        
                                        import math
                                        # Handle NaN for R
                                        if r_val is None or (isinstance(r_val, float) and math.isnan(r_val)):
                                            safe_r = None
                                        else:
                                            # Convert numpy float to python float
                                            safe_r = round(float(r_val), 4)
                                            
                                        # Handle NaN for P
                                        if p_val is None or (isinstance(p_val, float) and math.isnan(p_val)):
                                            safe_p = None
                                        else:
                                            safe_p = round(float(p_val), 5)

                                        if safe_r is None:
                                                row_res.append(None)
                                        else:
                                            row_res.append({
                                                'r': safe_r,
                                                'p': safe_p,
                                                'n': len(xs)
                                            })
                                    except Exception:
                                        row_res.append(None)
                                else:
                                    row_res.append(None)
                            corr_matrix.append(row_res)
                        
                        slot_inter_criterion_correlation = {
                            'criteria': item_names_corr,
                            'matrix': corr_matrix
                        }

            except Exception as e:
                print(f"Error calculating slot correlation: {e}")

            data['inter_criterion_correlation'] = slot_inter_criterion_correlation

        return Response({
            'id': slot.id,
            'label': slot.label,
            'response_type': slot.response_type,
            'data': data,
            'problem_distribution': problem_distribution
        })

class QuizInterRaterAgreementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        instructor = ensure_instructor(request.user)
        quiz = get_object_or_404(Quiz, id=quiz_id)
        if quiz.owner != instructor and not quiz.allowed_instructors.filter(id=instructor.id).exists():
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        # 1. Get Criteria Mapping
        # Map Quiz Criterion ID -> Instructor Criterion Code (RubricCriterion.criterion_id)
        quiz_criteria = QuizRatingCriterion.objects.filter(quiz=quiz).order_by('order')
        criterion_map = {} # quiz_crit_id -> instructor_crit_code
        criterion_names = {} # quiz_crit_id -> name
        for qc in quiz_criteria:
            if qc.instructor_criterion_code:
                criterion_map[qc.criterion_id] = qc.instructor_criterion_code
                criterion_names[qc.criterion_id] = qc.name
        
        if not criterion_map:
            return Response({
                'detail': 'No criteria mapping found. Please configure the rubric mapping in settings.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 2. Get Scale Mapping
        # Map Quiz Value -> Mapped Value (Instructor Scale)
        quiz_scale = QuizRatingScaleOption.objects.filter(quiz=quiz)
        scale_map = {} # quiz_value -> mapped_value
        for qs in quiz_scale:
            if qs.mapped_value is not None:
                scale_map[qs.value] = qs.mapped_value
        
        if not scale_map:
            return Response({
                'detail': 'No scale mapping found. Please configure the rubric mapping in settings.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        possible_ratings = sorted(list(scale_map.values()))

        # 3. Identify Problems
        # Get problems assigned in completed attempts
        attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False)
        quiz_problems = Problem.objects.filter(
            slot_links__quiz_slot__quiz=quiz,
            slot_links__quiz_slot__response_type='rating'
        ).distinct()
        
        # We need efficient lookup for student ratings per problem
        # ProblemID -> { CriterionID -> [List of Mapped Values] }
        student_ratings_data = {} 
        
        # Map ProblemID -> Label (Order in Bank)
        problem_label_map = {p.id: f"Problem {p.order_in_bank}" for p in quiz_problems}
        problem_group_map = {p.id: p.group or '' for p in quiz_problems}

        # Fetch all relevant attempt slots
        # We need the attempt ID to link to the total score
        attempt_slots = QuizAttemptSlot.objects.filter(
            attempt__in=attempts,
            slot__response_type='rating',
            answer_data__ratings__isnull=False
        ).values('id', 'assigned_problem_id', 'answer_data', 'attempt_id')
        
        # Calculate Total Quiz Score per Attempt
        # Sum up points from all graded slots in the attempt
        attempt_scores = QuizAttemptSlot.objects.filter(
            attempt__in=attempts,
            grade__isnull=False
        ).values('attempt_id').annotate(
            total_score=Coalesce(Sum('grade__items__selected_level__points'), 0.0)
        )
        
        attempt_score_map = {item['attempt_id']: item['total_score'] for item in attempt_scores}

        raw_score_data = [] # List of {pid, ratings, score}

        for entry in attempt_slots:
            pid = entry['assigned_problem_id']
            ratings = entry['answer_data'].get('ratings', {})
            # Get score from the attempt map, default to 0 if not found (though it should be if graded)
            # Check if attempting student even has a score (might be ungraded)
            attempt_id = entry['attempt_id']
            score = attempt_score_map.get(attempt_id)
            
            # Store raw data for score correlation analysis
            raw_score_data.append({
                'pid': pid,
                'ratings': ratings,
                'score': score,
                'attempt_id': attempt_id
            })
            
            if pid not in student_ratings_data:
                student_ratings_data[pid] = {}
            
            for q_cid, val in ratings.items():
                if q_cid in criterion_map and val in scale_map:
                    # Map to instructor codes/values
                    i_code = criterion_map[q_cid]
                    mapped_val = scale_map[val]
                    
                    if i_code not in student_ratings_data[pid]:
                        student_ratings_data[pid][i_code] = []
                    student_ratings_data[pid][i_code].append({
                        'raw': val,
                        'mapped': mapped_val
                    })

        # 4. Fetch Instructor Ratings
        # ProblemID -> { InstructorCriterionCode -> [List of Values] }
        instructor_ratings_data = {}
        
        # We only care about problems that students have rated
        relevant_problem_ids = list(student_ratings_data.keys())
        
        instructor_ratings = InstructorProblemRating.objects.filter(
            problem_id__in=relevant_problem_ids
        ).prefetch_related('entries__criterion')

        # We need to manually aggregate entries because filtering on Criterion ID from Rubric is tricky 
        # (RubricCriterion ID vs Code). The Entry links to RubricCriterion(db model).
        # RubricCriterion has .criterion_id field which matches instructor_criterion_code.
        
        weight_map = {} # instructor_code -> weight

        for rating in instructor_ratings:
            pid = rating.problem_id
            if pid not in instructor_ratings_data:
                instructor_ratings_data[pid] = {}
            
            for entry in rating.entries.all():
                code = entry.criterion.criterion_id
                val = entry.scale_option.value
                
                if code not in weight_map:
                     weight_map[code] = entry.criterion.weight

                if code not in instructor_ratings_data[pid]:
                    instructor_ratings_data[pid][code] = []
                instructor_ratings_data[pid][code].append({
                    'value': val
                })

        # 5. Compute Agreement per Criterion
        agreement_data = []
        detailed_comparisons = {}
        all_student_ratings_list = []
        all_instructor_ratings_list = []
        total_common_problems = 0

        # Iterate over mapped quiz criteria to preserve order
        for qc in quiz_criteria:
            q_cid = qc.criterion_id
            i_code = qc.instructor_criterion_code
            if not i_code:
                continue
                

            
            common_problems_for_criterion_count = 0
            s_list_for_criterion = []
            i_list_for_criterion = []
            
            for pid in relevant_problem_ids:
                s_vals_objs = student_ratings_data.get(pid, {}).get(i_code, [])
                i_vals_objs = instructor_ratings_data.get(pid, {}).get(i_code, [])
                
                if s_vals_objs and i_vals_objs:
                    # Extract values for kappa calculation
                    s_mapped_vals = [x['mapped'] for x in s_vals_objs]
                    i_vals = [x['value'] for x in i_vals_objs]

                    # Student Aggregation: Average Raw -> Nearest Raw -> Map to Instructor Scale
                    # 1. Get average of raw values
                    s_raw_vals = [x['raw'] for x in s_vals_objs]
                    s_mean_raw = mean(s_raw_vals) if s_raw_vals else 0
                    
                    # We need the set of valid raw values for this criterion to find the nearest one.
                    # The 'scale_map' has {raw: mapped}. The keys are valid raw values.
                    valid_raw_values = list(scale_map.keys())
                    
                    nearest_raw = calculate_average_nearest(s_raw_vals, valid_raw_values)
                    s_median = scale_map.get(nearest_raw)

                    # Instructor Aggregation: Average -> Nearest Valid Value (already on target scale)
                    i_mean_val = mean(i_vals) if i_vals else 0
                    i_median = calculate_average_nearest(i_vals, possible_ratings)

                    if s_median is not None and i_median is not None:
                        s_list_for_criterion.append(s_median)
                        i_list_for_criterion.append(i_median)
                        common_problems_for_criterion_count += 1
                    
                    if pid not in detailed_comparisons:
                        detailed_comparisons[pid] = {
                            'problem_id': pid,
                            'problem_label': problem_label_map.get(pid, f"Problem {pid}"),
                            'problem_group': problem_group_map.get(pid, ''),
                            'ratings': {}
                        }
                    
                    detailed_comparisons[pid]['ratings'][q_cid] = {
                        'instructor': i_median,
                        'instructor_mean': i_mean_val,
                        'student': s_median,
                        'student_mean': s_mean_raw,
                        'instructor_details': i_vals_objs,
                        'student_details': s_vals_objs
                    }

            if common_problems_for_criterion_count > 0:
                kappa = quadratic_weighted_kappa(
                    i_list_for_criterion, 
                    s_list_for_criterion, 
                    possible_ratings=possible_ratings,
                    context=f"Criterion {qc.criterion_id}"
                )
                
                agreement_data.append({
                    'criterion_id': q_cid,
                    'criterion_name': qc.name,
                    'instructor_code': i_code,
                    'common_problems': common_problems_for_criterion_count,
                    'kappa_score': round(kappa, 4)
                })

                # Accumulate for overall kappa
                all_student_ratings_list.extend(s_list_for_criterion)
                all_instructor_ratings_list.extend(i_list_for_criterion)
                total_common_problems += common_problems_for_criterion_count

        # Calculate Overall Agreement
        if all_student_ratings_list:
            overall_kappa = quadratic_weighted_kappa(all_instructor_ratings_list, all_student_ratings_list, possible_ratings=possible_ratings)
            agreement_data.append({
                'criterion_id': 'all',
                'criterion_name': 'Overall (All Criteria)',
                'instructor_code': '-',
                'common_problems': total_common_problems,
                'kappa_score': round(overall_kappa, 4)
            })

        # 6. Student vs Instructor Comparison (Paired T-Test)
        comparison_data = []

        # Determine Student Scale Lookup
        scale_lookup = {qs.value: qs.mapped_value for qs in quiz_scale}

        from scipy import stats
        
        # Build Groups
        # Group relevant_problem_ids by their group
        groups = {}
        for pid in relevant_problem_ids:
             g = problem_group_map.get(pid, '') or '-'
             if g not in groups:
                 groups[g] = []
             groups[g].append(pid)
        
        # Add Overall group
        groups['Overall'] = relevant_problem_ids
        
        # Pre-calculate weight_map was done above

        # Iterate Groups
        for group_name in sorted(groups.keys()):
            group_pids = groups[group_name]
            
            # --- Per Criterion Comparison ---
            for qc in quiz_criteria:
                q_cid = qc.criterion_id
                i_code = qc.instructor_criterion_code
                if not i_code:
                    continue

                # Collect pairs for this criterion (only for problems in this group)
                student_scores_mapped = []
                instructor_scores = []
                common_count = 0

                for pid in group_pids:
                    s_vals_objs = student_ratings_data.get(pid, {}).get(i_code, [])
                    i_vals_objs = instructor_ratings_data.get(pid, {}).get(i_code, [])

                    if s_vals_objs and i_vals_objs:
                        # Student Score: Map individual ratings then average
                        s_raw_vals = [x['raw'] for x in s_vals_objs]
                        
                        # Map using explicit lookup
                        s_mapped_list = []
                        for v in s_raw_vals:
                            single_mapped = scale_lookup.get(v)
                            if single_mapped is None:
                                single_mapped = v
                            s_mapped_list.append(single_mapped)

                        s_mapped = mean(s_mapped_list) if s_mapped_list else 0

                        # Instructor Score
                        i_vals = [x['value'] for x in i_vals_objs]
                        i_mean = mean(i_vals) if i_vals else 0

                        student_scores_mapped.append(s_mapped)
                        instructor_scores.append(i_mean)
                        common_count += 1
                        
                        # Update detailed comparisons (Per Problem - side effect OK inside loop)
                        if pid in detailed_comparisons and q_cid in detailed_comparisons[pid]['ratings']:
                            detailed_comparisons[pid]['ratings'][q_cid]['student_mean_norm'] = s_mapped
                            detailed_comparisons[pid]['ratings'][q_cid]['student_details'] = [{'raw': r, 'mapped': m} for r, m in zip(s_raw_vals, s_mapped_list)]
                
                # Perform Paired T-Test for Group
                t_stat = None
                p_val = None
                mean_diff = None
                
                if common_count > 1:
                    if all(s == i for s, i in zip(student_scores_mapped, instructor_scores)):
                         t_stat = 0.0
                         p_val = 1.0
                    else:
                        try:
                            result = stats.ttest_rel(student_scores_mapped, instructor_scores)
                            t_stat = result.statistic
                            p_val = result.pvalue
                        except Exception as e:
                            print(f"Error calculating t-test for {qc.name}: {e}")
                
                avg_s_mapped = mean(student_scores_mapped) if student_scores_mapped else 0
                avg_i = mean(instructor_scores) if instructor_scores else 0
                mean_diff = avg_s_mapped - avg_i

                comparison_data.append({
                    'criterion_id': q_cid,
                    'criterion_name': qc.name,
                    'group': group_name,
                    'common_problems': common_count,
                    't_statistic': round(t_stat, 4) if t_stat is not None else None,
                    'p_value': round(p_val, 5) if p_val is not None else None,
                    'instructor_mean': round(avg_i, 4),
                    'student_mean_norm': round(avg_s_mapped, 4),
                    'mean_difference': round(mean_diff, 4),
                    'df': common_count - 1 if common_count > 0 else 0
                })

            # --- Weighted Scores Comparison for Group ---
            weighted_student_scores = []
            weighted_instructor_scores = []
            weighted_common_count = 0
            
            for pid in group_pids:
                # Calculate weighted score for problem
                # Need s_mapped for each criterion.
                # Since we already computed s_mapped in loop above but didn't store per-pid easily accessible (unless we access detailed_comparisons).
                # But detailed_comparisons might not have it if q_cid not in detailed_comparisons[pid]['ratings']?
                # Actually detailed_comparisons is reliably populated.
                
                # Let's recompute or use detailed_comparisons
                # Recomputing is safer/cleaner than digging into detailed_comparisons structure which has presentation strings?
                # Detailed comparisons has numeric values stored.
                
                # Let's recompute to be safe and independent.
                
                s_sum = 0
                i_sum = 0
                w_sum = 0
                has_valid_data = False
                
                # We need to iterate all criteria again or look up what ratings this problem has.
                # Using student_ratings_data keys?
                # Better: Iterate all instructor criteria available for this pid.
                
                # We can iterate quiz_criteria again
                for qc in quiz_criteria:
                    i_code = qc.instructor_criterion_code
                    if not i_code or i_code not in weight_map:
                        continue
                        
                    weight = weight_map[i_code]
                    
                    s_vals_objs = student_ratings_data.get(pid, {}).get(i_code, [])
                    i_vals_objs = instructor_ratings_data.get(pid, {}).get(i_code, [])

                    if s_vals_objs and i_vals_objs:
                        # Student
                        s_raw_vals = [x['raw'] for x in s_vals_objs]
                        s_mapped_list = [scale_lookup.get(v, v) for v in s_raw_vals]
                        s_mapped = mean(s_mapped_list) if s_mapped_list else 0
                        
                        # Instructor
                        i_vals = [x['value'] for x in i_vals_objs]
                        i_mean = mean(i_vals) if i_vals else 0
                        
                        s_sum += s_mapped * weight
                        i_sum += i_mean * weight
                        w_sum += weight
                        has_valid_data = True
                
                if has_valid_data and w_sum > 0:
                    w_s_avg = s_sum / w_sum
                    w_i_avg = i_sum / w_sum
                    
                    weighted_student_scores.append(w_s_avg)
                    weighted_instructor_scores.append(w_i_avg)
                    weighted_common_count += 1
                    
                    if pid in detailed_comparisons:
                         detailed_comparisons[pid]['weighted_instructor'] = w_i_avg
                         detailed_comparisons[pid]['weighted_student'] = w_s_avg
                         detailed_comparisons[pid]['weighted_diff'] = w_s_avg - w_i_avg

            # T-Test Weighted
            wt_stat = None
            wp_val = None
            w_mean_diff = None
            
            if weighted_common_count > 1:
                if all(s == i for s, i in zip(weighted_student_scores, weighted_instructor_scores)):
                     wt_stat = 0.0
                     wp_val = 1.0
                else:
                    try:
                        wresult = stats.ttest_rel(weighted_student_scores, weighted_instructor_scores)
                        wt_stat = wresult.statistic
                        wp_val = wresult.pvalue
                    except Exception as e:
                        print(f"Error calculating weighted t-test: {e}")
            
            w_avg_s = mean(weighted_student_scores) if weighted_student_scores else 0
            w_avg_i = mean(weighted_instructor_scores) if weighted_instructor_scores else 0
            w_mean_diff = w_avg_s - w_avg_i
            
            comparison_data.append({
                'criterion_id': 'weighted',
                'criterion_name': 'Weighted Score',
                'group': group_name,
                'common_problems': weighted_common_count,
                't_statistic': round(wt_stat, 4) if wt_stat is not None else None,
                'p_value': round(wp_val, 5) if wp_val is not None else None,
                'instructor_mean': round(w_avg_i, 4),
                'student_mean_norm': round(w_avg_s, 4),
                'mean_difference': round(w_mean_diff, 4),
                'df': weighted_common_count - 1 if weighted_common_count > 0 else 0
            })
            
        details_list = sorted(list(detailed_comparisons.values()), key=lambda x: x['problem_id'])
        
        criteria_columns = []
        for qc in quiz_criteria:
             if qc.instructor_criterion_code:
                 criteria_columns.append({
                     'id': qc.criterion_id,
                     'name': qc.name,
                     'code': qc.instructor_criterion_code,
                     'order': qc.order
                 })

        # 7. Score vs Rating Correlation Analysis
        score_correlation = []
        
        # We need to collect pairs of (Rating, Score) for each criterion
        # And (WeightedRating, Score)
        
        # Prepare storage
        criterion_points = {} # name -> list of {x: score, y: rating}
        weighted_points = [] # list of {x: score, y: rating}
        time_points = [] # list of {x: score, y: duration_minutes}
        word_count_points = [] # list of {x: score, y: word_count}
        
        # Time vs Rating Storage
        time_vs_rating_points = {} # name -> list of {x: duration, y: rating}
        weighted_time_vs_rating_points = [] # list of {x: duration, y: weighted_rating}
        
        for qc in quiz_criteria:
            if qc.instructor_criterion_code:
                criterion_points[qc.name] = []
                time_vs_rating_points[qc.name] = []
        
        # Pre-calc durations for Time vs Rating
        # We perform valid collection for ALL graded attempts (present in attempt_score_map)
        attempts_data = attempts.values('id', 'started_at', 'completed_at')
        attempt_durations = {} # aid -> duration
        
        for att in attempts_data:
            if att['started_at'] and att['completed_at']:
                d = (att['completed_at'] - att['started_at']).total_seconds() / 60.0
                if d > 0:
                    attempt_durations[att['id']] = d

        for record in raw_score_data:
            pid = record['pid']
            ratings = record['ratings']
            score = record['score']
            aid = record.get('attempt_id')
            duration = attempt_durations.get(aid)
            
            # Weighted calc for this record
            w_sum_r = 0
            w_sum_w = 0
            
            for q_cid, val in ratings.items():
                # Use raw value 'val' directly as requested
                
                # Get criterion name to plot per-criterion
                c_name = criterion_names.get(q_cid)
                if c_name:
                    if score is not None and c_name in criterion_points:
                        criterion_points[c_name].append({'x': score, 'y': val})
                    if duration is not None and c_name in time_vs_rating_points:
                        time_vs_rating_points[c_name].append({'x': duration, 'y': val})
                
                # Weighted Calculation
                # We need to link this rating to a weight.
                # Use criterion_map to find the instructor code, then lookup weight.
                if q_cid in criterion_map:
                        i_code = criterion_map[q_cid]
                        if i_code in weight_map:
                            weight = weight_map[i_code]
                            w_sum_r += val * weight
                            w_sum_w += weight
            
            if w_sum_w > 0:
                weighted_avg = w_sum_r / w_sum_w
                if score is not None:
                    weighted_points.append({'x': score, 'y': weighted_avg})
                if duration is not None:
                    weighted_time_vs_rating_points.append({'x': duration, 'y': weighted_avg})

        # --- Time & Word Count Collection --- (Simplified now that attempts_data is fetched)
        # Pre-fetch text data if needed
        has_text_slots = quiz.slots.filter(response_type='open_text').exists()
        attempt_word_counts = {}
        
        if has_text_slots:
             text_aslots = QuizAttemptSlot.objects.filter(
                 attempt__in=attempts,
                 slot__response_type='open_text'
             ).values('attempt_id', 'answer_data')
             
             for tas in text_aslots:
                 aid = tas['attempt_id']
                 if tas['answer_data'] and 'text' in tas['answer_data']:
                     txt = tas['answer_data']['text'] or ""
                     count = len(txt.split())
                     attempt_word_counts[aid] = attempt_word_counts.get(aid, 0) + count

        for att in attempts_data:
            aid = att['id']
            score = attempt_score_map.get(aid)
            
            if score is not None:
                # Time
                if aid in attempt_durations:
                    time_points.append({'x': score, 'y': attempt_durations[aid]})
                
                # Word Count
                if has_text_slots:
                    wc = attempt_word_counts.get(aid, 0)
                    word_count_points.append({'x': score, 'y': wc})

        # Calculate Correlations
        def calculate_correlations(points, label):
             if len(points) < 2:
                 return {
                     'name': label,
                     'count': len(points),
                     'pearson_r': None,
                     'pearson_p': None,
                     'spearman_rho': None,
                     'spearman_p': None,
                     'points': points
                 }
            
             xs = [p['x'] for p in points]
             ys = [p['y'] for p in points]
             
             try:
                 p_res = stats.pearsonr(xs, ys)
                 s_res = stats.spearmanr(xs, ys)
                 
                 return {
                     'name': label,
                     'count': len(points),
                     'pearson_r': round(p_res.statistic, 4),
                     'pearson_p': round(p_res.pvalue, 5),
                     'spearman_rho': round(s_res.statistic, 4),
                     'spearman_p': round(s_res.pvalue, 5),
                     'points': points
                 }
             except Exception as e:
                 print(f"Error calculating correlation for {label}: {e}")
                 return {
                     'name': label,
                     'count': len(points),
                     'pearson_r': None,
                     'pearson_p': None,
                     'spearman_rho': None,
                     'spearman_p': None,
                     'points': points
                 }

        for c_name, points in criterion_points.items():
            score_correlation.append(calculate_correlations(points, c_name))
            
        score_correlation.append(calculate_correlations(weighted_points, "Weighted Rating"))

        # Calculate Time & Word Count Correlations
        time_correlation = []
        if time_points:
            time_correlation.append(calculate_correlations(time_points, "Quiz Duration"))

        # Calculate Time & Word Count Correlations
        time_correlation = []
        if time_points:
            time_correlation.append(calculate_correlations(time_points, "Quiz Duration"))

        word_count_correlation = []
        if word_count_points:
            word_count_correlation.append(calculate_correlations(word_count_points, "Word Count"))

        # Time vs Word Count Correlation
        word_count_vs_time_points = []
        for att in attempts_data:
            aid = att['id']
            duration = attempt_durations.get(aid) # Use pre-calc
            wc = None
            
            # Word Count
            if has_text_slots:
                wc = attempt_word_counts.get(aid, 0)
            
            if duration is not None and wc is not None:
                word_count_vs_time_points.append({'x': duration, 'y': wc})

        word_count_vs_time_correlation = []
        if word_count_vs_time_points:
            word_count_vs_time_correlation.append(calculate_correlations(word_count_vs_time_points, "Time vs Word Count"))

        # Time vs Rating Correlation Calculation
        time_vs_rating_correlation = []
        
        # Per Criterion
        for c_name, points in time_vs_rating_points.items():
            time_vs_rating_correlation.append(calculate_correlations(points, c_name))
        
        # Weighted
        time_vs_rating_correlation.append(calculate_correlations(weighted_time_vs_rating_points, "Weighted Rating"))

        # Sort
        time_vs_rating_correlation.sort(key=lambda x: (
            next((c['order'] for c in criteria_columns if c['name'] == x['name']), 999), 
            x['name']
        ))

        return Response(self.sanitize_data({
            'agreement': agreement_data,
            'comparison': comparison_data,
            'details': details_list,
            'criteria_columns': criteria_columns,
            'score_correlation': score_correlation,
            'time_correlation': time_correlation,
            'word_count_correlation': word_count_correlation,
            'word_count_vs_time_correlation': word_count_vs_time_correlation,
            'time_vs_rating_correlation': time_vs_rating_correlation
        }))

    def sanitize_data(self, data):
        """Recursively replace NaN/Inf with None for JSON compliance"""
        import numpy as np
        if isinstance(data, dict):
            return {k: self.sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_data(v) for v in data]
        elif isinstance(data, float):
            if np.isnan(data) or np.isinf(data):
                return None
        return data

