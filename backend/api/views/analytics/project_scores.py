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
        
        return Response({
            'score_correlation': [analysis_item],
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
