from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.models import ensure_instructor
from accounts.permissions import IsInstructor
from problems.models import ProblemBank, Rubric

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
