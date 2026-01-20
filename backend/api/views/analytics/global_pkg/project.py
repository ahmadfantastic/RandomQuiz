
import statistics
from scipy import stats
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.models import ensure_instructor, Instructor
from quizzes.models import Quiz, QuizProjectScore

from api.analytics_constants import PROJECT_SCORE_THRESHOLD

class GlobalProjectAnalysisView(APIView):
    permission_classes = [IsAuthenticated]
    

    def get(self, request):
        instructor = ensure_instructor(request.user)
        quizzes = Quiz.objects.filter(owner=instructor)
        
        # Output structures
        quiz_correlations = []
        
        # Aggregated Quadrant Counts
        # We track 4 configurations:
        # 1. Med / Med
        # 2. Med / 50% Max (if available)
        # 3. Thresh Max / Med
        # 4. Thresh Max / 50% Max (if available)
        
        aggregated_quadrants = {
            'med_med': {'masters': 0, 'implementers': 0, 'conceptualizers': 0, 'strugglers': 0},
            'med_half': {'masters': 0, 'implementers': 0, 'conceptualizers': 0, 'strugglers': 0, 'valid_count': 0}, # valid_count tracks quizzes where max possible was known
            'thresh_med': {'masters': 0, 'implementers': 0, 'conceptualizers': 0, 'strugglers': 0},
            'thresh_half': {'masters': 0, 'implementers': 0, 'conceptualizers': 0, 'strugglers': 0, 'valid_count': 0},
        }

        for quiz in quizzes:
            scores = list(QuizProjectScore.objects.filter(quiz=quiz))
            count = len(scores)
            if count < 2: 
                continue
                
            x_values = [s.quiz_score for s in scores] # Quiz Score
            y_values = [s.project_score for s in scores] # Project Score
            
            # 1. Correlation
            pearson_r, pearson_p, spearman_rho, spearman_p = None, None, None, None
            try:
                if len(set(x_values)) > 1 and len(set(y_values)) > 1:
                    pr, pp = stats.pearsonr(x_values, y_values)
                    pearson_r, pearson_p = round(pr, 4), round(pp, 4)
                    
                    sr, sp = stats.spearmanr(x_values, y_values)
                    spearman_rho, spearman_p = round(sr, 4), round(sp, 4)
            except Exception:
                pass
            
            # Sanitize NaN for JSON
            import math
            def sanitize(val):
                if val is not None and (math.isnan(val) or math.isinf(val)):
                    return None
                return val

            quiz_correlations.append({
                'quiz_id': quiz.id,
                'quiz_title': quiz.title,
                'count': count,
                'pearson_r': sanitize(pearson_r),
                'pearson_p': sanitize(pearson_p),
                'spearman_rho': sanitize(spearman_rho),
                'spearman_p': sanitize(spearman_p)
            })
            
            # 2. Quadrants (Local Thresholds)
            
            # Calc Thresholds
            p_median = statistics.median(y_values)
            p_max = max(y_values)
            p_thresh = p_max * PROJECT_SCORE_THRESHOLD
            
            q_median = statistics.median(x_values)
            
            # Quiz Max Possible
            q_max_possible = 0
            try:
                grading_rubric = getattr(quiz, 'grading_rubric', None)
                if grading_rubric:
                    from django.db.models import Max
                    for item in grading_rubric.items.all():
                        max_p = item.levels.aggregate(Max('points'))['points__max']
                        if max_p: q_max_possible += max_p
            except Exception:
                pass
            
            if q_max_possible == 0:
                 rubric = quiz.get_rubric()
                 if rubric:
                     scale = rubric.get('scale', [])
                     criteria = rubric.get('criteria', [])
                     if scale and criteria:
                         max_val = max([s['value'] for s in scale])
                         q_max_possible = max_val * len(criteria)

            q_half = q_max_possible * 0.5 if q_max_possible > 0 else None

            # Helper to classify
            def classify(p_score, q_score, p_t, q_t, strict_q=False):
                is_high_p = p_score >= p_t
                is_high_q = q_score > q_t if strict_q else q_score >= q_t
                if is_high_p and is_high_q: return 'masters'
                if is_high_p and not is_high_q: return 'implementers'
                if not is_high_p and is_high_q: return 'conceptualizers'
                return 'strugglers'

            for s in scores:
                p = s.project_score
                q = s.quiz_score
                
                # Update Med/Med
                cat = classify(p, q, p_median, q_median)
                aggregated_quadrants['med_med'][cat] += 1
                
                # Update Thresh/Med
                cat = classify(p, q, p_thresh, q_median)
                aggregated_quadrants['thresh_med'][cat] += 1
                
                # Update Med/Half
                if q_half is not None:
                    cat = classify(p, q, p_median, q_half, strict_q=True)
                    aggregated_quadrants['med_half'][cat] += 1
                
                # Update Thresh/Half
                if q_half is not None:
                    cat = classify(p, q, p_thresh, q_half, strict_q=True)
                    aggregated_quadrants['thresh_half'][cat] += 1
            
            if q_half is not None:
                aggregated_quadrants['med_half']['valid_count'] += count
                aggregated_quadrants['thresh_half']['valid_count'] += count

        return Response({
            'quiz_correlations': quiz_correlations,
            'aggregated_quadrants': aggregated_quadrants,
            'project_threshold_ratio': PROJECT_SCORE_THRESHOLD
        })
