from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    InstructorViewSet,
    CSRFTokenView,
    LoginView,
    LogoutView,
    ProblemBankProblemListCreate,
    ProblemBankViewSet,
    ProblemViewSet,
    PublicAttemptComplete,
    PublicAttemptDetail,
    PublicAttemptSlotAnswer,
    PublicAttemptSlotInteraction,
    PublicQuizDetail,
    PublicQuizStart,
    QuizAllowedInstructorDelete,
    QuizAllowedInstructorList,
    QuizRubricView,
    QuizSlotListCreate,
    QuizSlotViewSet,
    QuizAttemptDetail,
    QuizAttemptInteractions,
    QuizAttemptList,
    ResponseConfigView,
    SlotProblemDeleteView,
    SlotProblemListCreate,
    SlotProblemDeleteView,
    SlotProblemListCreate,
    QuizViewSet,
    DashboardStatsView,
)

router = DefaultRouter()
router.register('instructors', InstructorViewSet, basename='instructor')
router.register('problem-banks', ProblemBankViewSet, basename='problem-bank')
router.register('problems', ProblemViewSet, basename='problem')
router.register('quizzes', QuizViewSet, basename='quiz')
router.register('slots', QuizSlotViewSet, basename='slot')

urlpatterns = [
    path('auth/csrf/', CSRFTokenView.as_view(), name='api-csrf'),
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
    path('quizzes/<int:quiz_id>/rubric/', QuizRubricView.as_view(), name='quiz-rubric'),
    path('quizzes/<int:quiz_id>/attempts/', QuizAttemptList.as_view(), name='quiz-attempts'),
    path(
        'quizzes/<int:quiz_id>/attempts/<int:attempt_id>/',
        QuizAttemptDetail.as_view(),
        name='quiz-attempt-detail',
    ),
    path(
        'quizzes/<int:quiz_id>/attempts/<int:attempt_id>/interactions/',
        QuizAttemptInteractions.as_view(),
        name='quiz-attempt-interactions',
    ),
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('slots/<int:slot_id>/slot-problems/', SlotProblemListCreate.as_view(), name='slot-problem-list'),
    path('slot-problems/<int:pk>/', SlotProblemDeleteView.as_view(), name='slot-problem-delete'),
    path('public/quizzes/<slug:public_id>/', PublicQuizDetail.as_view(), name='public-quiz-detail'),
    path('public/quizzes/<slug:public_id>/start/', PublicQuizStart.as_view(), name='public-quiz-start'),
    path('public/attempts/<int:attempt_id>/', PublicAttemptDetail.as_view(), name='public-attempt-detail'),
    path('public/attempts/<int:attempt_id>/slots/<int:slot_id>/answer/', PublicAttemptSlotAnswer.as_view(), name='attempt-answer'),
    path('public/attempts/<int:attempt_id>/complete/', PublicAttemptComplete.as_view(), name='attempt-complete'),
    path(
        'public/attempts/<int:attempt_id>/slots/<int:slot_id>/interactions/',
        PublicAttemptSlotInteraction.as_view(),
        name='attempt-slot-interactions',
    ),
    path('response-config/', ResponseConfigView.as_view(), name='response-config'),
]
