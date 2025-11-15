from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    InstructorViewSet,
    LoginView,
    LogoutView,
    ProblemBankProblemListCreate,
    ProblemBankViewSet,
    ProblemViewSet,
    PublicAttemptComplete,
    PublicAttemptSlotAnswer,
    PublicQuizDetail,
    PublicQuizStart,
    QuizAllowedInstructorDelete,
    QuizAllowedInstructorList,
    QuizSlotListCreate,
    QuizSlotViewSet,
    SlotProblemDeleteView,
    SlotProblemListCreate,
    QuizViewSet,
)

router = DefaultRouter()
router.register('instructors', InstructorViewSet, basename='instructor')
router.register('problem-banks', ProblemBankViewSet, basename='problem-bank')
router.register('problems', ProblemViewSet, basename='problem')
router.register('quizzes', QuizViewSet, basename='quiz')
router.register('slots', QuizSlotViewSet, basename='slot')

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='api-login'),
    path('auth/logout/', LogoutView.as_view(), name='api-logout'),
    path('', include(router.urls)),
    path('problem-banks/<int:bank_id>/problems/', ProblemBankProblemListCreate.as_view(), name='bank-problems'),
    path('quizzes/<int:quiz_id>/slots/', QuizSlotListCreate.as_view(), name='quiz-slots'),
    path('quizzes/<int:quiz_id>/allowed-instructors/', QuizAllowedInstructorList.as_view(), name='quiz-allowed-list'),
    path(
        'quizzes/<int:quiz_id>/allowed-instructors/<int:instructor_id>/',
        QuizAllowedInstructorDelete.as_view(),
        name='quiz-allowed-delete',
    ),
    path('slots/<int:slot_id>/slot-problems/', SlotProblemListCreate.as_view(), name='slot-problem-list'),
    path('slot-problems/<int:pk>/', SlotProblemDeleteView.as_view(), name='slot-problem-delete'),
    path('public/quizzes/<slug:public_id>/', PublicQuizDetail.as_view(), name='public-quiz-detail'),
    path('public/quizzes/<slug:public_id>/start/', PublicQuizStart.as_view(), name='public-quiz-start'),
    path('public/attempts/<int:attempt_id>/slots/<int:slot_id>/answer/', PublicAttemptSlotAnswer.as_view(), name='attempt-answer'),
    path('public/attempts/<int:attempt_id>/complete/', PublicAttemptComplete.as_view(), name='attempt-complete'),
]
