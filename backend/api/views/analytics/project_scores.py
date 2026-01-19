import csv

from scipy import stats
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser

from quizzes.models import Quiz, QuizProjectScore
from quizzes.serializers import QuizProjectScoreSerializer

class QuizProjectScoreListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QuizProjectScoreSerializer
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        quiz_id = self.kwargs['quiz_id']
        return QuizProjectScore.objects.filter(quiz_id=quiz_id)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Calculate stats
        scores = list(queryset)
        points = []
        x_values = []
        y_values = []
        
        for s in scores:
            x = s.quiz_score
            y = s.project_score
            label = s.team if s.team else (s.grade_level if s.grade_level else '')
            
            points.append({
                'x': x,
                'y': y,
                'student_id': label
            })
            x_values.append(x)
            y_values.append(y)
            
        count = len(points)
        pearson_r = None
        pearson_p = None
        spearman_rho = None
        spearman_p = None

        if count > 1:
            try:
                # Pearson
                if len(set(x_values)) > 1 and len(set(y_values)) > 1:
                    pr, pp = stats.pearsonr(x_values, y_values)
                    pearson_r = round(pr, 4)
                    pearson_p = round(pp, 4)
                
                # Spearman
                if len(set(x_values)) > 1 and len(set(y_values)) > 1:
                    sr, sp = stats.spearmanr(x_values, y_values)
                    spearman_rho = round(sr, 4)
                    spearman_p = round(sp, 4)
            except Exception:
                pass

        analysis_item = {
            'name': 'Project Score vs Quiz Score',
            'count': count,
            'pearson_r': pearson_r,
            'pearson_p': pearson_p,
            'spearman_rho': spearman_rho,
            'spearman_p': spearman_p,
            'points': points
        }
        
        # Team Variance Analysis
        team_data_map = {}
        for s in scores:
            if not s.team:
                continue
            
            if s.team not in team_data_map:
                team_data_map[s.team] = {
                    'team': s.team,
                    'project_scores_list': [],
                    'quiz_scores': [],
                    'members': []
                }
            # Add score
            team_data_map[s.team]['quiz_scores'].append(s.quiz_score)
            team_data_map[s.team]['project_scores_list'].append(s.project_score)
            if s.grade_level: # Using grade_level as member id proxy or just ignore
                team_data_map[s.team]['members'].append(s.grade_level)
        
        # Calculate per-team stats and format for response
        team_variance_list = []
        import statistics

        for team_name, data in team_data_map.items():
             p_scores = data['project_scores_list']
             q_scores = data['quiz_scores']
             
             p_mean = round(statistics.mean(p_scores), 2) if p_scores else 0
             p_var = round(statistics.variance(p_scores), 2) if len(p_scores) > 1 else 0
             
             q_mean = round(statistics.mean(q_scores), 2) if q_scores else 0
             q_var = round(statistics.variance(q_scores), 2) if len(q_scores) > 1 else 0
             
             team_variance_list.append({
                 'team': team_name,
                 'project_score': p_mean,
                 'project_scores_list': p_scores,
                 'project_mean': p_mean,
                 'project_variance': p_var,
                 'quiz_mean': q_mean,
                 'quiz_variance': q_var,
                 'quiz_scores': q_scores,
                 'members': data['members']
             })

        # Sort teams by project score (mean)
        team_variance = sorted(team_variance_list, key=lambda x: x['project_mean'])

        # Calculate Global Stats
        stats_data = {
            'project_mean': None,
            'project_variance': None,
            'quiz_mean': None,
            'quiz_variance': None
        }
        
        quadrants_config = {
            'project_median': 0,
            'project_max_95': 0,
            'quiz_median': 0,
            'quiz_max_50': 0,
            'quiz_max_possible': 0
        }

        if count > 0:
            stats_data['project_mean'] = round(statistics.mean(y_values), 2)
            stats_data['quiz_mean'] = round(statistics.mean(x_values), 2)
            
            # Quadrants Project Stats
            p_median = statistics.median(y_values)
            p_max = max(y_values)
            quadrants_config['project_median'] = round(p_median, 2)
            quadrants_config['project_max_95'] = round(p_max * 0.95, 2)

            # Quadrants Quiz Stats
            q_median = statistics.median(x_values)
            quadrants_config['quiz_median'] = round(q_median, 2)
            
            # Calculate Quiz Max Possible
            quiz = self.get_queryset().first().quiz if queryset.exists() else None
            if not quiz:
                 try:
                     quiz = Quiz.objects.get(id=self.kwargs['quiz_id'])
                 except Quiz.DoesNotExist:
                     pass

            if quiz:
                # Try GradingRubric first (granular points per item)
                try:
                    # We need to access the related grading_rubric. 
                    # Note: accessing OneToOne that doesn't exist raises exception.
                    grading_rubric = getattr(quiz, 'grading_rubric', None)
                    if grading_rubric:
                        from django.db.models import Max
                        # Sum of max points per item
                        total_possible = 0
                        for item in grading_rubric.items.all():
                            max_p = item.levels.aggregate(Max('points'))['points__max']
                            if max_p:
                                total_possible += max_p
                        
                        if total_possible > 0:
                            quadrants_config['quiz_max_possible'] = total_possible
                            quadrants_config['quiz_max_50'] = round(total_possible * 0.5, 2)
                except Exception:
                    pass

                # Fallback to legacy get_rubric if score is still 0
                if quadrants_config['quiz_max_possible'] == 0:
                    rubric = quiz.get_rubric()
                    scale = rubric.get('scale', [])
                    criteria = rubric.get('criteria', [])
                    
                    if scale and criteria:
                        max_scale_val = max([s['value'] for s in scale])
                        total_possible = max_scale_val * len(criteria)
                        quadrants_config['quiz_max_possible'] = total_possible
                        quadrants_config['quiz_max_50'] = round(total_possible * 0.5, 2)

            if count > 1:
                stats_data['project_variance'] = round(statistics.variance(y_values), 2)
                stats_data['quiz_variance'] = round(statistics.variance(x_values), 2)
            else:
                stats_data['project_variance'] = 0
                stats_data['quiz_variance'] = 0

        return Response({
            'score_correlation': [analysis_item],
            'team_variance': team_variance,
            'global_stats': stats_data,
            'quadrants_config': quadrants_config,
            'raw_scores': QuizProjectScoreSerializer(queryset, many=True).data
        })

    def create(self, request, *args, **kwargs):
        # We override create to handle file upload specifically
        # The standard create expects JSON for a single object usually, but here we want to upload a CSV
        quiz_id = self.kwargs['quiz_id']
        try:
            quiz = Quiz.objects.get(id=quiz_id)
        except Quiz.DoesNotExist:
            return Response({'detail': 'Quiz not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permissions - assume owner or allowed instructor
        if quiz.owner != request.user.instructor and not quiz.allowed_instructors.filter(id=request.user.instructor.id).exists():
            return Response({'detail': 'You do not have permission to modify this quiz.'}, status=status.HTTP_403_FORBIDDEN)

        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded_file = file_obj.read().decode('utf-8').splitlines()
            reader = csv.reader(decoded_file)
            header = next(reader, None)
            
            if not header:
                return Response({'detail': 'Empty CSV file.'}, status=status.HTTP_400_BAD_REQUEST)

            # Detect columns
            header_map = {col.lower().strip(): i for i, col in enumerate(header)}
            
            project_idx = header_map.get('project score')
            quiz_idx = header_map.get('quiz score')
            team_idx = header_map.get('team')
            grade_idx = header_map.get('grade')

            # Fallback to positional if headers not found and we have enough columns
            if project_idx is None or quiz_idx is None:
                # Try to guess: 0 -> Project, 1 -> Quiz if headers don't match specific names
                # But to be safe, required headers are better.
                # Let's support positional as fallback if headers don't strictly match known names
                # but maybe just 0 and 1.
                if len(header) >= 2:
                    # Heuristic: check if they look like numbers? No, can't check header
                    # Assume user follows instructions. 
                    # If headers are missing "project score" etc, maybe they ARE the data?
                    # But standard practice is header row first.
                    
                    # If we didn't find specific headers, check if we can rely on order
                    pass

            if project_idx is None:
                project_idx = 0
            if quiz_idx is None:
                quiz_idx = 1
            if team_idx is None:
                # check for 'team'
                pass # already checked above
            
            # Re-read or just process
            # Since we already consumed header, we iterate rest
            
            scores_to_create = []
            
            # Clear existing scores for this quiz? 
            # Usually overwrite or append? "Add way to import" implies append or refresh.
            # "The csv that will be uploaded for each quiz" 
            # Let's Delete existing to avoid duplicates if re-uploading the same sheet.
            QuizProjectScore.objects.filter(quiz=quiz).delete()

            for row_idx, row in enumerate(reader):
                if not row: continue
                if len(row) < 2: continue # skip empty or malformed

                try:
                    p_score = float(row[project_idx])
                    q_score = float(row[quiz_idx])
                    
                    team_val = row[team_idx].strip() if team_idx is not None and team_idx < len(row) else None
                    grade_val = row[grade_idx].strip() if grade_idx is not None and grade_idx < len(row) else None

                    scores_to_create.append(QuizProjectScore(
                        quiz=quiz,
                        project_score=p_score,
                        quiz_score=q_score,
                        team=team_val,
                        grade_level=grade_val
                    ))
                except ValueError:
                    continue # Skip bad rows
            
            QuizProjectScore.objects.bulk_create(scores_to_create)

            return Response({'detail': f'Successfully imported {len(scores_to_create)} scores.'}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'detail': f'Error processing file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
